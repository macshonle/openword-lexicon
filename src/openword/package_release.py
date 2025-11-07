#!/usr/bin/env python3
"""
package_release.py — Package distributions into versioned release archives.

Reads:
  - data/build/{core,plus}/*.{trie,json}
  - data/{core,plus}/LICENSE
  - ATTRIBUTION.md

Outputs:
  - data/artifacts/releases/openword-lexicon-core-{version}.tar.zst
  - data/artifacts/releases/openword-lexicon-plus-{version}.tar.zst
  - data/artifacts/releases/*.sha256

Each tarball contains:
  - {distribution}.trie
  - {distribution}.meta.json
  - LICENSE
  - ATTRIBUTION.md
  - README.txt (quickstart)
"""

import hashlib
import logging
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from typing import List

import orjson
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


def create_readme(distribution: str) -> str:
    """Generate a quickstart README for the distribution."""
    license_type = "CC BY 4.0" if distribution == "core" else "CC BY-SA 4.0"

    return f"""# Openword Lexicon — {distribution.upper()} Distribution

Version: {VERSION}
License: {license_type}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Contents

- `{distribution}.trie` — Compact MARISA trie for fast word lookups
- `{distribution}.meta.json` — Full entry metadata (JSON array)
- `LICENSE` — Full license text
- `ATTRIBUTION.md` — Source attributions

## Quick Start (Python)

```python
import marisa_trie
import json

# Load trie
trie = marisa_trie.Trie()
trie.load('{distribution}.trie')

# Check if word exists
if 'castle' in trie:
    print("Found!")

# Pick a word and fetch its metadata
word = 'castle'
idx = trie[word][0]  # First match

# Load metadata
with open('{distribution}.meta.json', 'r') as f:
    metadata = json.load(f)

# Get entry
entry = metadata[idx]
print(entry)
```

## Statistics

Run `wc -l {distribution}.meta.json` to see entry count.
Run `du -h {distribution}.trie` to see trie size.

## License & Attribution

See LICENSE and ATTRIBUTION.md for full details.

## Support

- Repository: https://github.com/macshonle/openword-lexicon
- Issues: https://github.com/macshonle/openword-lexicon/issues
- Documentation: https://github.com/macshonle/openword-lexicon/blob/main/README.md
"""


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()

    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def package_distribution(distribution: str, version: str,
                        project_root: Path, output_dir: Path) -> Path:
    """
    Package a distribution into a versioned tarball.

    Returns: path to created tarball
    """
    logger.info(f"Packaging {distribution} distribution (v{version})")

    # Paths
    build_dir = project_root / "data" / "build" / distribution
    license_path = project_root / "data" / distribution / "LICENSE"
    attribution_path = project_root / "ATTRIBUTION.md"

    # Check required files exist
    trie_file = build_dir / f"{distribution}.trie"
    meta_file = build_dir / f"{distribution}.meta.json"

    if not trie_file.exists():
        logger.error(f"Missing trie file: {trie_file}")
        return None

    if not meta_file.exists():
        logger.error(f"Missing metadata file: {meta_file}")
        return None

    # Create staging directory
    stage_dir = output_dir / f"openword-lexicon-{distribution}-{version}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    # Copy files to staging
    shutil.copy2(trie_file, stage_dir / f"{distribution}.trie")
    shutil.copy2(meta_file, stage_dir / f"{distribution}.meta.json")

    if license_path.exists():
        shutil.copy2(license_path, stage_dir / "LICENSE")

    if attribution_path.exists():
        shutil.copy2(attribution_path, stage_dir / "ATTRIBUTION.md")

    # Create README
    readme_content = create_readme(distribution)
    with open(stage_dir / "README.txt", 'w') as f:
        f.write(readme_content)

    # Create tarball
    tarball_name = f"openword-lexicon-{distribution}-{version}.tar.zst"
    tarball_path = output_dir / tarball_name

    logger.info(f"  Creating tarball: {tarball_name}")

    # Use tar with zstd compression
    # Fall back to gzip if zstd not available
    try:
        subprocess.run([
            'tar',
            '-C', str(output_dir),
            '-cf', str(tarball_path),
            '--use-compress-program=zstd',
            stage_dir.name
        ], check=True, capture_output=True)
        logger.info(f"  ✓ Created: {tarball_path}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fall back to gzip
        logger.warning("  zstd not available, using gzip")
        tarball_name = f"openword-lexicon-{distribution}-{version}.tar.gz"
        tarball_path = output_dir / tarball_name

        with tarfile.open(tarball_path, 'w:gz') as tar:
            tar.add(stage_dir, arcname=stage_dir.name)

        logger.info(f"  ✓ Created: {tarball_path}")

    # Compute checksum
    sha256 = compute_sha256(tarball_path)
    checksum_path = tarball_path.with_suffix(tarball_path.suffix + '.sha256')

    with open(checksum_path, 'w') as f:
        f.write(f"{sha256}  {tarball_path.name}\n")

    logger.info(f"  ✓ Checksum: {checksum_path}")

    # Clean up staging
    shutil.rmtree(stage_dir)

    # Report size
    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    logger.info(f"  Size: {size_mb:.1f} MB")

    return tarball_path


def verify_package(tarball_path: Path) -> bool:
    """Verify package can be unpacked and contains expected files."""
    logger.info(f"Verifying package: {tarball_path.name}")

    # Create temp directory for extraction
    temp_dir = tarball_path.parent / "_verify_temp"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Extract
        if tarball_path.suffix == '.zst':
            subprocess.run([
                'tar',
                '-C', str(temp_dir),
                '-xf', str(tarball_path),
                '--use-compress-program=zstd'
            ], check=True, capture_output=True)
        else:
            with tarfile.open(tarball_path, 'r:*') as tar:
                tar.extractall(temp_dir)

        # Find extracted directory
        extracted_dirs = list(temp_dir.glob("openword-lexicon-*"))
        if not extracted_dirs:
            logger.error("  ✗ No extracted directory found")
            return False

        extracted_dir = extracted_dirs[0]

        # Check required files
        required_files = ['README.txt', 'LICENSE', 'ATTRIBUTION.md']
        distribution = 'core' if 'core' in tarball_path.name else 'plus'
        required_files.extend([f'{distribution}.trie', f'{distribution}.meta.json'])

        for filename in required_files:
            filepath = extracted_dir / filename
            if not filepath.exists():
                logger.error(f"  ✗ Missing file: {filename}")
                return False

        logger.info("  ✓ All required files present")

        # Try loading trie
        try:
            import marisa_trie
            trie = marisa_trie.Trie()
            trie.load(str(extracted_dir / f'{distribution}.trie'))

            # Test lookup
            if len(trie) > 0:
                # Get first word
                for word in list(trie)[:1]:
                    if word in trie:
                        logger.info(f"  ✓ Trie lookup works: '{word}' found")
                    break

            logger.info(f"  ✓ Trie contains {len(trie):,} words")
        except Exception as e:
            logger.error(f"  ✗ Trie verification failed: {e}")
            return False

        logger.info("  ✓ Package verification passed")
        return True

    except Exception as e:
        logger.error(f"  ✗ Verification failed: {e}")
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Main packaging pipeline."""
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / "data" / "artifacts" / "releases"

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("PHASE 16: Packaging & releases")
    logger.info("=" * 60)
    logger.info(f"Version: {VERSION}")
    logger.info("")

    # Package core distribution
    core_tarball = package_distribution('core', VERSION, project_root, output_dir)

    if core_tarball:
        logger.info("")
        verify_package(core_tarball)

    # Package plus distribution
    logger.info("")
    plus_tarball = package_distribution('plus', VERSION, project_root, output_dir)

    if plus_tarball:
        logger.info("")
        verify_package(plus_tarball)

    logger.info("")
    logger.info("✓ Packaging complete")
    logger.info(f"  Release directory: {output_dir}")

    # List all release files
    logger.info("")
    logger.info("Release artifacts:")
    for artifact in sorted(output_dir.glob("openword-lexicon-*")):
        size_mb = artifact.stat().st_size / (1024 * 1024)
        logger.info(f"  {artifact.name} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()
