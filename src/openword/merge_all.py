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
  - Prefer non-null values for lemma, concreteness, frequency_tier, phrase_type
  - Use max word_count (in case one source has better multi-word detection)

License tracking:
  - Automatically compute license requirements from sources
  - Enable runtime filtering by license compatibility
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

import orjson

from openword.progress_display import ProgressDisplay
from openword import build_stats


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

    # word_count: prefer max (in case one source has better multi-word detection)
    wc1 = entry1.get('word_count', len(entry1['word'].split()))
    wc2 = entry2.get('word_count', len(entry2['word'].split()))
    merged['word_count'] = max(wc1, wc2)

    # phrase_type: prefer non-null
    merged_phrase_type = entry1.get('phrase_type') or entry2.get('phrase_type')
    if merged_phrase_type:
        merged['phrase_type'] = merged_phrase_type

    # lemma: prefer non-null
    merged['lemma'] = entry1.get('lemma') or entry2.get('lemma')

    # syllables: prefer non-null
    merged['syllables'] = entry1.get('syllables') or entry2.get('syllables')

    # concreteness: prefer non-null
    if 'concreteness' in entry2 and not entry1.get('concreteness'):
        merged['concreteness'] = entry2['concreteness']

    # frequency_tier: prefer more frequent tier (earlier in alphabet)
    # Order: A (most frequent) < B < C < ... < Z (extremely rare)
    tier1 = entry1.get('frequency_tier', 'Z')
    tier2 = entry2.get('frequency_tier', 'Z')

    # Simple alphabetical comparison (A < B < ... < Z)
    if tier1 < tier2:
        merged['frequency_tier'] = tier1
    else:
        merged['frequency_tier'] = tier2

    # Union sources
    merged_sources = sorted(set(entry1.get('sources', []) + entry2.get('sources', [])))
    merged['sources'] = merged_sources

    # Compute license_sources from merged sources
    merged['license_sources'] = compute_license_sources(merged_sources)

    # Merge proper noun flags (OR logic - if ANY entry has it, keep it)
    # These fields track whether a word has proper noun usage, common usage, or both
    merged['is_proper_noun'] = (
        entry1.get('is_proper_noun', False) or
        entry2.get('is_proper_noun', False)
    )
    merged['has_proper_usage'] = (
        entry1.get('has_proper_usage', False) or
        entry2.get('has_proper_usage', False)
    )
    merged['has_common_usage'] = (
        entry1.get('has_common_usage', False) or
        entry2.get('has_common_usage', False)
    )

    return merged


def load_entries(filepath: Path) -> Dict[str, dict]:
    """Load entries from JSONL file into a dict keyed by word."""
    entries = {}

    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return entries

    logger.info(f"Loading {filepath.name}")

    with ProgressDisplay(f"Loading {filepath.name}", update_interval=10000) as progress:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
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

                    # Update progress display
                    progress.update(Lines=line_num, Words=len(entries))
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
            line = orjson.dumps(entries[word], option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"Written: {output_path}")


def generate_build_statistics(entries: Dict[str, dict]):
    """Generate build statistics JSON file for word list builder."""
    project_root = Path(__file__).parent.parent.parent
    stats_output = project_root / "tools" / "wordlist-builder" / "build-statistics.json"

    logger.info("")
    logger.info("Generating build statistics...")

    stats = build_stats.generate_and_write_statistics(entries, stats_output)

    # Print the JSON output to console (pretty-printed)
    logger.info("")
    print(json.dumps(stats, indent=2))
    logger.info("")
    logger.info(f"Statistics written to: {stats_output}")


def main():
    """Main unified merge pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate" / "en"

    logger.info("=== Unified Merge Pipeline (English) ===")
    logger.info("Merging all sources: EOWL + Wiktionary + WordNet")
    logger.info("(ENABLE optional - validation only)")

    # Load core entries (EOWL + optional ENABLE)
    core_path = intermediate_dir / "core_entries.jsonl"
    core_entries = load_entries(core_path)

    # Initialize proper noun flags for core entries (they're all common words from game word lists)
    for entry in core_entries.values():
        if 'is_proper_noun' not in entry:
            entry['is_proper_noun'] = False
        if 'has_proper_usage' not in entry:
            entry['has_proper_usage'] = False
        if 'has_common_usage' not in entry:
            entry['has_common_usage'] = True

    # Load Wiktionary entries
    wikt_path = intermediate_dir / "wikt_entries.jsonl"
    wikt_entries = load_entries(wikt_path)

    # Load WordNet entries (NEW!)
    wordnet_path = intermediate_dir / "wordnet_entries.jsonl"
    if wordnet_path.exists():
        wordnet_entries = load_entries(wordnet_path)
        logger.info(f"  Loaded WordNet: {len(wordnet_entries):,} entries")
    else:
        wordnet_entries = {}
        logger.warning(f"  WordNet entries not found at {wordnet_path}")
        logger.warning("  Continuing without WordNet word source")

    # --- Unified merge ---
    logger.info("")
    logger.info("Merging all sources...")

    unified = dict(core_entries)  # Start with core

    # Merge Wiktionary
    for word, entry in wikt_entries.items():
        if word in unified:
            unified[word] = merge_entries(unified[word], entry)
        else:
            unified[word] = entry

    # Merge WordNet
    for word, entry in wordnet_entries.items():
        if word in unified:
            unified[word] = merge_entries(unified[word], entry)
        else:
            unified[word] = entry

    # Write output
    unified_output = intermediate_dir / "entries_merged.jsonl"
    write_merged(unified, unified_output)

    # Generate build statistics
    generate_build_statistics(unified)

    logger.info("")
    logger.info("=== Unified merge complete ===")


if __name__ == '__main__':
    main()
