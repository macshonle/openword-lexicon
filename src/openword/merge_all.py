#!/usr/bin/env python3
"""
merge_all.py — Unified merge of all sources (ENABLE + EOWL + Wiktionary).

Reads:
  - data/intermediate/core/core_entries.jsonl
  - data/intermediate/plus/wikt_entries.jsonl

Outputs:
  - data/intermediate/unified/entries_merged.jsonl

Merge logic:
  - Union POS tags
  - Union all label categories
  - Union sources
  - Compute license_sources from sources
  - Prefer non-null values for lemma, concreteness, frequency_tier
  - Keep is_phrase if any source has it as true

License tracking:
  - Automatically compute license requirements from sources
  - Enable runtime filtering by license compatibility
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# License mapping for each source
SOURCE_LICENSES = {
    'enable': 'CC0',
    'eowl': 'UKACD',
    'wikt': 'CC-BY-SA-4.0',
    'wordnet': 'WordNet',
    'frequency': 'CC-BY-4.0'
}


def compute_license_sources(sources: List[str]) -> Dict[str, List[str]]:
    """
    Compute license_sources mapping from sources list.

    Args:
        sources: List of source identifiers (e.g., ['enable', 'wikt'])

    Returns:
        Dict mapping license IDs to source lists
        e.g., {'CC0': ['enable'], 'CC-BY-SA-4.0': ['wikt']}
    """
    license_map = {}

    for source in sources:
        license_id = SOURCE_LICENSES.get(source)
        if license_id:
            license_map.setdefault(license_id, []).append(source)

    # Sort sources within each license for consistency
    for license_id in license_map:
        license_map[license_id] = sorted(license_map[license_id])

    return license_map


def merge_entries(entry1: dict, entry2: dict) -> dict:
    """
    Merge two entries for the same word.

    Union lists (pos, labels, sources).
    Prefer non-null for scalar fields.
    Compute license_sources from merged sources.
    """
    # Start with a copy of entry1
    merged = dict(entry1)

    # Union POS
    merged['pos'] = sorted(set(entry1.get('pos', []) + entry2.get('pos', [])))

    # Union labels (each category separately)
    labels1 = entry1.get('labels', {})
    labels2 = entry2.get('labels', {})

    merged_labels = {}
    all_label_keys = set(labels1.keys()) | set(labels2.keys())

    for key in all_label_keys:
        vals1 = labels1.get(key, [])
        vals2 = labels2.get(key, [])
        merged_labels[key] = sorted(set(vals1 + vals2))

    merged['labels'] = merged_labels

    # is_phrase: true if either is true
    merged['is_phrase'] = entry1.get('is_phrase', False) or entry2.get('is_phrase', False)

    # lemma: prefer non-null
    merged['lemma'] = entry1.get('lemma') or entry2.get('lemma')

    # concreteness: prefer non-null
    if 'concreteness' in entry2 and not entry1.get('concreteness'):
        merged['concreteness'] = entry2['concreteness']

    # frequency_tier: prefer lower tier (more frequent)
    # Order: top10 < top100 < top300 < top500 < top1k < top3k < top10k < top25k < top50k < rare
    tier_order = ['top10', 'top100', 'top300', 'top500', 'top1k', 'top3k', 'top10k', 'top25k', 'top50k', 'rare']
    tier1 = entry1.get('frequency_tier', 'rare')
    tier2 = entry2.get('frequency_tier', 'rare')

    if tier_order.index(tier1) < tier_order.index(tier2):
        merged['frequency_tier'] = tier1
    else:
        merged['frequency_tier'] = tier2

    # Union sources
    merged_sources = sorted(set(entry1.get('sources', []) + entry2.get('sources', [])))
    merged['sources'] = merged_sources

    # Compute license_sources from merged sources
    merged['license_sources'] = compute_license_sources(merged_sources)

    return merged


def load_entries(filepath: Path) -> Dict[str, dict]:
    """Load entries from JSONL file into a dict keyed by word."""
    entries = {}

    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return entries

    logger.info(f"Loading {filepath.name}")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 100000 == 0:
                logger.info(f"  Loaded {line_num:,} lines...")

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                word = entry['word']

                # Add license_sources if not present (for backward compatibility)
                if 'license_sources' not in entry:
                    entry['license_sources'] = compute_license_sources(entry.get('sources', []))

                if word in entries:
                    # Merge with existing
                    entries[word] = merge_entries(entries[word], entry)
                else:
                    entries[word] = entry
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    logger.info(f"  -> Loaded {len(entries):,} unique words")
    return entries


def write_merged(entries: Dict[str, dict], output_path: Path):
    """Write merged entries to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing {len(entries):,} merged entries to {output_path}")

    # Sort by word
    sorted_words = sorted(entries.keys())

    with open(output_path, 'wb') as f:
        for word in sorted_words:
            line = orjson.dumps(entries[word]) + b'\n'
            f.write(line)

    logger.info(f"Written: {output_path}")


def print_statistics(entries: Dict[str, dict]):
    """Print detailed statistics about the unified build."""
    logger.info("")
    logger.info("=== Unified Build Statistics ===")
    logger.info(f"Total unique words: {len(entries):,}")

    # Source distribution
    logger.info("")
    logger.info("Source distribution:")
    source_counts = {}
    for entry in entries.values():
        sources_key = ','.join(sorted(entry.get('sources', [])))
        source_counts[sources_key] = source_counts.get(sources_key, 0) + 1

    for sources_key, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {sources_key}: {count:,} words")

    # License distribution
    logger.info("")
    logger.info("License requirements:")
    license_counts = {}
    for entry in entries.values():
        licenses = entry.get('license_sources', {})
        licenses_key = ','.join(sorted(licenses.keys()))
        license_counts[licenses_key] = license_counts.get(licenses_key, 0) + 1

    for licenses_key, count in sorted(license_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {licenses_key}: {count:,} words")

    # Coverage statistics
    logger.info("")
    logger.info("Metadata coverage:")

    # POS coverage
    pos_count = sum(1 for e in entries.values() if e.get('pos'))
    logger.info(f"  POS tags: {pos_count:,} ({100 * pos_count / len(entries):.1f}%)")

    # Labels coverage
    any_labels = sum(1 for e in entries.values() if any(e.get('labels', {}).values()))
    logger.info(f"  Any labels: {any_labels:,} ({100 * any_labels / len(entries):.1f}%)")

    register_labels = sum(1 for e in entries.values() if e.get('labels', {}).get('register'))
    logger.info(f"    Register: {register_labels:,} ({100 * register_labels / len(entries):.1f}%)")

    domain_labels = sum(1 for e in entries.values() if e.get('labels', {}).get('domain'))
    logger.info(f"    Domain: {domain_labels:,} ({100 * domain_labels / len(entries):.1f}%)")

    region_labels = sum(1 for e in entries.values() if e.get('labels', {}).get('region'))
    logger.info(f"    Region: {region_labels:,} ({100 * region_labels / len(entries):.1f}%)")

    temporal_labels = sum(1 for e in entries.values() if e.get('labels', {}).get('temporal'))
    logger.info(f"    Temporal: {temporal_labels:,} ({100 * temporal_labels / len(entries):.1f}%)")

    # Concreteness (nouns only)
    nouns = [e for e in entries.values() if 'noun' in e.get('pos', [])]
    concrete_nouns = sum(1 for e in nouns if e.get('concreteness'))
    if nouns:
        logger.info(f"  Concreteness (nouns): {concrete_nouns:,}/{len(nouns):,} ({100 * concrete_nouns / len(nouns):.1f}%)")

    # Frequency tiers
    freq_count = sum(1 for e in entries.values() if e.get('frequency_tier'))
    logger.info(f"  Frequency tier: {freq_count:,} ({100 * freq_count / len(entries):.1f}%)")

    # Phrases
    phrases = sum(1 for e in entries.values() if e.get('is_phrase'))
    logger.info(f"  Multi-word phrases: {phrases:,} ({100 * phrases / len(entries):.1f}%)")


def main():
    """Main unified merge pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate"

    logger.info("=== Unified Merge Pipeline ===")
    logger.info("Merging all sources: ENABLE + EOWL + Wiktionary")

    # Load core entries (ENABLE + EOWL)
    core_path = intermediate_dir / "core" / "core_entries.jsonl"
    core_entries = load_entries(core_path)

    # Load Wiktionary entries
    wikt_path = intermediate_dir / "plus" / "wikt_entries.jsonl"
    wikt_entries = load_entries(wikt_path)

    # --- Unified merge ---
    logger.info("")
    logger.info("Merging all sources...")

    unified = dict(core_entries)  # Start with core

    for word, entry in wikt_entries.items():
        if word in unified:
            unified[word] = merge_entries(unified[word], entry)
        else:
            unified[word] = entry

    # Write output
    unified_output = intermediate_dir / "unified" / "entries_merged.jsonl"
    write_merged(unified, unified_output)

    # Print statistics
    print_statistics(unified)

    logger.info("")
    logger.info("=== Unified merge complete ===")


if __name__ == '__main__':
    main()
