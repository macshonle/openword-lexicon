#!/usr/bin/env python3
"""
Compare Python and Rust Wiktionary parser outputs field-by-field.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def load_entries(jsonl_path):
    """Load entries from JSONL file into a dict keyed by word."""
    entries = {}
    with open(jsonl_path) as f:
        for line in f:
            entry = json.loads(line)
            entries[entry['id']] = entry
    return entries


def compare_field(word, field, py_val, rust_val):
    """Compare a single field and return differences."""
    if py_val == rust_val:
        return None

    # Handle None vs empty list/dict
    if (py_val is None and not rust_val) or (not py_val and rust_val is None):
        return None

    return {
        'id': word,
        'field': field,
        'python': py_val,
        'rust': rust_val
    }


def compare_entries(py_entries, rust_entries, sample_size=100):
    """Compare sample of entries from both outputs."""

    # Find common words
    common_words = set(py_entries.keys()) & set(rust_entries.keys())

    if len(common_words) < sample_size:
        sample_words = list(common_words)
        print(f"Warning: Only {len(common_words)} common entries found")
    else:
        sample_words = random.sample(list(common_words), sample_size)

    differences = []
    field_stats = defaultdict(lambda: {'match': 0, 'diff': 0, 'rust_only': 0, 'py_only': 0})

    for word in sorted(sample_words):
        py_entry = py_entries[word]
        rust_entry = rust_entries[word]

        # Compare each field
        for field in ['pos', 'labels', 'wc', 'is_phrase', 'is_abbreviation',
                      'is_vulgar', 'is_archaic', 'is_rare',
                      'is_informal', 'is_technical', 'is_regional', 'is_inflected',
                      'is_dated', 'sources', 'phrase_type', 'nsyll', 'morphology']:

            py_val = py_entry.get(field)
            rust_val = rust_entry.get(field)

            diff = compare_field(word, field, py_val, rust_val)
            if diff:
                differences.append(diff)
                field_stats[field]['diff'] += 1
            else:
                field_stats[field]['match'] += 1

            # Track presence statistics
            if py_val and not rust_val:
                field_stats[field]['py_only'] += 1
            elif rust_val and not py_val:
                field_stats[field]['rust_only'] += 1

    return sample_words, differences, field_stats


def print_report(sample_words, differences, field_stats):
    """Print comparison report."""

    print("=" * 80)
    print("WIKTIONARY PARSER COMPARISON REPORT")
    print("=" * 80)
    print()

    print(f"Sample size: {len(sample_words)} entries")
    print()

    # Field-by-field statistics
    print("Field-by-field comparison:")
    print("-" * 80)
    print(f"{'Field':<20} {'Matches':<10} {'Diffs':<10} {'Py Only':<10} {'Rust Only':<10}")
    print("-" * 80)

    for field in sorted(field_stats.keys()):
        stats = field_stats[field]
        print(f"{field:<20} {stats['match']:<10} {stats['diff']:<10} "
              f"{stats['py_only']:<10} {stats['rust_only']:<10}")

    print("-" * 80)
    total_matches = sum(s['match'] for s in field_stats.values())
    total_diffs = sum(s['diff'] for s in field_stats.values())
    total_checks = total_matches + total_diffs

    if total_checks > 0:
        match_pct = (total_matches / total_checks) * 100
        print(f"Total: {total_checks} field checks, {total_matches} matches ({match_pct:.1f}%), "
              f"{total_diffs} differences ({100-match_pct:.1f}%)")
    print()

    # Show differences
    if differences:
        print(f"\nFound {len(differences)} field differences:")
        print("=" * 80)

        # Group by field
        by_field = defaultdict(list)
        for diff in differences:
            by_field[diff['field']].append(diff)

        for field, diffs in sorted(by_field.items()):
            print(f"\n{field.upper()} ({len(diffs)} differences):")
            print("-" * 80)
            for diff in diffs[:5]:  # Show first 5 examples
                print(f"  Word: {diff['id']}")
                print(f"  Python: {diff['python']}")
                print(f"  Rust:   {diff['rust']}")
                print()
            if len(diffs) > 5:
                print(f"  ... and {len(diffs) - 5} more")
                print()
    else:
        print("\n✅ No differences found! Perfect parity.")

    print()
    print("=" * 80)


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_outputs.py <python_output.jsonl> <rust_output.jsonl>")
        sys.exit(1)

    py_path = Path(sys.argv[1])
    rust_path = Path(sys.argv[2])

    if not py_path.exists():
        print(f"Error: Python output not found: {py_path}")
        sys.exit(1)

    if not rust_path.exists():
        print(f"Error: Rust output not found: {rust_path}")
        sys.exit(1)

    print("Loading entries...")
    py_entries = load_entries(py_path)
    rust_entries = load_entries(rust_path)

    print(f"Python entries: {len(py_entries):,}")
    print(f"Rust entries: {len(rust_entries):,}")
    print(f"Common entries: {len(set(py_entries.keys()) & set(rust_entries.keys())):,}")
    print()

    print("Comparing random sample of 100 entries...")
    sample_words, differences, field_stats = compare_entries(py_entries, rust_entries, sample_size=100)

    print_report(sample_words, differences, field_stats)


if __name__ == '__main__':
    main()
