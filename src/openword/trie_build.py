#!/usr/bin/env python3
"""
trie_build.py — Build compact trie structures with metadata sidecar.

Reads:
  - data/filtered/{core,plus}/family_friendly.jsonl

Outputs:
  - data/build/{core,plus}/{distribution}.trie (MARISA trie)
  - data/build/{core,plus}/{distribution}.meta.json (metadata as JSON array)

The trie stores word strings for fast prefix/membership queries.
The metadata file stores full entry data indexed by position.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
import sys

import marisa_trie
import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_entries(input_path: Path) -> List[Dict]:
    """Load entries from JSONL file."""
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return []

    logger.info(f"Loading entries from {input_path.name}")

    entries = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                logger.info(f"  Loaded {line_num:,} entries...")

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    logger.info(f"  → Loaded {len(entries):,} entries")
    return entries


def build_trie(entries: List[Dict], trie_path: Path, meta_path: Path):
    """
    Build MARISA trie and metadata sidecar.

    The trie stores words for fast lookups.
    Metadata is stored separately indexed by trie position.
    """
    logger.info(f"Building trie with {len(entries):,} entries")

    # Sort entries by word (required for trie)
    entries = sorted(entries, key=lambda e: e['word'])

    # Extract words for trie
    words = [entry['word'] for entry in entries]

    # Build trie
    logger.info("  Building MARISA trie...")
    trie = marisa_trie.Trie(words)

    # Save trie
    trie_path.parent.mkdir(parents=True, exist_ok=True)
    trie.save(str(trie_path))
    logger.info(f"  ✓ Trie saved: {trie_path}")

    # Save metadata as JSON array (indexed by position)
    logger.info("  Writing metadata...")
    with open(meta_path, 'wb') as f:
        # Write as JSON array
        f.write(b'[\n')
        for i, entry in enumerate(entries):
            if i > 0:
                f.write(b',\n')
            f.write(b'  ')
            f.write(orjson.dumps(entry))
        f.write(b'\n]\n')

    logger.info(f"  ✓ Metadata saved: {meta_path}")

    # Report stats
    trie_size_kb = trie_path.stat().st_size / 1024
    meta_size_kb = meta_path.stat().st_size / 1024

    logger.info(f"  Trie size: {trie_size_kb:.1f} KB")
    logger.info(f"  Metadata size: {meta_size_kb:.1f} KB")
    logger.info(f"  Total: {trie_size_kb + meta_size_kb:.1f} KB")


def verify_trie(trie_path: Path, entries: List[Dict]):
    """Verify trie can be loaded and queried."""
    logger.info("Verifying trie...")

    trie = marisa_trie.Trie()
    trie.load(str(trie_path))

    # Check a few words
    test_words = [e['word'] for e in entries[:5]] if entries else []

    for word in test_words:
        if word in trie:
            logger.info(f"  ✓ Found: '{word}'")
        else:
            logger.error(f"  ✗ Missing: '{word}'")

    # Check word count
    if len(trie) == len(entries):
        logger.info(f"  ✓ Word count matches: {len(trie):,}")
    else:
        logger.error(f"  ✗ Word count mismatch: {len(trie)} vs {len(entries)}")


def main():
    """Main trie build pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    filtered_dir = data_root / "filtered"
    build_dir = data_root / "build"

    logger.info("=" * 60)
    logger.info("PHASE 12: Trie build (MARISA)")
    logger.info("=" * 60)

    # Build core trie
    core_input = filtered_dir / "core" / "family_friendly.jsonl"
    core_trie = build_dir / "core" / "core.trie"
    core_meta = build_dir / "core" / "core.meta.json"

    if core_input.exists():
        logger.info("\nBuilding CORE distribution trie...")
        entries = load_entries(core_input)
        if entries:
            build_trie(entries, core_trie, core_meta)
            verify_trie(core_trie, entries)

    # Build plus trie
    plus_input = filtered_dir / "plus" / "family_friendly.jsonl"
    plus_trie = build_dir / "plus" / "plus.trie"
    plus_meta = build_dir / "plus" / "plus.meta.json"

    if plus_input.exists():
        logger.info("\nBuilding PLUS distribution trie...")
        entries = load_entries(plus_input)
        if entries:
            build_trie(entries, plus_trie, plus_meta)
            verify_trie(plus_trie, entries)

    logger.info("")
    logger.info("✓ Trie build complete")


if __name__ == '__main__':
    main()
