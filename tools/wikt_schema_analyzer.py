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


def should_include_path(path: str) -> bool:
    """
    Determine if a path should be included in the analysis.

    Prunes all morphology paths except morphology.is_compound and morphology.type.

    Args:
        path: Dot-notation path to check

    Returns:
        True if path should be included, False otherwise
    """
    # Include all non-morphology paths
    if not path.startswith("morphology."):
        return True

    # Only include these specific morphology paths
    if path in ("morphology.is_compound", "morphology.type"):
        return True

    # Exclude all other morphology paths
    return False


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
    """Print final aggregate with all unique values on single lines."""
    print(f"\n{'='*80}")
    print(f"FINAL AGGREGATE - {entry_count:,} entries analyzed")
    print(f"{'='*80}\n")

    sorted_paths = sorted(aggregate.keys())

    for path in sorted_paths:
        values = aggregate[path]

        # Check if all values are integers (excluding None)
        non_null_values = [v for v in values if v is not None]
        all_integers = all(isinstance(v, int) and not isinstance(v, bool) for v in non_null_values)

        if all_integers and len(non_null_values) > 0:
            # For integer-only sets, show min and max
            min_val = min(non_null_values)
            max_val = max(non_null_values)
            print(f"{path}: [min: {min_val}, max: {max_val}]")
        else:
            # Sort values for consistent output
            try:
                sorted_values = sorted(values, key=lambda x: (x is None, isinstance(x, bool), x))
            except TypeError:
                # If values aren't comparable, convert to strings for sorting
                sorted_values = sorted(values, key=lambda x: (x is None, str(type(x)), str(x)))

            # Format all values inline
            formatted_values = [format_value(v) for v in sorted_values]
            values_str = ", ".join(formatted_values)
            print(f"{path}: [{values_str}]")


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
                    # Only include paths that pass the filter
                    if should_include_path(path):
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
