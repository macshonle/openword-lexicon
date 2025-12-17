#!/usr/bin/env python3
"""
validate_profanity_coverage.py — Validate lexicon's profanity labeling

⚠️  WARNING: Contains analysis of offensive and explicit content ⚠️

Purpose:
  Compare our lexicon's vulgar/offensive/derogatory labels against
  external profanity lists to identify gaps and validate coverage.

Sources:
  - censor-text/profanity-list: Clean, maintained list
  - dsojevic/profanity-list: Severity ratings + metadata (JSON)

Usage:
  python tools/validate_profanity_coverage.py

Output:
  - Validation report showing:
    * Words in profanity lists but NOT labeled in our lexicon (gaps)
    * Words labeled vulgar/offensive in our lexicon (for review)
    * Coverage statistics by severity level
    * Recommendations for label improvements
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

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


def load_censor_text_list(file_path: Path) -> Set[str]:
    """Load censor-text profanity list (plain text)."""
    if not file_path.exists():
        logger.warning(f"censor-text list not found: {file_path}")
        logger.warning("Run 'bash scripts/fetch/fetch_profanity_lists.sh' to download")
        return set()

    logger.info(f"Loading censor-text list from {file_path}")

    profanity_words = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip().lower()
            if word and not word.startswith('#'):
                profanity_words.add(word)

    logger.info(f"  Loaded {len(profanity_words):,} profanity terms")
    return profanity_words


def load_dsojevic_list(file_path: Path) -> Dict[str, dict]:
    """Load dsojevic profanity list (JSON with severity).

    Format: Array of objects with 'id', 'match', 'severity', 'tags'.
    - 'id': Unique identifier (use as word)
    - 'match': Pattern with pipes for alternatives (e.g., "word|alternate")
    - 'severity': 1-4 (Mild, Medium, Strong, Severe)
    - 'tags': Categories like "general", "sexual", "racial"
    """
    if not file_path.exists():
        logger.warning(f"dsojevic list not found: {file_path}")
        logger.warning("Run 'bash scripts/fetch/fetch_profanity_lists.sh' to download")
        return {}

    logger.info(f"Loading dsojevic list from {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert to dict keyed by word
    profanity_dict = {}

    # Handle array format
    if isinstance(data, list):
        for entry in data:
            # Use 'id' as the primary word identifier
            word_id = entry.get('id', '').lower()
            if not word_id:
                continue

            # Map severity numbers to labels
            severity_map = {1: 'mild', 2: 'medium', 3: 'strong', 4: 'severe'}
            severity_num = entry.get('severity', 0)
            severity = severity_map.get(severity_num, 'unknown')

            profanity_dict[word_id] = {
                'severity': severity,
                'categories': entry.get('tags', []),
            }

            # Also add any alternatives from 'match' field
            match = entry.get('match', '')
            if match and '|' in match:
                # Split on pipe to get alternatives
                alternatives = [alt.strip().lower() for alt in match.split('|')]
                for alt in alternatives:
                    if alt and alt not in profanity_dict:
                        profanity_dict[alt] = {
                            'severity': severity,
                            'categories': entry.get('tags', []),
                        }

    logger.info(f"  Loaded {len(profanity_dict):,} profanity terms with metadata")
    return profanity_dict


def get_labeled_words(lexicon: Dict[str, dict], labels: List[str]) -> Dict[str, dict]:
    """Get words from lexicon that have specific register labels."""
    labeled = {}

    for word, entry in lexicon.items():
        register_labels = entry.get('labels', {}).get('register', [])
        if any(label in register_labels for label in labels):
            labeled[word] = {
                'labels': register_labels,
                'pos': entry.get('pos', []),
                'sources': entry.get('sources', []),
            }

    return labeled


def analyze_coverage(
    lexicon: Dict[str, dict],
    censor_text: Set[str],
    dsojevic: Dict[str, dict]
) -> dict:
    """Analyze profanity labeling coverage."""

    # Get words labeled as vulgar/offensive/derogatory in our lexicon
    our_labeled = get_labeled_words(lexicon, ['vulgar', 'offensive', 'derogatory'])

    # Combine external profanity lists
    external_profanity = censor_text | set(dsojevic.keys())

    # Find gaps: words in external lists but NOT labeled in our lexicon
    gaps = []
    for word in external_profanity:
        if word in lexicon:
            entry = lexicon[word]
            register_labels = entry.get('labels', {}).get('register', [])

            # Check if it has any offensive labels
            has_offensive_label = any(
                label in register_labels
                for label in ['vulgar', 'offensive', 'derogatory']
            )

            if not has_offensive_label:
                severity = dsojevic.get(word, {}).get('severity', 'unknown')
                gaps.append({
                    'word': word,
                    'severity': severity,
                    'current_labels': register_labels,
                    'pos': entry.get('pos', []),
                    'sources': entry.get('sources', []),
                })
        else:
            # Word not in lexicon at all
            severity = dsojevic.get(word, {}).get('severity', 'unknown')
            gaps.append({
                'word': word,
                'severity': severity,
                'current_labels': [],
                'pos': [],
                'sources': [],
                'in_lexicon': False,
            })

    # Severity breakdown for gaps
    severity_counts = Counter(gap['severity'] for gap in gaps)

    # Words we label but aren't in external lists (potential false positives or regional differences)
    our_only = {
        word: info for word, info in our_labeled.items()
        if word not in external_profanity
    }

    return {
        'our_labeled_count': len(our_labeled),
        'external_count': len(external_profanity),
        'gaps': gaps,
        'gaps_count': len(gaps),
        'severity_counts': severity_counts,
        'our_only': our_only,
        'our_only_count': len(our_only),
        'coverage_pct': 100 * (1 - len([g for g in gaps if g.get('in_lexicon', True)]) / max(len(external_profanity), 1)),
    }


def print_report(analysis: dict):
    """Print validation report."""

    print()
    print("=" * 80)
    print("⚠️  PROFANITY COVERAGE VALIDATION REPORT  ⚠️")
    print("=" * 80)
    print()

    print("SUMMARY")
    print("-" * 80)
    print(f"  Words labeled vulgar/offensive/derogatory in our lexicon: {analysis['our_labeled_count']:,}")
    print(f"  Words in external profanity lists:                        {analysis['external_count']:,}")
    print(f"  Coverage (words in lexicon with labels):                  {analysis['coverage_pct']:.1f}%")
    print()

    print("GAPS (in external lists but NOT labeled in our lexicon)")
    print("-" * 80)
    print(f"  Total gaps: {analysis['gaps_count']:,}")
    print()

    if analysis['severity_counts']:
        print("  By severity:")
        for severity, count in analysis['severity_counts'].most_common():
            print(f"    {severity:15} {count:6,}")
        print()

    # Show sample gaps
    if analysis['gaps']:
        print("  Sample gaps (first 20):")
        for gap in analysis['gaps'][:20]:
            word = gap['word']
            severity = gap['severity']
            in_lex = gap.get('in_lexicon', True)

            if in_lex:
                labels = gap['current_labels'] or ['(no labels)']
                print(f"    {word:20} severity={severity:8} current_labels={labels}")
            else:
                print(f"    {word:20} severity={severity:8} (NOT IN LEXICON)")

        if len(analysis['gaps']) > 20:
            print(f"    ... and {len(analysis['gaps']) - 20:,} more")
        print()

    print("WORDS WE LABEL (but not in external lists)")
    print("-" * 80)
    print(f"  Total: {analysis['our_only_count']:,}")
    print()
    print("  These may be:")
    print("    - Regional variations (e.g., British vs American)")
    print("    - Context-dependent terms (offensive in some contexts)")
    print("    - Wiktionary editors' judgment calls")
    print("    - False positives (over-labeling)")
    print()

    if analysis['our_only']:
        print("  Sample (first 15):")
        for word, info in list(analysis['our_only'].items())[:15]:
            labels = info['labels']
            print(f"    {word:20} labels={labels}")

        if len(analysis['our_only']) > 15:
            print(f"    ... and {len(analysis['our_only']) - 15:,} more")
        print()

    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    if analysis['gaps_count'] > 0:
        print("  1. Review gaps to determine if Wiktionary should add labels")
        print("  2. Focus on high-severity terms first")
        print("  3. Consider that some terms may be context-dependent")
        print("  4. External lists may include regional slang not in formal dictionaries")
    else:
        print("  ✓ No significant gaps found!")
    print()

    if analysis['our_only_count'] > 100:
        print("  5. Review 'our only' list for potential over-labeling")
        print("  6. Consider regional/cultural differences in offensiveness")
    print()

    print("=" * 80)


def main():
    """Main validation pipeline."""

    # Paths (flat structure with language-prefixed files)
    project_root = Path(__file__).parent.parent
    lexicon_path = project_root / "data" / "intermediate" / "en-lexemes-enriched.jsonl"
    profanity_dir = project_root / "data" / "raw" / "validation" / "profanity"
    censor_text_path = profanity_dir / "censor-text-profanity-list.txt"
    dsojevic_path = profanity_dir / "dsojevic-profanity-list.json"

    logger.info("=" * 80)
    logger.info("Profanity Coverage Validation")
    logger.info("=" * 80)
    logger.info("")

    # Load data
    lexicon = load_lexicon(lexicon_path)
    censor_text = load_censor_text_list(censor_text_path)
    dsojevic = load_dsojevic_list(dsojevic_path)

    if not censor_text and not dsojevic:
        logger.error("No profanity lists found!")
        logger.error("Run: bash scripts/fetch/fetch_profanity_lists.sh")
        sys.exit(1)

    logger.info("")

    # Analyze
    analysis = analyze_coverage(lexicon, censor_text, dsojevic)

    # Report
    print_report(analysis)

    logger.info("Validation complete")


if __name__ == '__main__':
    main()
