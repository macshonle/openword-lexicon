#!/usr/bin/env python3
"""
wikt_schema_analyzer.py - Analyze Wiktionary JSON schema and extract all unique values

Reads data/intermediate/en/wikt.jsonl and builds an aggregate view of all unique
values for each field path across all entries.

Usage:
    python tools/wikt_schema_analyzer.py [INPUT_FILE]

Arguments:
    INPUT_FILE  Optional path to input JSONL file (default: data/intermediate/en/wikt.jsonl)
"""

import json
import sys
from pathlib import Path
from typing import Dict, Set, Any
from collections import defaultdict


def flatten_entry(entry: dict, prefix: str = "") -> Dict[str, Set[Any]]:
    """
    Flatten a JSON entry into path->values mapping.

    Args:
        entry: Dictionary to flatten
        prefix: Current path prefix

    Returns:
        Dictionary mapping paths to sets of primitive values
    """
    result = defaultdict(set)

    for key, value in entry.items():
        # Skip the 'word' field
        if prefix == "" and key == "word":
            continue

        path = f"{prefix}.{key}" if prefix else key

        if value is None:
            result[path].add(None)
        elif isinstance(value, (str, int, float, bool)):
            result[path].add(value)
        elif isinstance(value, list):
            # For arrays, add each element to the set
            for item in value:
                if isinstance(item, (str, int, float, bool, type(None))):
                    result[path].add(item)
                elif isinstance(item, dict):
                    # Nested dict in array
                    nested = flatten_entry(item, path)
                    for nested_path, nested_values in nested.items():
                        result[nested_path].update(nested_values)
        elif isinstance(value, dict):
            # Recursively flatten nested objects
            nested = flatten_entry(value, path)
            for nested_path, nested_values in nested.items():
                result[nested_path].update(nested_values)

    return result


def format_value(val: Any) -> str:
    """Format a value for display."""
    if isinstance(val, str):
        return f'"{val}"'
    elif val is None:
        return "null"
    elif isinstance(val, bool):
        return "true" if val else "false"
    else:
        return str(val)


def print_progress(aggregate: Dict[str, Set[Any]], entry_count: int):
    """Print progress update showing paths and value counts."""
    print(f"\n{'='*80}")
    print(f"Progress: {entry_count:,} entries processed")
    print(f"{'='*80}")

    sorted_paths = sorted(aggregate.keys())

    print(f"\nPaths found: {len(sorted_paths)}")
    print("-" * 80)

    for path in sorted_paths:
        value_count = len(aggregate[path])
        print(f"  {path:40s} [{value_count:>6,} unique values]")

    print()


def print_final_aggregate(aggregate: Dict[str, Set[Any]], entry_count: int):
    """Print final aggregate with all unique values."""
    print(f"\n{'='*80}")
    print(f"FINAL AGGREGATE - {entry_count:,} entries analyzed")
    print(f"{'='*80}\n")

    sorted_paths = sorted(aggregate.keys())

    for path in sorted_paths:
        values = aggregate[path]

        # Sort values for consistent output
        # Sort with None first, then by value
        try:
            sorted_values = sorted(values, key=lambda x: (x is None, isinstance(x, bool), x))
        except TypeError:
            # If values aren't comparable, convert to strings for sorting
            sorted_values = sorted(values, key=lambda x: (x is None, str(type(x)), str(x)))

        print(f"{path}:")

        # For large sets, show count and sample
        if len(sorted_values) > 50:
            print(f"  ({len(sorted_values):,} unique values - showing first 50)")
            print("  [")
            for i in range(50):
                formatted = format_value(sorted_values[i])
                print(f"    {formatted},")
            print(f"    ... and {len(sorted_values) - 50:,} more")
            print("  ]")
        else:
            # Show all values
            print(f"  ({len(sorted_values):,} unique values)")
            print("  [")
            for i, val in enumerate(sorted_values):
                formatted = format_value(val)
                if i < len(sorted_values) - 1:
                    print(f"    {formatted},")
                else:
                    print(f"    {formatted}")
            print("  ]")

        print()


def main():
    """Main analysis function."""
    # Check for command line argument
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    else:
        project_root = Path(__file__).parent.parent
        input_file = project_root / "data" / "intermediate" / "en" / "wikt.jsonl"

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        print("Run 'make build-wiktionary-json' first to extract Wiktionary data.")
        return 1

    print(f"Analyzing: {input_file}")
    print(f"File size: {input_file.stat().st_size / (1024*1024):.1f} MB")
    print()

    # Aggregate: path -> set of unique values
    aggregate = defaultdict(set)
    entry_count = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                entry = json.loads(line)

                # Flatten and aggregate
                flattened = flatten_entry(entry)
                for path, values in flattened.items():
                    aggregate[path].update(values)

                entry_count += 1

                # Progress update every 1000 entries
                if entry_count % 1000 == 0:
                    print_progress(aggregate, entry_count)

            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
                continue

    # Final output
    print_final_aggregate(aggregate, entry_count)

    # Summary stats
    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total entries analyzed: {entry_count:,}")
    print(f"Total unique paths: {len(aggregate):,}")
    print(f"Total unique values (across all paths): {sum(len(v) for v in aggregate.values()):,}")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
