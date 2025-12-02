#!/usr/bin/env python3
"""
wikt_sort.py - Sort Wiktionary entries lexicographically by word

Reads the unsorted wikt.jsonl (in XML source order) and outputs a sorted version
with entries sorted lexicographically by word. This ensures:
  1. Duplicate entries for the same word are consecutive
  2. Trie ordinal directly maps to line number (no offset table needed)
  3. Sorting logic matches trie_build.py exactly

Usage:
    python src/openword/wikt_sort.py --input INPUT.jsonl --output OUTPUT.jsonl

Both files are kept for traceability. The unsorted version preserves XML order
for debugging, while the sorted version is used by downstream tools.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict

from openword.progress_display import ProgressDisplay


def load_entries(input_file: Path) -> List[Dict]:
    """Load entries from JSONL file."""
    entries = []

    print(f"Loading {input_file.name}...")

    with ProgressDisplay(f"Loading entries", update_interval=1000) as progress:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    progress.update(Lines=line_num, Entries=len(entries))
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
                    continue

    print(f"Loaded {len(entries):,} entries")
    return entries


def sort_entries(entries: List[Dict]) -> List[Dict]:
    """
    Sort entries lexicographically by word.

    Uses the same sorting logic as trie_build.py to ensure consistency:
        sorted(entries, key=lambda e: e['word'])

    This is Python's default lexicographic sort based on Unicode code points.
    """
    print("Sorting entries by word...")

    # Same sorting as trie_build.py line 84
    sorted_entries = sorted(entries, key=lambda e: e['word'])

    # Report statistics about duplicates
    unique_words = len(set(e['word'] for e in entries))
    total_entries = len(entries)
    duplicate_entries = total_entries - unique_words

    print(f"  Unique words: {unique_words:,}")
    print(f"  Total entries: {total_entries:,}")
    print(f"  Duplicate entries: {duplicate_entries:,} ({duplicate_entries / total_entries * 100:.1f}%)")

    return sorted_entries


def write_entries(entries: List[Dict], output_file: Path):
    """Write sorted entries to JSONL file."""
    print(f"Writing {output_file.name}...")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with ProgressDisplay(f"Writing entries", update_interval=1000) as progress:
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(entries, start=1):
                json.dump(entry, f, ensure_ascii=False, separators=(',', ':'))
                f.write('\n')
                progress.update(Written=i)

    print(f"Wrote {len(entries):,} entries to {output_file}")

    # Report file sizes
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"File size: {size_mb:.2f} MB")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Sort Wiktionary entries lexicographically by word'
    )
    parser.add_argument('--input', type=Path, required=True,
                        help='Input JSONL file (unsorted Wiktionary entries)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output JSONL file (sorted by word)')
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        print(f"Run 'make build-wiktionary-json' first to extract Wiktionary data.")
        return 1

    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print()

    # Load entries
    entries = load_entries(input_file)

    # Sort entries (same logic as trie_build.py)
    sorted_entries = sort_entries(entries)

    # Write sorted entries
    print()
    write_entries(sorted_entries, output_file)

    print()
    print("=" * 80)
    print("SORTING COMPLETE")
    print("=" * 80)
    print(f"Sorted {len(sorted_entries):,} entries")
    print(f"Duplicate words now consecutive in {output_file.name}")
    print(f"Trie ordinals will map directly to line numbers")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
