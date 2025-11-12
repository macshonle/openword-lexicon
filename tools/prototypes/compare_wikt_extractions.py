#!/usr/bin/env python3
"""
compare_wikt_extractions.py - Compare wiktextract vs simple parser output

Validates that simple parser achieves acceptable coverage.

Usage:
    python compare_wikt_extractions.py wikt.jsonl wikt_simple.jsonl
"""

import json
import sys
from pathlib import Path
from collections import Counter


def load_entries(filepath: Path):
    """Load entries from JSONL file."""
    entries = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get('word', '')
            entries[word] = entry
    return entries


def compare_extractions(wiktextract_file: Path, simple_file: Path):
    """Compare two extraction outputs."""
    print(f"Loading wiktextract output: {wiktextract_file}")
    wikt_entries = load_entries(wiktextract_file)

    print(f"Loading simple parser output: {simple_file}")
    simple_entries = load_entries(simple_file)

    print()
    print("=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print()

    # Word coverage
    wikt_words = set(wikt_entries.keys())
    simple_words = set(simple_entries.keys())

    common = wikt_words & simple_words
    wikt_only = wikt_words - simple_words
    simple_only = simple_words - wikt_words

    print(f"Wiktextract words: {len(wikt_words):,}")
    print(f"Simple parser words: {len(simple_words):,}")
    print(f"Common words: {len(common):,}")
    print(f"Wiktextract only: {len(wikt_only):,}")
    print(f"Simple parser only: {len(simple_only):,}")
    print()

    coverage = len(common) / len(wikt_words) * 100 if wikt_words else 0
    print(f"Coverage: {coverage:.1f}%")
    print()

    # Show samples
    if wikt_only:
        print("Sample words in wiktextract but not simple parser:")
        for word in sorted(wikt_only)[:10]:
            print(f"  - {word}")
        print()

    if simple_only:
        print("Sample words in simple parser but not wiktextract:")
        for word in sorted(simple_only)[:10]:
            print(f"  - {word}")
        print()

    # Compare metadata for common words
    print("Metadata comparison (common words):")
    print()

    pos_matches = 0
    label_matches = 0

    for word in sorted(common)[:100]:  # Sample 100
        wikt_entry = wikt_entries[word]
        simple_entry = simple_entries[word]

        # Compare POS
        wikt_pos = set(wikt_entry.get('pos', []))
        simple_pos = set(simple_entry.get('pos', []))

        if wikt_pos == simple_pos:
            pos_matches += 1

        # Compare labels
        wikt_labels = wikt_entry.get('labels', {})
        simple_labels = simple_entry.get('labels', {})

        if wikt_labels == simple_labels:
            label_matches += 1

    print(f"POS match rate: {pos_matches}/100 ({pos_matches}%)")
    print(f"Label match rate: {label_matches}/100 ({label_matches}%)")
    print()

    # Show examples of differences
    print("Sample metadata differences:")
    print()

    shown = 0
    for word in sorted(common):
        if shown >= 5:
            break

        wikt_entry = wikt_entries[word]
        simple_entry = simple_entries[word]

        wikt_pos = set(wikt_entry.get('pos', []))
        simple_pos = set(simple_entry.get('pos', []))

        if wikt_pos != simple_pos:
            print(f"Word: {word}")
            print(f"  Wiktextract POS: {wikt_pos}")
            print(f"  Simple POS: {simple_pos}")
            print()
            shown += 1

    print("=" * 70)


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_wikt_extractions.py WIKTEXTRACT.jsonl SIMPLE.jsonl")
        sys.exit(1)

    wiktextract_file = Path(sys.argv[1])
    simple_file = Path(sys.argv[2])

    if not wiktextract_file.exists():
        print(f"Error: File not found: {wiktextract_file}")
        sys.exit(1)

    if not simple_file.exists():
        print(f"Error: File not found: {simple_file}")
        sys.exit(1)

    compare_extractions(wiktextract_file, simple_file)


if __name__ == '__main__':
    main()
