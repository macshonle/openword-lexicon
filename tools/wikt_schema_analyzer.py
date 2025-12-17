#!/usr/bin/env python3
"""
wikt_schema_analyzer.py - Analyze Wiktionary JSON schema and extract all unique values

Reads data/intermediate/en-wikt.jsonl and builds an aggregate view of all unique
values for each field path across all entries. Shows:
  - All unique values for each field
  - Bit counts for encoding (mutually exclusive fields use log2, combinatorial use count)
  - Array combination analysis (frequency of value combinations)

This helps identify encoding optimization opportunities. See also:
  - wikt_entry_mapper.py: Build word-to-entry offset mapping for duplicate words
  - wikt_entry_lookup.py: Lookup entries using the sparse offset table

Usage:
    python tools/wikt_schema_analyzer.py [INPUT_FILE]

Arguments:
    INPUT_FILE  Optional path to input JSONL file (default: data/intermediate/en-wikt.jsonl)
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, Set, Any, List, Tuple
from collections import defaultdict, Counter


def flatten_entry(entry: dict, prefix: str = "") -> Dict[str, Set[Any]]:
    """
    Flatten a JSON entry into path->values mapping.

    Args:
        entry: Dictionary to flatten
        prefix: Current path prefix

    Returns:
        Dictionary mapping paths (underscore-separated) to sets of primitive values
    """
    result = defaultdict(set)

    for key, value in entry.items():
        # Skip the 'word' field
        if prefix == "" and key == "id":
            continue

        path = f"{prefix}_{key}" if prefix else key

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

    Prunes all morphology paths except morphology_is_compound and morphology_type.

    Args:
        path: Underscore-separated path to check

    Returns:
        True if path should be included, False otherwise
    """
    # Include all non-morphology paths
    if not path.startswith("morphology_"):
        return True

    # Only include these specific morphology paths
    if path in ("morphology_is_compound", "morphology_type"):
        return True

    # Exclude all other morphology paths
    return False


def extract_array_combinations(entry: dict, prefix: str = "") -> Dict[str, Tuple[str, ...]]:
    """
    Extract array-valued fields and their combinations.

    Args:
        entry: Dictionary to extract from
        prefix: Current path prefix

    Returns:
        Dictionary mapping paths to tuples of sorted values (the combination)
    """
    result = {}

    for key, value in entry.items():
        # Skip the 'word' field
        if prefix == "" and key == "id":
            continue

        path = f"{prefix}_{key}" if prefix else key

        if isinstance(value, list):
            # Check if list contains only primitive values
            if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                # Sort and convert to tuple for hashability
                sorted_values = tuple(sorted(str(v) for v in value if v is not None))
                if sorted_values:  # Only include non-empty arrays
                    result[path] = sorted_values
        elif isinstance(value, dict):
            # Recursively extract from nested objects
            nested = extract_array_combinations(value, path)
            result.update(nested)

    return result


def format_value(val: Any) -> str:
    """Format a value for display (without quotes)."""
    if isinstance(val, str):
        return f'"{val}"'
    elif val is None:
        return "null"
    elif isinstance(val, bool):
        return "true" if val else "false"
    else:
        return str(val)


def format_integer_range(values: Set[int]) -> str:
    """
    Format a set of integers as compressed ranges.

    Example: {1,2,3,5,7,8,9} -> "1-3,5,7-9 (8 ~ 3 bits)"

    Args:
        values: Set of integer values

    Returns:
        Formatted range string with statistics
    """
    sorted_vals = sorted(values)
    if not sorted_vals:
        return ""

    # Find consecutive ranges
    ranges: List[str] = []
    start = sorted_vals[0]
    end = sorted_vals[0]

    for i in range(1, len(sorted_vals)):
        if sorted_vals[i] == end + 1:
            # Consecutive
            end = sorted_vals[i]
        else:
            # Gap - finish current range
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = sorted_vals[i]
            end = sorted_vals[i]

    # Don't forget the last range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    range_str = ",".join(ranges)

    # Calculate stats
    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]
    v = max_val - min_val
    bits = math.ceil(math.log2(v)) if v > 0 else 0

    return f"{range_str} ({v} ~ {bits} bits)"


def print_progress(aggregate: Dict[str, Set[Any]], entry_count: int, last_line_count: int = 0):
    """
    Print progress update showing paths and value counts.

    Uses ANSI escape codes to update in place without scrolling.

    Args:
        aggregate: Current aggregate state
        entry_count: Number of entries processed
        last_line_count: Number of lines printed in last update (for clearing)

    Returns:
        Number of lines printed in this update
    """
    # Clear previous output if this isn't the first update
    if last_line_count > 0:
        # Move cursor up and clear lines
        for _ in range(last_line_count):
            sys.stdout.write('\033[A')  # Move up
            sys.stdout.write('\033[K')  # Clear line

    lines = []
    lines.append(f"{'='*80}")
    lines.append(f"Progress: {entry_count:,} entries processed")
    lines.append(f"{'='*80}")
    lines.append("")
    lines.append(f"Paths found: {len(aggregate)}")
    lines.append("-" * 80)

    sorted_paths = sorted(aggregate.keys())
    for path in sorted_paths:
        value_count = len(aggregate[path])
        lines.append(f"  {path:40s} [{value_count:>6,} unique values]")

    lines.append("")

    # Print all lines
    for line in lines:
        print(line)

    return len(lines)


def print_final_aggregate(aggregate: Dict[str, Set[Any]], entry_count: int) -> int:
    """
    Print final aggregate with all unique values on single lines.

    Format:
    - Label paths: path: "val1", "val2", "val3" (count = count bits)
    - Other non-integers: path: "val1", "val2" (count ~ bits)
    - Integers: path: 1-3,5,7-9 (range ~ bits)

    Returns:
        Total bit count across all paths
    """
    print(f"\n{'='*80}")
    print(f"FINAL AGGREGATE - {entry_count:,} entries analyzed")
    print(f"{'='*80}\n")

    sorted_paths = sorted(aggregate.keys())
    total_bits = 0

    for path in sorted_paths:
        values = aggregate[path]

        # Check if all values are integers (excluding None)
        non_null_values = [v for v in values if v is not None]
        all_integers = all(isinstance(v, int) and not isinstance(v, bool) for v in non_null_values)

        if all_integers and len(non_null_values) > 0:
            # For integer-only sets, use range compression
            range_str = format_integer_range(set(non_null_values))
            print(f"{path}: {range_str}")

            # Calculate bits for integers (based on range)
            min_val = min(non_null_values)
            max_val = max(non_null_values)
            v = max_val - min_val
            bits = math.ceil(math.log2(v)) if v > 0 else 0
            total_bits += bits
        else:
            # Sort values for consistent output
            try:
                sorted_values = sorted(values, key=lambda x: (x is None, isinstance(x, bool), x))
            except TypeError:
                # If values aren't comparable, convert to strings for sorting
                sorted_values = sorted(values, key=lambda x: (x is None, str(type(x)), str(x)))

            # Format all values inline (comma-separated, with count and bits)
            formatted_values = [format_value(v) for v in sorted_values]
            values_str = ", ".join(formatted_values)
            count = len(sorted_values)

            # Calculate bits: labels use count directly, others use log2
            if path.startswith("labels_"):
                # Label paths: any combination possible, so count = bits
                bits = count
                total_bits += bits
                print(f"{path}: {values_str} ({count} = {bits} bit{'s' if bits != 1 else ''})")
            else:
                # Non-label paths: use log2 for encoding
                bits = math.ceil(math.log2(count)) if count > 1 else 0
                total_bits += bits
                print(f"{path}: {values_str} ({count} ~ {bits} bit{'s' if bits != 1 else ''})")

    return total_bits


def print_array_combination_stats(combinations: Dict[str, Counter], entry_count: int):
    """
    Print statistics about array value combinations.

    Shows most common combinations and individual value frequencies.
    """
    print(f"\n{'='*80}")
    print("ARRAY COMBINATION ANALYSIS")
    print(f"{'='*80}\n")

    for path in sorted(combinations.keys()):
        combo_counts = combinations[path]
        if not combo_counts:
            continue

        total_occurrences = sum(combo_counts.values())
        unique_combinations = len(combo_counts)

        print(f"{path}:")
        print(f"  Total occurrences: {total_occurrences:,}")
        print(f"  Unique combinations: {unique_combinations:,}")
        print(f"  Coverage: {total_occurrences / entry_count * 100:.1f}% of entries")

        # Show top 10 combinations
        print("\n  Top 10 combinations:")
        for i, (combo, count) in enumerate(combo_counts.most_common(10), 1):
            pct = count / total_occurrences * 100
            combo_str = ", ".join(f'"{v}"' for v in combo)
            print(f"    {i:2d}. [{combo_str}] - {count:,} ({pct:.1f}%)")

        # Calculate individual value frequencies
        value_freq = Counter()
        for combo, count in combo_counts.items():
            for value in combo:
                value_freq[value] += count

        print("\n  Individual value frequencies:")
        for value, count in value_freq.most_common(10):
            pct = count / total_occurrences * 100
            print(f"    \"{value}\": {count:,} ({pct:.1f}%)")

        # Coverage analysis
        cumulative = 0
        for i, (combo, count) in enumerate(combo_counts.most_common(), 1):
            cumulative += count
            coverage = cumulative / total_occurrences * 100
            if coverage >= 80 and i <= 20:
                print(f"\n  Top {i} combinations cover {coverage:.1f}% of occurrences")
                break
            elif i == 5:
                print(f"\n  Top 5 combinations cover {coverage:.1f}% of occurrences")

        print()


def main():
    """Main analysis function."""
    # Check for command line argument (flat structure with language-prefixed files)
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    else:
        project_root = Path(__file__).parent.parent
        input_file = project_root / "data" / "intermediate" / "en-wikt.jsonl"

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        print("Run 'make build-wiktionary-json' first to extract Wiktionary data.")
        return 1

    print(f"Analyzing: {input_file}")
    print(f"File size: {input_file.stat().st_size / (1024*1024):.1f} MB")
    print()

    # Aggregate: path -> set of unique values
    aggregate = defaultdict(set)
    # Track array combinations: path -> Counter of combination tuples
    array_combinations = defaultdict(Counter)
    entry_count = 0
    last_line_count = 0

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

                # Extract and count array combinations
                combos = extract_array_combinations(entry)
                for path, combo in combos.items():
                    if should_include_path(path):
                        array_combinations[path][combo] += 1

                entry_count += 1

                # Progress update every 1000 entries
                if entry_count % 1000 == 0:
                    last_line_count = print_progress(aggregate, entry_count, last_line_count)

            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
                continue

    # Clear the progress display before showing final output
    if last_line_count > 0:
        for _ in range(last_line_count):
            sys.stdout.write('\033[A')  # Move up
            sys.stdout.write('\033[K')  # Clear line

    # Final output
    total_bits = print_final_aggregate(aggregate, entry_count)

    # Array combination analysis
    print_array_combination_stats(array_combinations, entry_count)

    # Summary stats
    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total entries analyzed: {entry_count:,}")
    print(f"Total unique paths: {len(aggregate):,}")
    print(f"Total unique values (across all paths): {sum(len(v) for v in aggregate.values()):,}")
    print(f"Total bits: {total_bits}")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
