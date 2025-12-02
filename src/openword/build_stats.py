#!/usr/bin/env python3
"""
build_stats.py - Generate build statistics for the Advanced Word List Builder

Computes comprehensive statistics from lexeme entries and generates a JSON file
for the web-based word list builder to provide accurate estimates.

Supports both:
  - Two-file format: en-lexeme-enriched.jsonl + en-senses.jsonl (current pipeline)
  - Single-file format: entries with sources/labels/pos (owlex format)
"""

import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


def detect_format(entries: Dict[str, dict]) -> str:
    """Detect whether entries are in two-file lexeme format or single-file format."""
    sample = next(iter(entries.values())) if entries else {}
    # Two-file format has sense_offset/sense_length, single-file has sources/labels
    if 'sense_offset' in sample or 'sense_length' in sample:
        return 'lexeme'
    return 'single_file'


def load_senses_by_word(senses_path: Path) -> Dict[str, List[dict]]:
    """
    Load senses from JSONL file and group by word.

    Returns:
        Dictionary mapping word -> list of sense entries
    """
    senses_by_word: Dict[str, List[dict]] = defaultdict(list)

    with open(senses_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                sense = json.loads(line)
                word = sense.get('word')
                if word:
                    senses_by_word[word].append(sense)
            except json.JSONDecodeError:
                continue

    return dict(senses_by_word)


def aggregate_sense_stats(senses: List[dict]) -> dict:
    """
    Aggregate statistics from multiple senses for a single word.

    Returns dict with:
        - pos: list of unique POS tags
        - has_register: bool
        - has_domain: bool
        - has_region: bool
        - has_temporal: bool
        - register_tags: list of all register tags
        - domain_tags: list of all domain tags
        - region_tags: list of all region tags
        - temporal_tags: list of all temporal tags
    """
    pos_set = set()
    register_tags = []
    domain_tags = []
    region_tags = []
    temporal_tags = []

    for sense in senses:
        # POS
        pos = sense.get('pos')
        if pos:
            pos_set.add(pos)

        # Tags - aggregate all
        register_tags.extend(sense.get('register_tags', []))
        domain_tags.extend(sense.get('domain_tags', []))
        region_tags.extend(sense.get('region_tags', []))
        temporal_tags.extend(sense.get('temporal_tags', []))

    return {
        'pos': list(pos_set),
        'has_register': len(register_tags) > 0,
        'has_domain': len(domain_tags) > 0,
        'has_region': len(region_tags) > 0,
        'has_temporal': len(temporal_tags) > 0,
        'register_tags': register_tags,
        'domain_tags': domain_tags,
        'region_tags': region_tags,
        'temporal_tags': temporal_tags,
    }


def compute_statistics_lexeme(entries: Dict[str, dict], senses_by_word: Optional[Dict[str, List[dict]]] = None) -> dict:
    """Compute statistics from two-file lexeme format with multi-source support.

    Args:
        entries: Dictionary of lexeme entries (word -> entry dict)
        senses_by_word: Optional dictionary of senses grouped by word (from senses file)
    """
    stats = {
        'total_words': len(entries),
        'generated_at': None,
        'sources': {},  # Per-source word counts
        'source_combinations': {},  # Combination counts with licenses
        'metadata_coverage': {},
        'metadata_by_source': {},  # Metadata coverage broken down by source
        'enrichment_impact': {},
        'pos_distribution': {},
        'frequency_distribution': {},
        'concreteness_distribution': {},
        'label_categories': {},
    }

    freq_counts = defaultdict(int)
    concrete_counts = defaultdict(int)
    source_counts = defaultdict(int)
    source_combo_counts = defaultdict(lambda: {'count': 0, 'licenses': set()})
    pos_counts = defaultdict(int)

    # Per-source metadata tracking
    source_metadata = defaultdict(lambda: {
        'total': 0,
        'with_concreteness': 0,
        'with_frequency': 0,
        'with_syllables': 0,
        'with_senses': 0,
        'with_pos': 0,
        'with_labels': 0,
    })

    with_syllables = 0
    with_concreteness = 0
    with_frequency = 0
    multi_word = 0
    total_senses = 0

    # Sense-level counters (from senses file)
    with_pos = 0
    with_any_labels = 0
    with_register = 0
    with_domain = 0
    with_region = 0
    with_temporal = 0
    label_category_counts = {
        'register': defaultdict(int),
        'domain': defaultdict(int),
        'region': defaultdict(int),
        'temporal': defaultdict(int),
    }

    entries_list = entries.values() if isinstance(entries, dict) else entries
    for entry in entries_list:
        word = entry.get('word', '')
        # Source tracking
        sources = entry.get('sources', ['wikt'])  # Default to wikt for backwards compat
        sources_key = ','.join(sorted(sources))
        license_sources = entry.get('license_sources', {})

        # Count individual sources
        for src in sources:
            source_counts[src] += 1
            source_metadata[src]['total'] += 1

        # Count source combinations
        combo = source_combo_counts[sources_key]
        combo['count'] += 1
        for lic in license_sources.keys():
            combo['licenses'].add(lic)

        # Syllables
        if entry.get('syllables') is not None:
            with_syllables += 1
            for src in sources:
                source_metadata[src]['with_syllables'] += 1

        # Concreteness
        if entry.get('concreteness'):
            with_concreteness += 1
            concrete_val = entry['concreteness']
            concrete_counts[concrete_val] += 1
            for src in sources:
                source_metadata[src]['with_concreteness'] += 1

        # Frequency
        if entry.get('frequency_tier'):
            with_frequency += 1
            freq_counts[entry['frequency_tier']] += 1
            for src in sources:
                source_metadata[src]['with_frequency'] += 1

        # Multi-word
        if entry.get('word_count', 1) > 1:
            multi_word += 1

        # Sense count
        sense_count = entry.get('sense_count', entry.get('sense_length', 0))
        total_senses += sense_count
        if sense_count > 0:
            for src in sources:
                source_metadata[src]['with_senses'] += 1

        # Process sense-level data if available
        if senses_by_word and word in senses_by_word:
            word_senses = senses_by_word[word]
            sense_stats = aggregate_sense_stats(word_senses)

            # POS
            if sense_stats['pos']:
                with_pos += 1
                for pos in sense_stats['pos']:
                    pos_counts[pos] += 1
                for src in sources:
                    source_metadata[src]['with_pos'] += 1

            # Labels
            has_labels = (sense_stats['has_register'] or sense_stats['has_domain'] or
                         sense_stats['has_region'] or sense_stats['has_temporal'])
            if has_labels:
                with_any_labels += 1
                for src in sources:
                    source_metadata[src]['with_labels'] += 1

            if sense_stats['has_register']:
                with_register += 1
                for tag in sense_stats['register_tags']:
                    label_category_counts['register'][tag] += 1

            if sense_stats['has_domain']:
                with_domain += 1
                for tag in sense_stats['domain_tags']:
                    label_category_counts['domain'][tag] += 1

            if sense_stats['has_region']:
                with_region += 1
                for tag in sense_stats['region_tags']:
                    label_category_counts['region'][tag] += 1

            if sense_stats['has_temporal']:
                with_temporal += 1
                for tag in sense_stats['temporal_tags']:
                    label_category_counts['temporal'][tag] += 1

    total = stats['total_words']

    # Convert source counts
    stats['sources'] = dict(sorted(source_counts.items(), key=lambda x: -x[1]))

    # Convert source combinations (convert license sets to sorted strings)
    for combo_key, combo_data in source_combo_counts.items():
        stats['source_combinations'][combo_key] = {
            'count': combo_data['count'],
            'licenses': ','.join(sorted(combo_data['licenses']))
        }
    # Sort by count descending
    stats['source_combinations'] = dict(
        sorted(stats['source_combinations'].items(), key=lambda x: -x[1]['count'])
    )

    # Per-source metadata coverage
    for src, meta in source_metadata.items():
        src_total = meta['total']
        stats['metadata_by_source'][src] = {
            'total': src_total,
            'concreteness': {
                'count': meta['with_concreteness'],
                'percentage': round(100 * meta['with_concreteness'] / src_total, 1) if src_total > 0 else 0
            },
            'frequency_tier': {
                'count': meta['with_frequency'],
                'percentage': round(100 * meta['with_frequency'] / src_total, 1) if src_total > 0 else 0
            },
            'syllables': {
                'count': meta['with_syllables'],
                'percentage': round(100 * meta['with_syllables'] / src_total, 1) if src_total > 0 else 0
            },
            'senses': {
                'count': meta['with_senses'],
                'percentage': round(100 * meta['with_senses'] / src_total, 1) if src_total > 0 else 0
            },
            'pos_tags': {
                'count': meta['with_pos'],
                'percentage': round(100 * meta['with_pos'] / src_total, 1) if src_total > 0 else 0
            },
            'any_labels': {
                'count': meta['with_labels'],
                'percentage': round(100 * meta['with_labels'] / src_total, 1) if src_total > 0 else 0
            },
        }

    stats['metadata_coverage'] = {
        'syllables': {
            'count': with_syllables,
            'percentage': round(100 * with_syllables / total, 1) if total > 0 else 0
        },
        'concreteness': {
            'count': with_concreteness,
            'percentage': round(100 * with_concreteness / total, 1) if total > 0 else 0
        },
        'frequency_tier': {
            'count': with_frequency,
            'percentage': round(100 * with_frequency / total, 1) if total > 0 else 0
        },
        'multi_word_phrases': {
            'count': multi_word,
            'percentage': round(100 * multi_word / total, 1) if total > 0 else 0
        },
        'total_senses': {
            'count': total_senses,
            'avg_per_word': round(total_senses / total, 2) if total > 0 else 0
        },
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
    }

    # POS distribution (all POS tags, sorted by count)
    stats['pos_distribution'] = dict(
        sorted(pos_counts.items(), key=lambda x: -x[1])
    )

    stats['frequency_distribution'] = dict(sorted(freq_counts.items()))
    stats['concreteness_distribution'] = dict(concrete_counts)

    # Label categories (top 15 per category to capture most labels)
    stats['label_categories'] = {
        category: dict(sorted(counts.items(), key=lambda x: -x[1])[:15])
        for category, counts in label_category_counts.items()
    }

    return stats


def compute_statistics(entries: Dict[str, dict], senses_by_word: Optional[Dict[str, List[dict]]] = None) -> dict:
    """Compute comprehensive statistics from entries (auto-detects format).

    Args:
        entries: Dictionary of word entries (word -> entry dict)
        senses_by_word: Optional dictionary of senses grouped by word (for two-file format)
    """
    # Detect format and dispatch
    fmt = detect_format(entries)
    if fmt == 'lexeme':
        return compute_statistics_lexeme(entries, senses_by_word)

    # Single-file format processing below
    stats = {
        'total_words': len(entries),
        'generated_at': None,  # Will be set when writing
        'sources': {},
        'source_combinations': {},
        'metadata_coverage': {},
        'metadata_by_combination': {},
        'enrichment_impact': {},
        'pos_distribution': {},
        'frequency_distribution': {},
        'concreteness_distribution': {},
        'label_categories': {},
    }

    # Initialize counters
    # Store both count and licenses for each source combination
    source_combo_data = defaultdict(lambda: {'count': 0, 'licenses': None})
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
        # Source combinations with licenses
        sources = entry.get('sources', [])
        sources_key = ','.join(sorted(sources))

        # Get licenses for this combination
        licenses = entry.get('license_sources', {})
        licenses_key = ','.join(sorted(licenses.keys()))

        # Store combined data
        combo_data = source_combo_data[sources_key]
        combo_data['count'] += 1
        combo_data['licenses'] = licenses_key

        # Individual source tracking
        for source in sources:
            if source not in stats['sources']:
                stats['sources'][source] = 0
            stats['sources'][source] += 1

        # Separate primary sources from enrichment sources
        # Note: 'enable' is validation-only, not a primary source
        primary_sources = [s for s in sources if s in ('eowl', 'wikt')]
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

    # Store source combinations with licenses (sorted by count descending)
    stats['source_combinations'] = {
        k: v for k, v in sorted(
            source_combo_data.items(),
            key=lambda x: -x[1]['count']
        )
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

    # POS distribution (all POS tags, sorted by count)
    stats['pos_distribution'] = dict(
        sorted(pos_counts.items(), key=lambda x: -x[1])
    )

    # Frequency distribution
    stats['frequency_distribution'] = dict(
        sorted(freq_counts.items())
    )

    # Concreteness distribution
    stats['concreteness_distribution'] = dict(concrete_counts)

    return stats


def generate_and_write_statistics(
    entries: Dict[str, dict],
    output_path: Path,
    senses_by_word: Optional[Dict[str, List[dict]]] = None
) -> dict:
    """
    Generate statistics from entries and write to JSON file.

    Args:
        entries: Dictionary of word entries (word -> entry dict)
        output_path: Path to write JSON statistics file
        senses_by_word: Optional dictionary of senses grouped by word (for two-file format)

    Returns:
        Statistics dictionary (same as what's written to file)
    """
    # Compute statistics
    stats = compute_statistics(entries, senses_by_word)

    # Add timestamp
    stats['generated_at'] = datetime.datetime.now().isoformat()

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, sort_keys=False)

    return stats
