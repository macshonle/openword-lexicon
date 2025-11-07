#!/usr/bin/env python3
"""
manifest.py — Generate MANIFEST.json with checksums for reproducibility.

Reads:
  - All build artifacts

Outputs:
  - MANIFEST.json (checksums, sizes, timestamps)

The manifest provides a diffable snapshot of the build output
for verification and reproducibility.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()

    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def get_file_info(filepath: Path) -> Dict:
    """Get file metadata (size, hash, mtime)."""
    if not filepath.exists():
        return None

    stat = filepath.stat()

    return {
        'path': str(filepath.relative_to(Path.cwd())),
        'size_bytes': stat.st_size,
        'size_human': format_size(stat.st_size),
        'sha256': compute_sha256(filepath),
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


def format_size(size_bytes: int) -> str:
    """Format size in human-readable form."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def collect_artifacts(project_root: Path) -> Dict[str, List[Dict]]:
    """Collect all build artifacts and their metadata."""
    artifacts = {
        'core': [],
        'plus': [],
        'documentation': [],
        'source_metadata': []
    }

    data_dir = project_root / "data"

    # Core artifacts
    core_patterns = [
        data_dir / "build" / "core" / "core.trie",
        data_dir / "build" / "core" / "core.meta.json",
        data_dir / "filtered" / "core" / "family_friendly.jsonl",
        data_dir / "intermediate" / "core" / "entries_merged.jsonl",
        data_dir / "core" / "LICENSE"
    ]

    for pattern in core_patterns:
        info = get_file_info(pattern)
        if info:
            artifacts['core'].append(info)

    # Plus artifacts
    plus_patterns = [
        data_dir / "build" / "plus" / "plus.trie",
        data_dir / "build" / "plus" / "plus.meta.json",
        data_dir / "filtered" / "plus" / "family_friendly.jsonl",
        data_dir / "intermediate" / "plus" / "entries_merged.jsonl",
        data_dir / "plus" / "LICENSE"
    ]

    for pattern in plus_patterns:
        info = get_file_info(pattern)
        if info:
            artifacts['plus'].append(info)

    # Documentation
    doc_patterns = [
        project_root / "ATTRIBUTION.md",
        project_root / "docs" / "schema" / "entry.schema.json",
        project_root / "docs" / "labels.md"
    ]

    for pattern in doc_patterns:
        info = get_file_info(pattern)
        if info:
            artifacts['documentation'].append(info)

    # Source metadata
    source_patterns = list((data_dir / "raw").glob("*/*.SOURCE.json"))

    for source_file in source_patterns:
        info = get_file_info(source_file)
        if info:
            artifacts['source_metadata'].append(info)

    return artifacts


def generate_manifest(project_root: Path, output_path: Path):
    """Generate complete manifest with checksums."""
    logger.info("Generating MANIFEST.json")

    artifacts = collect_artifacts(project_root)

    # Build manifest
    manifest = {
        'version': '0.0.0',
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'generator': 'openword-lexicon/manifest.py',
        'distributions': {
            'core': {
                'license': 'CC BY 4.0',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                'artifacts': artifacts['core'],
                'artifact_count': len(artifacts['core']),
                'total_size_bytes': sum(a['size_bytes'] for a in artifacts['core'])
            },
            'plus': {
                'license': 'CC BY-SA 4.0',
                'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'artifacts': artifacts['plus'],
                'artifact_count': len(artifacts['plus']),
                'total_size_bytes': sum(a['size_bytes'] for a in artifacts['plus'])
            }
        },
        'documentation': artifacts['documentation'],
        'source_metadata': artifacts['source_metadata'],
        'build_info': {
            'python_version': '3.11+',
            'build_system': 'uv',
            'reproducible': True
        }
    }

    # Write manifest
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"✓ Manifest written: {output_path}")

    # Report stats
    logger.info("")
    logger.info("Manifest summary:")
    logger.info(f"  Core artifacts: {manifest['distributions']['core']['artifact_count']}")
    logger.info(f"  Core total size: {format_size(manifest['distributions']['core']['total_size_bytes'])}")
    logger.info(f"  Plus artifacts: {manifest['distributions']['plus']['artifact_count']}")
    logger.info(f"  Plus total size: {format_size(manifest['distributions']['plus']['total_size_bytes'])}")
    logger.info(f"  Documentation files: {len(artifacts['documentation'])}")
    logger.info(f"  Source metadata: {len(artifacts['source_metadata'])}")


def main():
    """Main manifest generation pipeline."""
    project_root = Path(__file__).parent.parent.parent
    output_path = project_root / "MANIFEST.json"

    logger.info("=" * 60)
    logger.info("PHASE 15: Manifest generation")
    logger.info("=" * 60)

    generate_manifest(project_root, output_path)

    logger.info("")
    logger.info("✓ Manifest generation complete")


if __name__ == '__main__':
    main()
