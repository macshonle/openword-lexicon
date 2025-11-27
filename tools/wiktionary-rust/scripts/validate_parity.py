#!/usr/bin/env python3
"""
Validate parity between Python and Rust Wiktionary scanners.

Compares outputs at the word level, accounting for format differences:
- Python: One entry per word with pos: [list]
- Rust: One entry per sense with pos: string

Usage:
    uv run python tools/wiktionary-rust/scripts/validate_parity.py \
        --python-output /tmp/python-wikt.jsonl \
        --rust-output /tmp/rust-wikt.jsonl

    # Or just validate existing files
    uv run python tools/wiktionary-rust/scripts/validate_parity.py \
        --python-output data/benchmark/parity-python.jsonl \
        --rust-output data/benchmark/parity-rust.jsonl
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_python_output(path: Path) -> dict[str, set[str]]:
    """Load Python scanner output, aggregating senses to word -> set of POS tags.

    Python output format (same as Rust): one entry per sense with pos as string.
    """
    words = defaultdict(set)
    with open(path) as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("word", "")
            pos = entry.get("pos", "")
            if word and pos:
                words[word].add(pos)
    return dict(words)


def load_rust_output(path: Path) -> dict[str, set[str]]:
    """Load Rust scanner output, aggregating senses to word -> set of POS tags."""
    words = defaultdict(set)
    with open(path) as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("word", "")
            pos = entry.get("pos", "")
            if word and pos:
                words[word].add(pos)
    return dict(words)


def compare_outputs(python_words: dict, rust_words: dict) -> dict:
    """Compare word sets and POS tags between outputs."""
    py_set = set(python_words.keys())
    rust_set = set(rust_words.keys())

    common = py_set & rust_set
    python_only = py_set - rust_set
    rust_only = rust_set - py_set

    # Check POS tag mismatches for common words
    pos_mismatches = []
    for word in sorted(common):
        py_pos = python_words[word]
        rust_pos = rust_words[word]
        if py_pos != rust_pos:
            pos_mismatches.append({
                "word": word,
                "python_pos": sorted(py_pos),
                "rust_pos": sorted(rust_pos),
                "python_only": sorted(py_pos - rust_pos),
                "rust_only": sorted(rust_pos - py_pos),
            })

    return {
        "python_word_count": len(py_set),
        "rust_word_count": len(rust_set),
        "common_words": len(common),
        "python_only_count": len(python_only),
        "rust_only_count": len(rust_only),
        "python_only_sample": sorted(python_only)[:20],
        "rust_only_sample": sorted(rust_only)[:20],
        "pos_mismatch_count": len(pos_mismatches),
        "pos_mismatch_sample": pos_mismatches[:20],
    }


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

    print(f"Loading Python output: {args.python_output}")
    python_words = load_python_output(args.python_output)
    print(f"  Loaded {len(python_words):,} words")

    print(f"Loading Rust output: {args.rust_output}")
    rust_words = load_rust_output(args.rust_output)
    print(f"  Loaded {len(rust_words):,} words (aggregated from senses)")

    print("\nComparing outputs...")
    results = compare_outputs(python_words, rust_words)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 60)
        print("Parity Validation Results")
        print("=" * 60)
        print(f"Python words:     {results['python_word_count']:,}")
        print(f"Rust words:       {results['rust_word_count']:,}")
        print(f"Common words:     {results['common_words']:,}")
        print(f"Python-only:      {results['python_only_count']:,}")
        print(f"Rust-only:        {results['rust_only_count']:,}")
        print(f"POS mismatches:   {results['pos_mismatch_count']:,}")

        if results['python_only_count'] > 0:
            print(f"\nPython-only sample: {', '.join(results['python_only_sample'][:10])}")

        if results['rust_only_count'] > 0:
            print(f"\nRust-only sample: {', '.join(results['rust_only_sample'][:10])}")

        if results['pos_mismatch_count'] > 0:
            print("\nPOS mismatch sample:")
            for m in results['pos_mismatch_sample'][:5]:
                print(f"  {m['word']}: Python {m['python_pos']} vs Rust {m['rust_pos']}")

        # Determine pass/fail
        overlap_pct = results['common_words'] / max(results['python_word_count'], 1) * 100
        print(f"\nOverlap: {overlap_pct:.1f}%")

        if overlap_pct >= 95:
            print("\n✓ PASS: High parity between scanners")
            sys.exit(0)
        else:
            print(f"\n✗ FAIL: Low parity ({overlap_pct:.1f}% < 95%)")
            sys.exit(1)


if __name__ == "__main__":
    main()
