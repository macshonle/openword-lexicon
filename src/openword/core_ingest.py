#!/usr/bin/env python3
"""
core_ingest.py — Parse core word lists (ENABLE, EOWL) and normalize to schema.

Reads:
  - data/raw/core/enable1.txt
  - data/raw/core/eowl.txt

Outputs:
  - data/intermediate/core/core_entries.jsonl

Each entry has:
  - word (NFKC normalized)
  - pos: [] (empty; no POS in source)
  - labels: {} (empty; no labels in source)
  - is_phrase: false
  - lemma: null
  - sources: ["enable"] or ["eowl"] or both
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


def merge_entries(enable_words: Set[str], eowl_words: Set[str]) -> Dict[str, list]:
    """Merge word sets and track sources."""
    word_sources = {}

    for word in enable_words:
        word_sources.setdefault(word, []).append("enable")

    for word in eowl_words:
        word_sources.setdefault(word, []).append("eowl")

    logger.info(f"Merged entries: {len(word_sources):,} unique words")
    return word_sources


def create_entry(word: str, sources: list) -> dict:
    """Create a normalized entry following the schema."""
    return {
        "word": word,
        "pos": [],
        "labels": {},
        "is_phrase": False,
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
            line = orjson.dumps(entry) + b'\n'
            f.write(line)

    logger.info(f"Written: {output_path}")


def main():
    """Main ingestion pipeline."""
    # Paths
    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / "core"
    intermediate_dir = data_root / "intermediate" / "core"

    enable_path = raw_dir / "enable1.txt"
    eowl_path = raw_dir / "eowl.txt"
    output_path = intermediate_dir / "core_entries.jsonl"

    logger.info("Core word list ingestion")

    # Read source lists
    enable_words = read_wordlist(enable_path, "ENABLE")
    eowl_words = read_wordlist(eowl_path, "EOWL")

    if not enable_words and not eowl_words:
        logger.error("No source data found. Run 'make fetch-core' first.")
        sys.exit(1)

    # Merge and track sources
    word_sources = merge_entries(enable_words, eowl_words)

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
    logger.info(f"  ENABLE only: {sum(1 for e in entries if e['sources'] == ['enable']):,}")
    logger.info(f"  EOWL only: {sum(1 for e in entries if e['sources'] == ['eowl']):,}")
    logger.info(f"  Both sources: {sum(1 for e in entries if len(e['sources']) == 2):,}")
    logger.info("")
    logger.info("Core ingest complete")


if __name__ == '__main__':
    main()
