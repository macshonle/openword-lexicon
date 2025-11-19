#!/usr/bin/env python3
"""
build_stats.py - Generate build statistics for the Advanced Word List Builder

Computes comprehensive statistics from unified entries and generates a JSON file
for the web-based word list builder to provide accurate estimates.
"""

import json
import datetime
from pathlib import Path
from typing import Dict
from collections import defaultdict


def compute_statistics(entries: Dict[str, dict]) -> dict:
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

    # Process each entry (entries is a dict, iterate over values)
    entries_list = entries.values() if isinstance(entries, dict) else entries
    for entry in entries_list:
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


def generate_and_write_statistics(entries: Dict[str, dict], output_path: Path) -> dict:
    """
    Generate statistics from entries and write to JSON file.

    Args:
        entries: Dictionary of word entries (word -> entry dict)
        output_path: Path to write JSON statistics file

    Returns:
        Statistics dictionary (same as what's written to file)
    """
    # Compute statistics
    stats = compute_statistics(entries)

    # Add timestamp
    stats['generated_at'] = datetime.datetime.now().isoformat()

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, sort_keys=False)

    return stats
