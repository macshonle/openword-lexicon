#!/usr/bin/env python3
"""
validate_childish_terms.py — Validate childish term labeling

Purpose:
  Analyze words labeled as 'childish' in our lexicon (from Wiktionary)
  and demonstrate how to filter them for family-friendly games.

Wiktionary Category:
  https://en.wiktionary.org/wiki/Category:English_childish_terms

  "English terms that are typically only used by, or to, children."

  Labels: childish, baby talk, infantile, puerile

Example Use Cases:
  - Family games: Exclude childish terms (e.g., "tushie", "poo-poo")
  - Educational apps: Filter by age-appropriateness
  - Word puzzles: Avoid informal/childish variants

Usage:
  python tools/validate_childish_terms.py

Output:
  - Statistics on childish term labeling
  - Sample childish terms by POS
  - Filtering recommendations for developers
"""

import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_lexicon(lexicon_path: Path) -> Dict[str, dict]:
    """Load lexicon entries from JSONL."""
    lexicon = {}

    if not lexicon_path.exists():
        logger.error(f"Lexicon not found: {lexicon_path}")
        logger.error("Run 'make build-en' first to generate the lexicon")
        sys.exit(1)

    logger.info(f"Loading lexicon from {lexicon_path}")

    with open(lexicon_path, 'rb') as f:
        for line in f:
            entry = orjson.loads(line)
            word = entry['id']
            lexicon[word] = entry

    logger.info(f"  Loaded {len(lexicon):,} entries")
    return lexicon


def analyze_childish_terms(lexicon: Dict[str, dict]) -> dict:
    """Analyze childish term labeling."""

    childish_words = {}

    for word, entry in lexicon.items():
        register_labels = entry.get('labels', {}).get('register', [])

        if 'childish' in register_labels:
            childish_words[word] = {
                'pos': entry.get('pos', []),
                'labels': register_labels,
                'sources': entry.get('sources', []),
                'frequency_tier': entry.get('frequency_tier'),
                'nsyll': entry.get('nsyll'),
            }

    # Statistics
    pos_counts = Counter()
    multi_label_count = 0
    also_vulgar = []
    also_informal = []

    for word, info in childish_words.items():
        for pos in info['pos']:
            pos_counts[pos] += 1

        labels = info['labels']
        if len(labels) > 1:
            multi_label_count += 1

        if 'vulgar' in labels:
            also_vulgar.append(word)
        if 'informal' in labels or 'colloquial' in labels:
            also_informal.append(word)

    return {
        'total_count': len(childish_words),
        'childish_words': childish_words,
        'pos_counts': pos_counts,
        'multi_label_count': multi_label_count,
        'also_vulgar': also_vulgar,
        'also_informal': also_informal,
    }


def print_report(analysis: dict):
    """Print validation report."""

    print()
    print("=" * 80)
    print("CHILDISH TERMS VALIDATION REPORT")
    print("=" * 80)
    print()

    print("SUMMARY")
    print("-" * 80)
    print(f"  Words labeled 'childish':                 {analysis['total_count']:,}")
    print(f"  Words with multiple register labels:      {analysis['multi_label_count']:,}")
    print(f"  Childish + vulgar:                        {len(analysis['also_vulgar']):,}")
    print(f"  Childish + informal/colloquial:           {len(analysis['also_informal']):,}")
    print()

    print("BREAKDOWN BY PART OF SPEECH")
    print("-" * 80)
    for pos, count in analysis['pos_counts'].most_common():
        print(f"  {pos:15} {count:6,}")
    print()

    print("SAMPLE CHILDISH TERMS")
    print("-" * 80)

    # Group by POS for samples
    by_pos = defaultdict(list)
    for word, info in analysis['childish_words'].items():
        for pos in info['pos'] or ['(no POS)']:
            by_pos[pos].append(word)

    for pos in ['NOU', 'VRB', 'ADJ', 'ITJ']:
        if pos in by_pos:
            words = by_pos[pos][:10]
            print(f"  {pos}:")
            for word in words:
                info = analysis['childish_words'][word]
                labels = info['labels']
                freq = info.get('frequency_tier', 'unknown')
                print(f"    {word:20} labels={labels} freq={freq}")

            if len(by_pos[pos]) > 10:
                print(f"    ... and {len(by_pos[pos]) - 10} more")
            print()

    if analysis['also_vulgar']:
        print("CHILDISH + VULGAR (e.g., bathroom humor)")
        print("-" * 80)
        for word in analysis['also_vulgar'][:15]:
            info = analysis['childish_words'][word]
            print(f"  {word:20} pos={info['pos']}")
        if len(analysis['also_vulgar']) > 15:
            print(f"  ... and {len(analysis['also_vulgar']) - 15} more")
        print()

    print("=" * 80)
    print("USE CASES FOR DEVELOPERS")
    print("=" * 80)
    print()

    print("1. FAMILY-FRIENDLY WORD GAMES")
    print("   Filter: Exclude 'childish' + 'vulgar' labels")
    print("   Example: Avoid 'poo-poo', 'wee-wee', 'tushie'")
    print()

    print("2. EDUCATIONAL APPS (Age-Appropriate)")
    print("   Filter: Include OR exclude 'childish' based on target age")
    print("   - Ages 3-5: INCLUDE childish terms (familiar vocabulary)")
    print("   - Ages 8+: EXCLUDE childish terms (mature vocabulary)")
    print()

    print("3. PROFESSIONAL/FORMAL CONTEXTS")
    print("   Filter: Exclude 'childish', 'informal', 'colloquial'")
    print("   Example: Business writing tools, academic spell-checkers")
    print()

    print("4. WORD PUZZLES (Crosswords, Scrabble-like)")
    print("   Decision: Developer's choice")
    print("   - Casual games: May include childish terms")
    print("   - Competitive games: May exclude to avoid controversy")
    print()

    print("5. UNION vs INTERSECTION STRATEGY")
    print("-" * 80)
    print()
    print("  Example: 'tush' / 'tushie'")
    print()
    print("  Wiktionary labels:")
    print("    - tush (US):     childish, informal (buttocks)")
    print("    - tush (dialect): (tusk)")
    print("    - tush (British): informal (nonsense)")
    print()
    print("  UNION approach (include if ANY sense is appropriate):")
    print("    → INCLUDE 'tush' (has valid dialectal/British senses)")
    print()
    print("  INTERSECTION approach (exclude if ANY sense is problematic):")
    print("    → EXCLUDE 'tush' (has childish/informal sense for US audience)")
    print()
    print("  Recommendation: Use INTERSECTION for global games with US market")
    print("  Rationale: Avoids potential awkwardness even if word has other meanings")
    print()

    print("=" * 80)
    print("FILTER NOTES")
    print("=" * 80)
    print()
    print("  In the two-file pipeline format:")
    print("    - en-lexemes-enriched.jsonl: word-level properties")
    print("    - en-senses.jsonl: sense-level properties (register_tags, etc.)")
    print()
    print("  Use filters.py for programmatic filtering:")
    print("    uv run python -m openword.filters \\")
    print("      data/intermediate/en-lexemes-enriched.jsonl \\")
    print("      --senses data/intermediate/en-senses.jsonl \\")
    print("      --no-profanity --modern output.jsonl")
    print()
    print("=" * 80)
    print()


def main():
    """Main validation pipeline."""

    # Paths (flat structure with language-prefixed files)
    project_root = Path(__file__).parent.parent
    lexicon_path = project_root / "data" / "intermediate" / "en-lexemes-enriched.jsonl"

    logger.info("=" * 80)
    logger.info("Childish Terms Validation")
    logger.info("=" * 80)
    logger.info("")

    # Load data
    lexicon = load_lexicon(lexicon_path)

    logger.info("")

    # Analyze
    analysis = analyze_childish_terms(lexicon)

    # Report
    print_report(analysis)

    logger.info("Validation complete")


if __name__ == '__main__':
    main()
