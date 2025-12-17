#!/usr/bin/env python3
"""
Extract full JSON entries for specific words from Python and Rust outputs.

Usage:
    python tools/extract_word_entries.py PYTHON.jsonl RUST.jsonl WORD1 WORD2 ...

Output: Prints full JSON entries for comparison, suitable for pasting into chat.
"""

import json
import sys
from pathlib import Path


def load_entries_for_words(jsonl_path, words):
    """Load entries for specific words from JSONL file."""
    word_set = set(words)
    entries = {}

    with open(jsonl_path) as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("id", "")
            if word in word_set:
                entries[word] = entry

    return entries


def main():
    if len(sys.argv) < 4:
        print("Usage: python tools/extract_word_entries.py PYTHON.jsonl RUST.jsonl WORD1 [WORD2 ...]")
        print("\nExample:")
        print("  python tools/extract_word_entries.py /tmp/test-python.jsonl /tmp/test-rust-fixed.jsonl acronym dialect four")
        sys.exit(1)

    python_path = Path(sys.argv[1])
    rust_path = Path(sys.argv[2])
    words = sys.argv[3:]

    if not python_path.exists():
        print(f"Error: Python file not found: {python_path}")
        sys.exit(1)

    if not rust_path.exists():
        print(f"Error: Rust file not found: {rust_path}")
        sys.exit(1)

    print(f"Loading entries for words: {', '.join(words)}")
    print(f"Python file: {python_path}")
    print(f"Rust file: {rust_path}")
    print()

    python_entries = load_entries_for_words(python_path, words)
    rust_entries = load_entries_for_words(rust_path, words)

    # Print comparison for each word
    for word in words:
        print("=" * 80)
        print(f"WORD: {word}")
        print("=" * 80)
        print()

        if word not in python_entries:
            print(f"⚠️  Word '{word}' not found in Python output")
        else:
            print("PYTHON ENTRY:")
            print("-" * 80)
            print(json.dumps(python_entries[word], indent=2, sort_keys=True))
            print()

        if word not in rust_entries:
            print(f"⚠️  Word '{word}' not found in Rust output")
        else:
            print("RUST ENTRY:")
            print("-" * 80)
            print(json.dumps(rust_entries[word], indent=2, sort_keys=True))
            print()

        # Highlight key differences
        if word in python_entries and word in rust_entries:
            py = python_entries[word]
            rust = rust_entries[word]

            differences = []
            for key in set(py.keys()) | set(rust.keys()):
                py_val = py.get(key)
                rust_val = rust.get(key)
                if py_val != rust_val:
                    differences.append((key, py_val, rust_val))

            if differences:
                print("KEY DIFFERENCES:")
                print("-" * 80)
                for key, py_val, rust_val in differences:
                    print(f"  {key}:")
                    print(f"    Python: {py_val}")
                    print(f"    Rust:   {rust_val}")
                print()

        print()


if __name__ == "__main__":
    main()
