#!/usr/bin/env python3
"""
generate_statistics.py - Generate build statistics for the Advanced Word List Builder

This script reads the final enriched entries file and generates comprehensive
statistics in build-statistics.json for the web-based word list builder.

This must run AFTER all enrichment steps (wordnet, brysbaert, frequency) to
ensure accurate metadata counts.

Usage:
    python src/openword/generate_statistics.py [--lang LANG]

Options:
    --lang LANG     Language code (default: en)
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Dict

from openword import build_stats

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_entries_from_jsonl(input_path: Path) -> Dict[str, dict]:
    """Load entries from JSONL file into a dictionary."""
    logger.info(f"Loading entries from {input_path}")
    entries = {}

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                word = entry.get('word')
                if word:
                    entries[word] = entry
            except json.JSONDecodeError as e:
                logger.warning(f"  Line {line_num}: Invalid JSON - {e}")
                continue

    logger.info(f"  Loaded {len(entries):,} entries")
    return entries


def main():
    """Generate build statistics from final enriched entries."""
    parser = argparse.ArgumentParser(description='Generate build statistics for word list builder')
    parser.add_argument('--lang', default='en', help='Language code (default: en)')
    parser.add_argument('--input', type=Path, help='Input JSONL file (overrides default path)')
    args = parser.parse_args()

    # Determine paths
    project_root = Path(__file__).parent.parent.parent
    lang_dir = project_root / "data" / "intermediate" / args.lang
    output_file = project_root / "tools" / "wordlist-builder" / "build-statistics.json"

    # Determine input file
    if args.input:
        input_file = args.input
    else:
        # Current pipeline output (two-file format)
        input_file = lang_dir / f"{args.lang}-lexeme-enriched.jsonl"

        if not input_file.exists():
            logger.error(f"No input file found: {input_file}")
            logger.error("Make sure to run the full build pipeline first:")
            logger.error("  make build-en")
            return 1

    # Verify input file exists
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        logger.error("Make sure to run the full build pipeline first:")
        logger.error("  make build-en")
        return 1

    logger.info("")
    logger.info("=" * 80)
    logger.info("GENERATING BUILD STATISTICS")
    logger.info("=" * 80)
    logger.info(f"  Input:  {input_file}")
    logger.info(f"  Output: {output_file}")
    logger.info("")

    # Load entries from final enriched file
    entries = load_entries_from_jsonl(input_file)

    if not entries:
        logger.error("No entries loaded - cannot generate statistics")
        return 1

    # Generate and write statistics
    logger.info("")
    logger.info("Computing statistics...")
    stats = build_stats.generate_and_write_statistics(entries, output_file)

    # Report summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("STATISTICS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"  Total words: {stats['total_words']:,}")

    meta = stats.get('metadata_coverage', {})
    if meta:
        logger.info("")
        logger.info("Metadata coverage:")
        logger.info(f"  POS tags:        {meta.get('pos_tags', {}).get('count', 0):,} ({meta.get('pos_tags', {}).get('percentage', 0)}%)")
        logger.info(f"  Any labels:      {meta.get('any_labels', {}).get('count', 0):,} ({meta.get('any_labels', {}).get('percentage', 0)}%)")
        logger.info(f"  Concreteness:    {meta.get('concreteness', {}).get('count', 0):,} ({meta.get('concreteness', {}).get('percentage', 0)}%)")
        logger.info(f"  Frequency tiers: {meta.get('frequency_tier', {}).get('count', 0):,} ({meta.get('frequency_tier', {}).get('percentage', 0)}%)")

    logger.info("")
    logger.info(f"Statistics written to: {output_file}")
    logger.info("")

    return 0


if __name__ == '__main__':
    exit(main())
