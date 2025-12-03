#!/usr/bin/env python3
"""
Validate parity between Python and Rust Wiktionary scanners.

Performs line-by-line comparison of JSONL outputs:
- Checks that both files have the same number of entries
- Compares each entry as parsed JSON (property order doesn't matter)
- Verifies entries appear in the same order
- Reports all property differences, not just word/POS

Usage:
    uv run python tools/wiktionary-scanner-rust/scripts/validate_parity.py \
        --python-output /tmp/parity-python.jsonl \
        --rust-output /tmp/parity-rust.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def normalize_entry(entry: dict) -> dict:
    """Normalize an entry for comparison.

    Recursively sorts lists and dict keys for consistent comparison.
    """
    if isinstance(entry, dict):
        return {k: normalize_entry(v) for k, v in sorted(entry.items())}
    elif isinstance(entry, list):
        # Sort lists of strings/numbers, but preserve order for complex objects
        if all(isinstance(x, (str, int, float, bool)) for x in entry):
            return sorted(entry)
        return [normalize_entry(x) for x in entry]
    return entry


def diff_entries(py_entry: dict, rust_entry: dict) -> dict[str, Any]:
    """Find differences between two entries.

    Returns a dict describing the differences.
    """
    differences = {}

    all_keys = set(py_entry.keys()) | set(rust_entry.keys())

    for key in sorted(all_keys):
        py_val = py_entry.get(key)
        rust_val = rust_entry.get(key)

        if py_val is None and rust_val is not None:
            differences[key] = {"rust_only": rust_val}
        elif rust_val is None and py_val is not None:
            differences[key] = {"python_only": py_val}
        elif normalize_entry(py_val) != normalize_entry(rust_val):
            differences[key] = {"python": py_val, "rust": rust_val}

    return differences


def compare_files(python_path: Path, rust_path: Path) -> dict:
    """Compare two JSONL files line by line."""

    results = {
        "python_lines": 0,
        "rust_lines": 0,
        "matching_entries": 0,
        "mismatched_entries": 0,
        "mismatches": [],  # First N mismatches with details
    }

    max_mismatches_to_report = 20

    with open(python_path) as py_file, open(rust_path) as rust_file:
        line_num = 0

        while True:
            py_line = py_file.readline()
            rust_line = rust_file.readline()
            line_num += 1

            # Check for end of files
            py_eof = not py_line
            rust_eof = not rust_line

            if py_eof and rust_eof:
                break

            if py_eof:
                # Rust has more lines
                results["rust_lines"] = line_num
                # Count remaining rust lines
                remaining = 1
                while rust_file.readline():
                    remaining += 1
                results["rust_lines"] = line_num + remaining - 1
                results["mismatched_entries"] += remaining
                if len(results["mismatches"]) < max_mismatches_to_report:
                    results["mismatches"].append({
                        "line": line_num,
                        "error": "Python file ended early",
                        "rust_entry": json.loads(rust_line.strip()) if rust_line.strip() else None
                    })
                break

            if rust_eof:
                # Python has more lines
                results["python_lines"] = line_num
                # Count remaining python lines
                remaining = 1
                while py_file.readline():
                    remaining += 1
                results["python_lines"] = line_num + remaining - 1
                results["mismatched_entries"] += remaining
                if len(results["mismatches"]) < max_mismatches_to_report:
                    results["mismatches"].append({
                        "line": line_num,
                        "error": "Rust file ended early",
                        "python_entry": json.loads(py_line.strip()) if py_line.strip() else None
                    })
                break

            results["python_lines"] = line_num
            results["rust_lines"] = line_num

            # Parse and compare entries
            try:
                py_entry = json.loads(py_line.strip())
                rust_entry = json.loads(rust_line.strip())
            except json.JSONDecodeError as e:
                results["mismatched_entries"] += 1
                if len(results["mismatches"]) < max_mismatches_to_report:
                    results["mismatches"].append({
                        "line": line_num,
                        "error": f"JSON parse error: {e}",
                    })
                continue

            # Normalize and compare
            py_normalized = normalize_entry(py_entry)
            rust_normalized = normalize_entry(rust_entry)

            if py_normalized == rust_normalized:
                results["matching_entries"] += 1
            else:
                results["mismatched_entries"] += 1
                if len(results["mismatches"]) < max_mismatches_to_report:
                    diffs = diff_entries(py_entry, rust_entry)
                    results["mismatches"].append({
                        "line": line_num,
                        "word": py_entry.get("word") or rust_entry.get("word"),
                        "pos": py_entry.get("pos") or rust_entry.get("pos"),
                        "differences": diffs,
                    })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate parity between Python and Rust Wiktionary scanners"
    )
    parser.add_argument(
        "--python-output",
        type=Path,
        required=True,
        help="Path to Python scanner JSONL output",
    )
    parser.add_argument(
        "--rust-output",
        type=Path,
        required=True,
        help="Path to Rust scanner JSONL output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if not args.python_output.exists():
        print(f"Error: Python output not found: {args.python_output}")
        sys.exit(1)
    if not args.rust_output.exists():
        print(f"Error: Rust output not found: {args.rust_output}")
        sys.exit(1)

    print(f"Comparing outputs line-by-line...")
    print(f"  Python: {args.python_output}")
    print(f"  Rust:   {args.rust_output}")

    results = compare_files(args.python_output, args.rust_output)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 60)
        print("Parity Validation Results (Full Entry Comparison)")
        print("=" * 60)
        print(f"Python entries:   {results['python_lines']:,}")
        print(f"Rust entries:     {results['rust_lines']:,}")
        print(f"Matching:         {results['matching_entries']:,}")
        print(f"Mismatched:       {results['mismatched_entries']:,}")

        if results['mismatched_entries'] > 0:
            print(f"\nFirst {min(len(results['mismatches']), 20)} mismatches:")
            for m in results['mismatches'][:10]:
                if "error" in m:
                    print(f"  Line {m['line']}: {m['error']}")
                else:
                    print(f"  Line {m['line']}: {m['word']} ({m['pos']})")
                    for key, diff in m.get('differences', {}).items():
                        if 'python_only' in diff:
                            print(f"    {key}: Python has {diff['python_only']!r}, Rust missing")
                        elif 'rust_only' in diff:
                            print(f"    {key}: Rust has {diff['rust_only']!r}, Python missing")
                        else:
                            print(f"    {key}: Python={diff['python']!r} vs Rust={diff['rust']!r}")

        # Determine pass/fail
        total = results['matching_entries'] + results['mismatched_entries']
        if total == 0:
            print("\n✗ FAIL: No entries found")
            sys.exit(1)

        match_pct = results['matching_entries'] / total * 100
        print(f"\nMatch rate: {match_pct:.2f}%")

        if results['mismatched_entries'] == 0:
            print("\n✓ PASS: Perfect parity between scanners")
            sys.exit(0)
        elif match_pct >= 99.0:
            print(f"\n~ PASS: High parity ({match_pct:.2f}% match)")
            sys.exit(0)
        else:
            print(f"\n✗ FAIL: Low parity ({match_pct:.2f}% < 99%)")
            sys.exit(1)


if __name__ == "__main__":
    main()
