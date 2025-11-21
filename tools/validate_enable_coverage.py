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
from typing import List, Set

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


def try_depluralize(word: str) -> List[str]:
    """
    Try to find potential singular/base forms by removing plural suffixes.

    Returns list of potential base forms to check.

    Examples:
        "abrosias" → ["abrosia"]
        "aboves" → ["above"]
        "absentmindednesses" → ["absentmindedness", "absentmindednes"]
        "academias" → ["academia"]
    """
    candidates = []

    # Try removing 's'
    if word.endswith('s') and len(word) > 2:
        candidates.append(word[:-1])

    # Try removing 'es'
    if word.endswith('es') and len(word) > 3:
        candidates.append(word[:-2])

    # Try removing 'ies' and adding 'y' (e.g., "accidies" → "accidy")
    if word.endswith('ies') and len(word) > 4:
        candidates.append(word[:-3] + 'y')

    return candidates


def analyze_missing_words(missing: Set[str], lexicon_words: Set[str]) -> dict:
    """
    Analyze missing words to categorize them.

    Returns dict with:
        - 'likely_plurals': Words where base form exists in lexicon
        - 'true_missing': Words where no base form found
    """
    likely_plurals = []
    true_missing = []

    for word in sorted(missing):
        # Try to find base forms
        base_forms = try_depluralize(word)

        # Check if any base form exists in lexicon
        found_base = False
        for base in base_forms:
            if base in lexicon_words:
                likely_plurals.append({
                    'word': word,
                    'base': base,
                })
                found_base = True
                break

        if not found_base:
            true_missing.append(word)

    return {
        'likely_plurals': likely_plurals,
        'true_missing': true_missing,
    }


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

    # Analyze missing words
    if missing:
        logger.info("")
        logger.info("=" * 70)
        logger.info("Missing Word Analysis")
        logger.info("=" * 70)

        analysis = analyze_missing_words(missing, lexicon_words)

        likely_plurals = analysis['likely_plurals']
        true_missing = analysis['true_missing']

        logger.info(f"Likely plurals (base form exists):  {len(likely_plurals):,}")
        logger.info(f"True missing (no base form found):  {len(true_missing):,}")
        logger.info("")

        # Show sample of likely plurals
        if likely_plurals:
            logger.info("Sample likely plurals (first 15):")
            for item in likely_plurals[:15]:
                logger.info(f"  - {item['word']:30} → base: {item['base']}")

            if len(likely_plurals) > 15:
                logger.info(f"  ... and {len(likely_plurals) - 15:,} more")
            logger.info("")

        # Show sample of true missing
        if true_missing:
            logger.info("Sample true missing words (first 15):")
            for word in true_missing[:15]:
                logger.info(f"  - {word}")

            if len(true_missing) > 15:
                logger.info(f"  ... and {len(true_missing) - 15:,} more")
            logger.info("")

        # Analysis summary
        plural_pct = (len(likely_plurals) / len(missing)) * 100 if missing else 0
        logger.info("=" * 70)
        logger.info("Summary:")
        logger.info(f"  {plural_pct:.1f}% of missing words are likely plurals")
        logger.info(f"  {100 - plural_pct:.1f}% are truly missing (no base form)")
        logger.info("")
        logger.info("Note: ENABLE includes many unusual plural forms not typically")
        logger.info("listed as separate entries in dictionaries (e.g., 'absentmindednesses').")

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
