#!/usr/bin/env python3
"""
generate_build_stats.py - Generate build statistics for the Advanced Word List Builder

Reads the unified merged entries and generates a comprehensive statistics JSON file
that can be used by the web-based word list builder to provide accurate estimates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_entries(filepath: Path) -> List[dict]:
    """Load entries from JSONL file."""
    entries = []

    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        return entries

    logger.info(f"Loading {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    logger.info(f"Loaded {len(entries):,} entries")
    return entries


def compute_statistics(entries: List[dict]) -> dict:
    """Compute comprehensive statistics from entries."""
    stats = {
        'total_words': len(entries),
        'generated_at': None,  # Will be set when writing
        'sources': {},
        'source_combinations': {},
        'license_combinations': {},
        'metadata_coverage': {},
        'pos_distribution': {},
        'frequency_distribution': {},
        'concreteness_distribution': {},
        'label_categories': {},
    }

    # Initialize counters
    source_counts = defaultdict(int)
    license_counts = defaultdict(int)
    pos_counts = defaultdict(int)
    freq_counts = defaultdict(int)
    concrete_counts = defaultdict(int)

    # Coverage counters
    with_pos = 0
    with_any_labels = 0
    with_register = 0
    with_domain = 0
    with_region = 0
    with_temporal = 0
    with_concreteness = 0
    with_frequency = 0
    multi_word = 0
    nouns = 0
    nouns_with_concrete = 0

    # Process each entry
    for entry in entries:
        # Source combinations
        sources = entry.get('sources', [])
        sources_key = ','.join(sorted(sources))
        source_counts[sources_key] += 1

        # Individual source tracking
        for source in sources:
            if source not in stats['sources']:
                stats['sources'][source] = 0
            stats['sources'][source] += 1

        # License combinations
        licenses = entry.get('license_sources', {})
        licenses_key = ','.join(sorted(licenses.keys()))
        license_counts[licenses_key] += 1

        # POS tags
        pos_tags = entry.get('pos', [])
        if pos_tags:
            with_pos += 1
            for pos in pos_tags:
                pos_counts[pos] += 1

        if 'noun' in pos_tags:
            nouns += 1
            if entry.get('concreteness'):
                nouns_with_concrete += 1

        # Labels
        labels = entry.get('labels', {})
        if any(labels.values()):
            with_any_labels += 1

        if labels.get('register'):
            with_register += 1
        if labels.get('domain'):
            with_domain += 1
        if labels.get('region'):
            with_region += 1
        if labels.get('temporal'):
            with_temporal += 1

        # Concreteness
        if entry.get('concreteness'):
            with_concreteness += 1
            concrete_val = entry['concreteness']
            if concrete_val == 'concrete':
                concrete_counts['concrete'] += 1
            elif concrete_val == 'abstract':
                concrete_counts['abstract'] += 1
            elif concrete_val == 'mixed':
                concrete_counts['mixed'] += 1

        # Frequency
        if entry.get('frequency_tier'):
            with_frequency += 1
            tier = entry['frequency_tier']
            freq_counts[tier] += 1

        # Multi-word phrases
        word_count = entry.get('word_count', 1)
        if word_count > 1:
            multi_word += 1

    # Store source combinations
    stats['source_combinations'] = {
        k: v for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
    }

    # Store license combinations
    stats['license_combinations'] = {
        k: v for k, v in sorted(license_counts.items(), key=lambda x: -x[1])
    }

    # Metadata coverage
    total = stats['total_words']
    stats['metadata_coverage'] = {
        'pos_tags': {
            'count': with_pos,
            'percentage': round(100 * with_pos / total, 1) if total > 0 else 0
        },
        'any_labels': {
            'count': with_any_labels,
            'percentage': round(100 * with_any_labels / total, 1) if total > 0 else 0
        },
        'register_labels': {
            'count': with_register,
            'percentage': round(100 * with_register / total, 1) if total > 0 else 0
        },
        'domain_labels': {
            'count': with_domain,
            'percentage': round(100 * with_domain / total, 1) if total > 0 else 0
        },
        'region_labels': {
            'count': with_region,
            'percentage': round(100 * with_region / total, 1) if total > 0 else 0
        },
        'temporal_labels': {
            'count': with_temporal,
            'percentage': round(100 * with_temporal / total, 1) if total > 0 else 0
        },
        'concreteness': {
            'count': with_concreteness,
            'percentage': round(100 * with_concreteness / total, 1) if total > 0 else 0
        },
        'concreteness_nouns': {
            'count': nouns_with_concrete,
            'total_nouns': nouns,
            'percentage': round(100 * nouns_with_concrete / nouns, 1) if nouns > 0 else 0
        },
        'frequency_tier': {
            'count': with_frequency,
            'percentage': round(100 * with_frequency / total, 1) if total > 0 else 0
        },
        'multi_word_phrases': {
            'count': multi_word,
            'percentage': round(100 * multi_word / total, 1) if total > 0 else 0
        }
    }

    # POS distribution (top 10)
    stats['pos_distribution'] = dict(
        sorted(pos_counts.items(), key=lambda x: -x[1])[:10]
    )

    # Frequency distribution
    stats['frequency_distribution'] = dict(
        sorted(freq_counts.items())
    )

    # Concreteness distribution
    stats['concreteness_distribution'] = dict(concrete_counts)

    return stats


def write_statistics(stats: dict, output_path: Path):
    """Write statistics to JSON file."""
    import datetime

    # Add timestamp
    stats['generated_at'] = datetime.datetime.now().isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, sort_keys=False)

    logger.info(f"Statistics written to: {output_path}")


def print_summary(stats: dict):
    """Print a summary of the statistics."""
    logger.info("")
    logger.info("=== Build Statistics Summary ===")
    logger.info(f"Total unique words: {stats['total_words']:,}")
    logger.info("")

    logger.info("Source distribution:")
    for source_combo, count in list(stats['source_combinations'].items())[:7]:
        logger.info(f"  {source_combo}: {count:,} words")
    logger.info("")

    logger.info("License requirements:")
    for license_combo, count in list(stats['license_combinations'].items())[:7]:
        logger.info(f"  {license_combo}: {count:,} words")
    logger.info("")

    logger.info("Metadata coverage:")
    mc = stats['metadata_coverage']
    logger.info(f"  POS tags: {mc['pos_tags']['count']:,} ({mc['pos_tags']['percentage']}%)")
    logger.info(f"  Any labels: {mc['any_labels']['count']:,} ({mc['any_labels']['percentage']}%)")
    logger.info(f"    Register: {mc['register_labels']['count']:,} ({mc['register_labels']['percentage']}%)")
    logger.info(f"    Domain: {mc['domain_labels']['count']:,} ({mc['domain_labels']['percentage']}%)")
    logger.info(f"    Region: {mc['region_labels']['count']:,} ({mc['region_labels']['percentage']}%)")
    logger.info(f"    Temporal: {mc['temporal_labels']['count']:,} ({mc['temporal_labels']['percentage']}%)")
    logger.info(f"  Concreteness (nouns): {mc['concreteness_nouns']['count']:,}/{mc['concreteness_nouns']['total_nouns']:,} ({mc['concreteness_nouns']['percentage']}%)")
    logger.info(f"  Frequency tier: {mc['frequency_tier']['count']:,} ({mc['frequency_tier']['percentage']}%)")
    logger.info(f"  Multi-word phrases: {mc['multi_word_phrases']['count']:,} ({mc['multi_word_phrases']['percentage']}%)")


def main():
    """Main entry point."""
    # Find the merged entries file
    project_root = Path(__file__).parent.parent
    merged_file = project_root / "data" / "intermediate" / "en" / "entries_merged.jsonl"

    if not merged_file.exists():
        logger.error(f"Merged entries file not found: {merged_file}")
        logger.error("Please run 'make build-en' first to generate the merged data")
        return 1

    # Load entries
    entries = load_entries(merged_file)
    if not entries:
        logger.error("No entries loaded")
        return 1

    # Compute statistics
    logger.info("Computing statistics...")
    stats = compute_statistics(entries)

    # Write to file
    output_file = project_root / "tools" / "wordlist-builder" / "build-statistics.json"
    write_statistics(stats, output_file)

    # Print summary
    print_summary(stats)

    logger.info("")
    logger.info("=== Statistics generation complete ===")
    logger.info(f"JSON file: {output_file}")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
