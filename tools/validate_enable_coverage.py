#!/usr/bin/env python3
"""
validate_enable_coverage.py — Validate lexicon coverage against ENABLE word list.

This is an optional validation tool to verify that the lexicon provides good
coverage of the classic ENABLE word list (172k Scrabble-style words).

ENABLE is no longer a required dependency - Wiktionary provides far more
comprehensive coverage. This script is used periodically to ensure we haven't
regressed on baseline word game vocabulary.

Usage:
    python tools/validate_enable_coverage.py

    # Or via Makefile:
    make validate-enable
"""

import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Set

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def normalize_word(word: str) -> str:
    """Apply Unicode NFKC normalization and lowercase."""
    word = word.strip()
    word = unicodedata.normalize('NFKC', word)
    word = word.lower()
    return word


def load_enable_words(enable_path: Path) -> Set[str]:
    """Load and normalize ENABLE word list."""
    words = set()

    if not enable_path.exists():
        logger.error(f"ENABLE file not found: {enable_path}")
        return words

    logger.info(f"Loading ENABLE from {enable_path}")

    with open(enable_path, 'r', encoding='utf-8') as f:
        for line in f:
            word = normalize_word(line)
            if word:
                words.add(word)

    logger.info(f"  Loaded {len(words):,} ENABLE words")
    return words


def load_lexicon_words(build_path: Path) -> Set[str]:
    """Load words from built unified lexicon."""
    words = set()

    if not build_path.exists():
        logger.error(f"Lexicon file not found: {build_path}")
        logger.error("Run 'make build-en' first to generate the lexicon.")
        return words

    logger.info(f"Loading lexicon from {build_path}")

    with open(build_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                word = entry.get('word', '').strip()

                # Skip multi-word phrases for ENABLE comparison
                # (ENABLE only contains single words)
                if entry.get('word_count', 1) > 1:
                    continue

                if word:
                    words.add(normalize_word(word))
            except json.JSONDecodeError:
                logger.warning(f"Line {line_num}: JSON decode error")
                continue

    logger.info(f"  Loaded {len(words):,} single-word lexicon entries")
    return words


def main():
    """Run ENABLE coverage validation."""
    # Paths
    data_root = Path(__file__).parent.parent / "data"
    enable_path = data_root / "raw" / "en" / "enable1.txt"

    # Try unified lexicon first, fall back to intermediate
    lexicon_path = data_root / "intermediate" / "unified" / "entries_tiered.jsonl"
    if not lexicon_path.exists():
        lexicon_path = data_root / "intermediate" / "en" / "wikt_entries.jsonl"

    logger.info("=" * 70)
    logger.info("ENABLE Coverage Validation")
    logger.info("=" * 70)
    logger.info("")

    # Load data
    enable_words = load_enable_words(enable_path)
    if not enable_words:
        logger.error("Failed to load ENABLE data")
        sys.exit(1)

    lexicon_words = load_lexicon_words(lexicon_path)
    if not lexicon_words:
        logger.error("Failed to load lexicon data")
        sys.exit(1)

    # Calculate coverage
    logger.info("")
    logger.info("=" * 70)
    logger.info("Coverage Analysis")
    logger.info("=" * 70)

    covered = enable_words & lexicon_words
    missing = enable_words - lexicon_words
    coverage_pct = (len(covered) / len(enable_words)) * 100

    logger.info(f"Total ENABLE words:     {len(enable_words):,}")
    logger.info(f"Covered by lexicon:     {len(covered):,}")
    logger.info(f"Missing from lexicon:   {len(missing):,}")
    logger.info(f"Coverage percentage:    {coverage_pct:.2f}%")

    # Show sample of missing words
    if missing:
        logger.info("")
        logger.info("Sample of missing words (first 20):")
        for word in sorted(missing)[:20]:
            logger.info(f"  - {word}")

        if len(missing) > 20:
            logger.info(f"  ... and {len(missing) - 20:,} more")

    # Extra words in lexicon
    extra = lexicon_words - enable_words
    logger.info("")
    logger.info(f"Extra words in lexicon (not in ENABLE): {len(extra):,}")
    logger.info("  (This is expected - Wiktionary has much broader coverage)")

    # Validation result
    logger.info("")
    logger.info("=" * 70)

    # We expect very high coverage (>99%) since Wiktionary is comprehensive
    if coverage_pct >= 99.0:
        logger.info("✓ VALIDATION PASSED - Excellent ENABLE coverage!")
        logger.info("")
        logger.info("The lexicon provides comprehensive coverage of classic")
        logger.info("Scrabble-style vocabulary (ENABLE word list).")
        sys.exit(0)
    elif coverage_pct >= 95.0:
        logger.warning("⚠ VALIDATION WARNING - Good but not excellent coverage")
        logger.warning("")
        logger.warning("Coverage is acceptable but some common words may be missing.")
        logger.warning("Consider investigating missing words.")
        sys.exit(0)
    else:
        logger.error("✗ VALIDATION FAILED - Poor ENABLE coverage")
        logger.error("")
        logger.error(f"Only {coverage_pct:.2f}% coverage - significant gaps detected.")
        logger.error("This may indicate data quality issues.")
        sys.exit(1)


if __name__ == '__main__':
    main()
