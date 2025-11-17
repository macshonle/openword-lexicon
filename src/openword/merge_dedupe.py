#!/usr/bin/env python3
"""
merge_dedupe.py — Merge and deduplicate entries per distribution.

Reads:
  - data/intermediate/core/core_entries_tiered.jsonl
  - data/intermediate/plus/wikt_entries_tiered.jsonl

Outputs:
  - data/intermediate/core/entries_merged.jsonl (core only)
  - data/intermediate/plus/entries_merged.jsonl (core + plus)

Merge logic:
  - Union POS tags
  - Union all label categories
  - Union sources
  - Prefer non-null values for lemma, concreteness, frequency_tier, phrase_type
  - Use max word_count (in case one source has better multi-word detection)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

import orjson

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def merge_entries(entry1: dict, entry2: dict) -> dict:
    """
    Merge two entries for the same word.

    Union lists (pos, labels, sources).
    Prefer non-null for scalar fields.
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
    merged['sources'] = sorted(set(entry1.get('sources', []) + entry2.get('sources', [])))

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

                    if word in entries:
                        # Merge with existing
                        entries[word] = merge_entries(entries[word], entry)
                    else:
                        entries[word] = entry

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


def main():
    """Main merge and deduplicate pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate"

    logger.info("Merge and deduplicate")

    # Load core entries
    core_path = intermediate_dir / "core" / "core_entries_tiered.jsonl"
    core_entries = load_entries(core_path)

    # Load plus entries
    plus_path = intermediate_dir / "plus" / "wikt_entries_tiered.jsonl"
    plus_entries = load_entries(plus_path)

    # --- CORE distribution (core sources only) ---
    logger.info("")
    logger.info("Creating CORE distribution...")
    core_output = intermediate_dir / "core" / "entries_merged.jsonl"
    write_merged(core_entries, core_output)

    logger.info(f"  Core distribution stats:")
    logger.info(f"    Total words: {len(core_entries):,}")
    logger.info(f"    Sources: {sorted(set(src for e in core_entries.values() for src in e['sources']))}")

    # --- PLUS distribution (core + plus) ---
    logger.info("")
    logger.info("Creating PLUS distribution...")

    # Merge core and plus
    combined = dict(core_entries)  # Start with core

    for word, entry in plus_entries.items():
        if word in combined:
            combined[word] = merge_entries(combined[word], entry)
        else:
            combined[word] = entry

    plus_output = intermediate_dir / "plus" / "entries_merged.jsonl"
    write_merged(combined, plus_output)

    logger.info(f"  Plus distribution stats:")
    logger.info(f"    Total words: {len(combined):,}")
    logger.info(f"    Core only: {sum(1 for e in combined.values() if 'wikt' not in e['sources']):,}")
    logger.info(f"    Plus only: {sum(1 for e in combined.values() if not any(s in ['enable', 'eowl'] for s in e['sources'])):,}")
    logger.info(f"    Both: {sum(1 for e in combined.values() if 'wikt' in e['sources'] and any(s in ['enable', 'eowl'] for s in e['sources'])):,}")
    logger.info(f"    Sources: {sorted(set(src for e in combined.values() for src in e['sources']))}")

    logger.info("")
    logger.info("Merge and deduplicate complete")


if __name__ == '__main__':
    main()
