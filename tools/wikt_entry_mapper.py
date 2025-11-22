#!/usr/bin/env python3
"""
wikt_entry_mapper.py - Build word-to-entry offset mapping for trie lookups

Reads wikt.jsonl and creates an efficient mapping from trie word ordinals
to entry data, handling words with multiple entries using a sparse offset table.

Usage:
    python tools/wikt_entry_mapper.py [INPUT_FILE] [OUTPUT_DIR]

Arguments:
    INPUT_FILE  Path to wikt.jsonl (default: data/intermediate/en/wikt.jsonl)
    OUTPUT_DIR  Output directory for mapping files (default: data/intermediate/en/)

Outputs:
    - entry_offsets.bin: Array of entry start indices (4 bytes × num_unique_words)
    - entry_counts.json: Sparse map of {word_ordinal: count} for multi-entry words
    - duplicate_analysis.txt: Statistics about duplicate word distribution
"""

import json
import struct
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict


def analyze_duplicates(input_file: Path) -> Tuple[Dict[str, List[int]], List[str]]:
    """
    Analyze duplicate word entries and build word-to-line-number mapping.

    Returns:
        Tuple of (word_to_lines, ordered_words)
        - word_to_lines: Dict mapping each word to list of line numbers where it appears
        - ordered_words: List of unique words in order of first appearance
    """
    word_to_lines = defaultdict(list)
    ordered_words = []
    seen_words = set()

    print(f"Scanning {input_file}...")

    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=0):  # 0-indexed
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                word = entry.get('word')

                if word:
                    word_to_lines[word].append(line_num)

                    if word not in seen_words:
                        ordered_words.append(word)
                        seen_words.add(word)

            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
                continue

    return dict(word_to_lines), ordered_words


def build_mapping_structures(
    word_to_lines: Dict[str, List[int]],
    ordered_words: List[str]
) -> Tuple[List[int], Dict[int, int]]:
    """
    Build sparse offset table structures.

    Args:
        word_to_lines: Map of word -> list of line numbers
        ordered_words: List of unique words in order

    Returns:
        Tuple of (entry_offsets, entry_counts)
        - entry_offsets: List of starting line numbers for each word
        - entry_counts: Sparse dict of {word_ordinal: count} for multi-entry words
    """
    entry_offsets = []
    entry_counts = {}

    for ordinal, word in enumerate(ordered_words):
        lines = word_to_lines[word]

        # Store the first line number as the offset
        entry_offsets.append(lines[0])

        # Only store count if > 1 (sparse)
        if len(lines) > 1:
            entry_counts[ordinal] = len(lines)

    return entry_offsets, entry_counts


def write_mapping_files(
    entry_offsets: List[int],
    entry_counts: Dict[int, int],
    output_dir: Path
):
    """Write mapping structures to disk."""

    # Write binary offset array (4 bytes per entry)
    offsets_file = output_dir / "entry_offsets.bin"
    with open(offsets_file, 'wb') as f:
        for offset in entry_offsets:
            f.write(struct.pack('<I', offset))  # Little-endian unsigned int

    print(f"✓ Wrote {len(entry_offsets):,} offsets to {offsets_file}")
    print(f"  File size: {offsets_file.stat().st_size / (1024*1024):.2f} MB")

    # Write sparse counts as JSON
    counts_file = output_dir / "entry_counts.json"
    with open(counts_file, 'w', encoding='utf-8') as f:
        json.dump(entry_counts, f, indent=2)

    print(f"✓ Wrote {len(entry_counts):,} multi-entry counts to {counts_file}")
    print(f"  File size: {counts_file.stat().st_size / 1024:.2f} KB")


def write_duplicate_analysis(
    word_to_lines: Dict[str, List[int]],
    output_file: Path
):
    """Write detailed analysis of duplicate word patterns."""

    # Calculate statistics
    total_words = len(word_to_lines)
    total_entries = sum(len(lines) for lines in word_to_lines.values())

    duplicate_words = {word: lines for word, lines in word_to_lines.items() if len(lines) > 1}
    duplicate_count = len(duplicate_words)
    duplicate_entries = sum(len(lines) for lines in duplicate_words.values())

    # Entry count distribution
    entry_count_dist = Counter(len(lines) for lines in word_to_lines.values())

    # Top duplicates
    top_duplicates = sorted(duplicate_words.items(), key=lambda x: len(x[1]), reverse=True)[:50]

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("WIKTIONARY DUPLICATE WORD ANALYSIS\n")
        f.write("=" * 80 + "\n\n")

        f.write("SUMMARY STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total unique words:        {total_words:>12,}\n")
        f.write(f"Total entries:             {total_entries:>12,}\n")
        f.write(f"Single-entry words:        {total_words - duplicate_count:>12,} ({(total_words - duplicate_count) / total_words * 100:.1f}%)\n")
        f.write(f"Multi-entry words:         {duplicate_count:>12,} ({duplicate_count / total_words * 100:.1f}%)\n")
        f.write(f"Duplicate entries:         {duplicate_entries - duplicate_count:>12,}\n")
        f.write("\n")

        f.write("ENTRY COUNT DISTRIBUTION\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Entries/Word':<15} {'Count':<12} {'Percentage':<12} {'Cumulative'}\n")

        cumulative = 0
        for count in sorted(entry_count_dist.keys()):
            freq = entry_count_dist[count]
            pct = freq / total_words * 100
            cumulative += freq
            cum_pct = cumulative / total_words * 100
            f.write(f"{count:<15} {freq:<12,} {pct:>10.2f}% {cum_pct:>12.2f}%\n")

        f.write("\n")
        f.write("TOP 50 WORDS WITH MOST ENTRIES\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Rank':<6} {'Word':<20} {'Entries':<10} {'Line Numbers'}\n")

        for i, (word, lines) in enumerate(top_duplicates, 1):
            # Show first 10 line numbers
            line_preview = ", ".join(str(ln) for ln in lines[:10])
            if len(lines) > 10:
                line_preview += f", ... ({len(lines) - 10} more)"
            f.write(f"{i:<6} {word:<20} {len(lines):<10} {line_preview}\n")

    print(f"✓ Wrote duplicate analysis to {output_file}")


def main():
    """Main entry point."""

    # Parse arguments
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    else:
        project_root = Path(__file__).parent.parent
        input_file = project_root / "data" / "intermediate" / "en" / "wikt.jsonl"

    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = input_file.parent

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        print("Run 'make build-wiktionary-json' first to extract Wiktionary data.")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Input:  {input_file}")
    print(f"Output: {output_dir}/")
    print()

    # Step 1: Analyze duplicates
    word_to_lines, ordered_words = analyze_duplicates(input_file)

    print(f"\nFound {len(ordered_words):,} unique words")
    print(f"Total entries: {sum(len(lines) for lines in word_to_lines.values()):,}")

    # Step 2: Build mapping structures
    print("\nBuilding mapping structures...")
    entry_offsets, entry_counts = build_mapping_structures(word_to_lines, ordered_words)

    # Step 3: Write output files
    print("\nWriting output files...")
    write_mapping_files(entry_offsets, entry_counts, output_dir)

    # Step 4: Write analysis
    analysis_file = output_dir / "duplicate_analysis.txt"
    write_duplicate_analysis(word_to_lines, analysis_file)

    # Summary
    print("\n" + "=" * 80)
    print("MAPPING COMPLETE")
    print("=" * 80)
    print(f"Unique words:           {len(ordered_words):>12,}")
    print(f"Multi-entry words:      {len(entry_counts):>12,} ({len(entry_counts) / len(ordered_words) * 100:.1f}%)")
    print(f"Total storage overhead: {(len(entry_offsets) * 4 + Path(output_dir / 'entry_counts.json').stat().st_size) / (1024*1024):>11.2f} MB")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
