#!/usr/bin/env python3
"""
core_ingest.py — Parse EOWL word list and normalize to schema.

Reads:
  - data/raw/en/eowl.txt

Outputs:
  - data/intermediate/en/core_entries.jsonl

Each entry has:
  - word (NFKC normalized)
  - pos: [] (empty; no POS in source)
  - labels: {} (empty; no labels in source)
  - word_count: 1 (single words from these sources)
  - lemma: null
  - sources: ["eowl"]

Note: ENABLE is NOT ingested here. It's only used for optional validation
via 'make validate-enable'. See tools/validate_enable_coverage.py.
"""

import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Set

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def normalize_word(word: str) -> str:
    """Apply Unicode NFKC normalization and basic cleanup."""
    # Strip whitespace
    word = word.strip()
    # Apply NFKC normalization
    word = unicodedata.normalize('NFKC', word)
    # Convert to lowercase for canonical form
    word = word.lower()
    return word


def read_wordlist(filepath: Path, source_id: str) -> Set[str]:
    """Read a plain text wordlist and return normalized words."""
    words = set()

    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return words

    logger.info(f"Reading {source_id} from {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            word = line.strip()
            if not word or word.startswith('#'):
                continue

            normalized = normalize_word(word)
            if normalized:
                words.add(normalized)

    logger.info(f"  -> Loaded {len(words):,} unique words from {source_id}")
    return words


def create_word_sources(eowl_words: Set[str]) -> Dict[str, list]:
    """Create word source dict from EOWL words."""
    word_sources = {}

    for word in eowl_words:
        word_sources[word] = ["eowl"]

    logger.info(f"Total entries: {len(word_sources):,} unique words")
    return word_sources


def create_entry(word: str, sources: list) -> dict:
    """Create a normalized entry following the schema."""
    return {
        "word": word,
        "pos": [],
        "labels": {},
        "word_count": 1,  # Core sources only contain single words
        "lemma": None,
        "sources": sorted(set(sources))  # deduplicate and sort
    }


def write_jsonl(entries: list, output_path: Path) -> None:
    """Write entries to JSONL format using orjson."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing {len(entries):,} entries to {output_path}")

    with open(output_path, 'wb') as f:
        for entry in entries:
            # orjson.dumps returns bytes
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"Written: {output_path}")


def main():
    """Main ingestion pipeline."""
    # Paths
    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / "en"
    intermediate_dir = data_root / "intermediate" / "en"

    eowl_path = raw_dir / "eowl.txt"
    output_path = intermediate_dir / "core_entries.jsonl"

    logger.info("EOWL word list ingestion (English)")
    logger.info("Note: ENABLE is NOT ingested - use 'make validate-enable' for validation")
    logger.info("")

    # Read EOWL
    eowl_words = read_wordlist(eowl_path, "EOWL")

    if not eowl_words:
        logger.error("EOWL not found. This is required for the build.")
        logger.error("Run 'make fetch-en' to fetch EOWL and other sources.")
        sys.exit(1)

    # Create word sources dict
    word_sources = create_word_sources(eowl_words)

    # Create entries
    entries = [
        create_entry(word, sources)
        for word, sources in sorted(word_sources.items())
    ]

    # Write output
    write_jsonl(entries, output_path)

    # Stats
    logger.info("")
    logger.info("Statistics:")
    logger.info(f"  Total unique words: {len(entries):,}")
    logger.info(f"  All from EOWL")
    logger.info("")
    logger.info("Core ingest complete")


if __name__ == '__main__':
    main()
