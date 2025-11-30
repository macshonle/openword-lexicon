#!/usr/bin/env python3
"""
package_release.py — Package language lexicons into versioned release archives.

Reads:
  - data/build/en.trie (full profile)
  - data/build/en-game.trie (game profile)
  - data/build/en-*.json.gz (modular metadata)

Outputs:
  - data/artifacts/releases/openword-lexicon-en-{version}.tar.zst
  - data/artifacts/releases/*.sha256

Each tarball contains:
  - en.trie (full profile)
  - en-game.trie (game profile)
  - en-*.json.gz (6 metadata modules)
  - README.txt (quickstart)
"""

import hashlib
import logging
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import tomllib


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_version() -> str:
    """Read project version from pyproject.toml so releases stay in sync."""
    project_root = Path(__file__).parent.parent.parent
    pyproject_path = project_root / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


VERSION = load_version()

# Expected metadata modules
METADATA_MODULES = [
    'frequency',
    'sources',
    'lemmas',
    'syllables',
    'concreteness',
    'lemma-groups',
]


def create_readme(lang: str, files: list[str]) -> str:
    """Generate a quickstart README for the distribution."""
    file_list = "\n".join(f"- `{f}`" for f in sorted(files))

    return f"""# Openword Lexicon — {lang.upper()} Distribution

Version: {VERSION}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC

## Contents

{file_list}

## Profiles

- `{lang}.trie` — Full profile: all words from lexicon
- `{lang}-game.trie` — Game profile: pure lowercase a-z only (for word games)

## Metadata Modules

- `{lang}-frequency.json.gz` — Frequency tier assignments (A-P scale)
- `{lang}-sources.json.gz` — Source attribution per word
- `{lang}-lemmas.json.gz` — Base lemma forms
- `{lang}-syllables.json.gz` — Syllable count data
- `{lang}-concreteness.json.gz` — Concreteness ratings
- `{lang}-lemma-groups.json.gz` — Lemma groupings

## Quick Start (Python)

```python
import marisa_trie
import gzip
import json

# Load trie (game profile for word games)
trie = marisa_trie.Trie()
trie.load('{lang}-game.trie')

# Check if word exists
if 'castle' in trie:
    print("Found!")

# Load frequency metadata
with gzip.open('{lang}-frequency.json.gz', 'rt') as f:
    frequency = json.load(f)

# Get frequency tier for a word
tier = frequency.get('castle')  # Returns tier like 'D' or None
```

## Statistics

Run `wc -l` on decompressed metadata to see entry counts.
Run `du -h *.trie` to see trie sizes.

## Support

- Repository: https://github.com/macshonle/openword-lexicon
- Issues: https://github.com/macshonle/openword-lexicon/issues
"""


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()

    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def package_language(lang: str, version: str,
                     project_root: Path, output_dir: Path) -> Path | None:
    """
    Package a language lexicon into a versioned tarball.

    Returns: path to created tarball, or None if required files missing
    """
    logger.info(f"Packaging {lang} lexicon (v{version})")

    build_dir = project_root / "data" / "build"

    # Check required trie files exist
    trie_full = build_dir / f"{lang}.trie"
    trie_game = build_dir / f"{lang}-game.trie"

    if not trie_full.exists():
        logger.error(f"Missing trie file: {trie_full}")
        return None

    if not trie_game.exists():
        logger.error(f"Missing game trie file: {trie_game}")
        return None

    # Collect all files to package
    files_to_package = [
        (trie_full, f"{lang}.trie"),
        (trie_game, f"{lang}-game.trie"),
    ]

    # Add metadata modules
    for module in METADATA_MODULES:
        meta_file = build_dir / f"{lang}-{module}.json.gz"
        if meta_file.exists():
            files_to_package.append((meta_file, meta_file.name))
        else:
            logger.warning(f"  Missing optional metadata: {meta_file.name}")

    # Create staging directory
    stage_dir = output_dir / f"openword-lexicon-{lang}-{version}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # Copy files to staging
    staged_files = []
    for src_path, dest_name in files_to_package:
        dest_path = stage_dir / dest_name
        shutil.copy2(src_path, dest_path)
        staged_files.append(dest_name)
        logger.info(f"  Added: {dest_name}")

    # Create README
    readme_content = create_readme(lang, staged_files)
    readme_path = stage_dir / "README.txt"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    staged_files.append("README.txt")

    # Create tarball
    tarball_name = f"openword-lexicon-{lang}-{version}.tar.zst"
    tarball_path = output_dir / tarball_name

    logger.info(f"  Creating tarball: {tarball_name}")

    # Use tar with zstd compression, fall back to gzip if zstd not available
    try:
        subprocess.run([
            'tar',
            '-C', str(output_dir),
            '-cf', str(tarball_path),
            '--use-compress-program=zstd',
            stage_dir.name
        ], check=True, capture_output=True)
        logger.info(f"  Created: {tarball_path}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fall back to gzip
        logger.warning("  zstd not available, using gzip")
        tarball_name = f"openword-lexicon-{lang}-{version}.tar.gz"
        tarball_path = output_dir / tarball_name

        with tarfile.open(tarball_path, 'w:gz') as tar:
            tar.add(stage_dir, arcname=stage_dir.name)

        logger.info(f"  Created: {tarball_path}")

    # Compute checksum
    sha256 = compute_sha256(tarball_path)
    checksum_path = tarball_path.with_suffix(tarball_path.suffix + '.sha256')

    with open(checksum_path, 'w') as f:
        f.write(f"{sha256}  {tarball_path.name}\n")

    logger.info(f"  Checksum: {checksum_path}")

    # Clean up staging
    shutil.rmtree(stage_dir)

    # Report size
    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    logger.info(f"  Size: {size_mb:.1f} MB")

    return tarball_path


def verify_package(tarball_path: Path, lang: str) -> bool:
    """Verify package can be unpacked and contains expected files."""
    logger.info(f"Verifying package: {tarball_path.name}")

    # Create temp directory for extraction
    temp_dir = tarball_path.parent / "_verify_temp"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Extract using zstd pipe for compatibility
        if tarball_path.name.endswith('.tar.zst'):
            # Use zstd -d -c | tar x for better cross-platform compatibility
            zstd_proc = subprocess.Popen(
                ['zstd', '-d', '-c', str(tarball_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            tar_proc = subprocess.Popen(
                ['tar', '-xf', '-', '-C', str(temp_dir)],
                stdin=zstd_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            zstd_proc.stdout.close()
            tar_proc.communicate()
            if tar_proc.returncode != 0:
                raise subprocess.CalledProcessError(tar_proc.returncode, 'tar')
        else:
            with tarfile.open(tarball_path, 'r:*') as tar:
                tar.extractall(temp_dir)

        # Find extracted directory
        extracted_dirs = list(temp_dir.glob("openword-lexicon-*"))
        if not extracted_dirs:
            logger.error("  No extracted directory found")
            return False

        extracted_dir = extracted_dirs[0]

        # Check required files
        required_files = [
            'README.txt',
            f'{lang}.trie',
            f'{lang}-game.trie',
        ]

        for filename in required_files:
            filepath = extracted_dir / filename
            if not filepath.exists():
                logger.error(f"  Missing required file: {filename}")
                return False

        logger.info("  All required files present")

        # Try loading trie
        try:
            import marisa_trie
            trie = marisa_trie.Trie()
            trie.load(str(extracted_dir / f'{lang}.trie'))

            # Test lookup
            if len(trie) > 0:
                for word in list(trie)[:1]:
                    if word in trie:
                        logger.info(f"  Trie lookup works: '{word}' found")
                    break

            logger.info(f"  Full trie contains {len(trie):,} words")

            # Also check game trie
            game_trie = marisa_trie.Trie()
            game_trie.load(str(extracted_dir / f'{lang}-game.trie'))
            logger.info(f"  Game trie contains {len(game_trie):,} words")

        except Exception as e:
            logger.error(f"  Trie verification failed: {e}")
            return False

        logger.info("  Package verification passed")
        return True

    except Exception as e:
        logger.error(f"  Verification failed: {e}")
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Main packaging pipeline."""
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / "data" / "artifacts" / "releases"

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Packaging lexicon release")
    logger.info(f"Version: {VERSION}")
    logger.info("")

    # Package English lexicon
    lang = 'en'
    tarball = package_language(lang, VERSION, project_root, output_dir)

    if tarball:
        logger.info("")
        verify_package(tarball, lang)

    logger.info("")
    logger.info("Packaging complete")
    logger.info(f"  Release directory: {output_dir}")

    # List all release files
    logger.info("")
    logger.info("Release artifacts:")
    for artifact in sorted(output_dir.glob("openword-lexicon-*")):
        size_mb = artifact.stat().st_size / (1024 * 1024)
        logger.info(f"  {artifact.name} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()
