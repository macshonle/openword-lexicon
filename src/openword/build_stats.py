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
        'metadata_by_combination': {},
        'enrichment_impact': {},
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

    # Metadata by combination counters - nested dict[combo][metric]
    combo_metadata = defaultdict(lambda: {
        'total': 0,
        'with_pos': 0,
        'with_any_labels': 0,
        'with_register': 0,
        'with_domain': 0,
        'with_region': 0,
        'with_temporal': 0,
        'with_concreteness': 0,
        'with_frequency': 0,
        'multi_word': 0,
        'nouns': 0,
        'nouns_with_concrete': 0,
    })

    # Enrichment impact counters - nested dict[primary_combo][enrichment_source][metric]
    enrichment_impact = defaultdict(lambda: defaultdict(lambda: {
        'entries_with_source': 0,
        'entries_with_pos': 0,
        'entries_with_concreteness': 0,
        'entries_with_frequency': 0,
    }))

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

        # Separate primary sources from enrichment sources
        primary_sources = [s for s in sources if s in ('enable', 'eowl', 'wikt')]
        enrichment_sources = [s for s in sources if s in ('wordnet', 'brysbaert', 'frequency')]
        primary_key = ','.join(sorted(primary_sources)) if primary_sources else 'none'

        # POS tags
        pos_tags = entry.get('pos', [])
        has_pos = bool(pos_tags)
        if has_pos:
            with_pos += 1
            for pos in pos_tags:
                pos_counts[pos] += 1

        is_noun = 'noun' in pos_tags
        if is_noun:
            nouns += 1
            if entry.get('concreteness'):
                nouns_with_concrete += 1

        # Labels
        labels = entry.get('labels', {})
        has_any_labels = any(labels.values())
        has_register = bool(labels.get('register'))
        has_domain = bool(labels.get('domain'))
        has_region = bool(labels.get('region'))
        has_temporal = bool(labels.get('temporal'))

        if has_any_labels:
            with_any_labels += 1
        if has_register:
            with_register += 1
        if has_domain:
            with_domain += 1
        if has_region:
            with_region += 1
        if has_temporal:
            with_temporal += 1

        # Concreteness
        has_concreteness = bool(entry.get('concreteness'))
        if has_concreteness:
            with_concreteness += 1
            concrete_val = entry['concreteness']
            if concrete_val == 'concrete':
                concrete_counts['concrete'] += 1
            elif concrete_val == 'abstract':
                concrete_counts['abstract'] += 1
            elif concrete_val == 'mixed':
                concrete_counts['mixed'] += 1

        # Frequency
        has_frequency = bool(entry.get('frequency_tier'))
        if has_frequency:
            with_frequency += 1
            tier = entry['frequency_tier']
            freq_counts[tier] += 1

        # Multi-word phrases
        word_count = entry.get('word_count', 1)
        is_multi_word = word_count > 1
        if is_multi_word:
            multi_word += 1

        # ========================================================================
        # METADATA BY COMBINATION
        # Track metadata coverage for this specific source combination
        # ========================================================================
        combo_meta = combo_metadata[sources_key]
        combo_meta['total'] += 1
        if has_pos:
            combo_meta['with_pos'] += 1
        if has_any_labels:
            combo_meta['with_any_labels'] += 1
        if has_register:
            combo_meta['with_register'] += 1
        if has_domain:
            combo_meta['with_domain'] += 1
        if has_region:
            combo_meta['with_region'] += 1
        if has_temporal:
            combo_meta['with_temporal'] += 1
        if has_concreteness:
            combo_meta['with_concreteness'] += 1
        if has_frequency:
            combo_meta['with_frequency'] += 1
        if is_multi_word:
            combo_meta['multi_word'] += 1
        if is_noun:
            combo_meta['nouns'] += 1
            if has_concreteness:
                combo_meta['nouns_with_concrete'] += 1

        # ========================================================================
        # ENRICHMENT IMPACT
        # Track how enrichment sources contribute to primary source combinations
        # ========================================================================
        for enrich_src in enrichment_sources:
            impact = enrichment_impact[primary_key][enrich_src]
            impact['entries_with_source'] += 1

            # Track which metadata this enrichment source provided
            if enrich_src == 'wordnet':
                if has_pos:
                    impact['entries_with_pos'] += 1
                if has_concreteness:
                    impact['entries_with_concreteness'] += 1
            elif enrich_src == 'brysbaert':
                if has_concreteness:
                    impact['entries_with_concreteness'] += 1
            elif enrich_src == 'frequency':
                if has_frequency:
                    impact['entries_with_frequency'] += 1

    # Store source combinations
    stats['source_combinations'] = {
        k: v for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
    }

    # Store license combinations
    stats['license_combinations'] = {
        k: v for k, v in sorted(license_counts.items(), key=lambda x: -x[1])
    }

    # Metadata coverage (global stats)
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

    # ============================================================================
    # METADATA BY COMBINATION
    # Per-combination metadata coverage for accurate union calculations
    # ============================================================================
    stats['metadata_by_combination'] = {}
    for combo_key, combo_data in sorted(combo_metadata.items(), key=lambda x: -x[1]['total']):
        combo_total = combo_data['total']
        stats['metadata_by_combination'][combo_key] = {
            'total': combo_total,
            'pos_tags': {
                'count': combo_data['with_pos'],
                'percentage': round(100 * combo_data['with_pos'] / combo_total, 1) if combo_total > 0 else 0
            },
            'any_labels': {
                'count': combo_data['with_any_labels'],
                'percentage': round(100 * combo_data['with_any_labels'] / combo_total, 1) if combo_total > 0 else 0
            },
            'register_labels': {
                'count': combo_data['with_register'],
                'percentage': round(100 * combo_data['with_register'] / combo_total, 1) if combo_total > 0 else 0
            },
            'domain_labels': {
                'count': combo_data['with_domain'],
                'percentage': round(100 * combo_data['with_domain'] / combo_total, 1) if combo_total > 0 else 0
            },
            'region_labels': {
                'count': combo_data['with_region'],
                'percentage': round(100 * combo_data['with_region'] / combo_total, 1) if combo_total > 0 else 0
            },
            'temporal_labels': {
                'count': combo_data['with_temporal'],
                'percentage': round(100 * combo_data['with_temporal'] / combo_total, 1) if combo_total > 0 else 0
            },
            'concreteness': {
                'count': combo_data['with_concreteness'],
                'percentage': round(100 * combo_data['with_concreteness'] / combo_total, 1) if combo_total > 0 else 0
            },
            'concreteness_nouns': {
                'count': combo_data['nouns_with_concrete'],
                'total_nouns': combo_data['nouns'],
                'percentage': round(100 * combo_data['nouns_with_concrete'] / combo_data['nouns'], 1) if combo_data['nouns'] > 0 else 0
            },
            'frequency_tier': {
                'count': combo_data['with_frequency'],
                'percentage': round(100 * combo_data['with_frequency'] / combo_total, 1) if combo_total > 0 else 0
            },
            'multi_word_phrases': {
                'count': combo_data['multi_word'],
                'percentage': round(100 * combo_data['multi_word'] / combo_total, 1) if combo_total > 0 else 0
            }
        }

    # ============================================================================
    # ENRICHMENT IMPACT
    # Shows how enrichment sources (wordnet, brysbaert, frequency) contribute
    # to each primary source combination
    # ============================================================================
    stats['enrichment_impact'] = {}
    for primary_key, enrichments in sorted(enrichment_impact.items()):
        stats['enrichment_impact'][primary_key] = {}
        for enrich_src, impact_data in sorted(enrichments.items()):
            total_entries = impact_data['entries_with_source']
            stats['enrichment_impact'][primary_key][enrich_src] = {
                'entries_with_source': total_entries,
                'entries_with_pos': impact_data['entries_with_pos'],
                'entries_with_concreteness': impact_data['entries_with_concreteness'],
                'entries_with_frequency': impact_data['entries_with_frequency'],
                'pos_percentage': round(100 * impact_data['entries_with_pos'] / total_entries, 1) if total_entries > 0 else 0,
                'concreteness_percentage': round(100 * impact_data['entries_with_concreteness'] / total_entries, 1) if total_entries > 0 else 0,
                'frequency_percentage': round(100 * impact_data['entries_with_frequency'] / total_entries, 1) if total_entries > 0 else 0,
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
