#!/usr/bin/env python3
"""
wikt_entry_lookup.py - Lookup entries using the word-to-entry offset mapping

Demonstrates how to use the sparse offset table to efficiently retrieve
entries for a given word ordinal from the trie.

Usage:
    # Lookup by word ordinal
    python tools/wikt_entry_lookup.py --ordinal 1234

    # Lookup by word string
    python tools/wikt_entry_lookup.py --word "example"

    # Interactive mode
    python tools/wikt_entry_lookup.py --interactive

Arguments:
    --ordinal N        Lookup word at ordinal position N
    --word WORD        Lookup entries for WORD (requires building word index)
    --interactive      Interactive lookup mode
    --data-dir DIR     Directory containing mapping files (default: data/intermediate/)
    --entries FILE     Path to wikt.jsonl (default: data/intermediate/en-wikt.jsonl)
"""

import json
import struct
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


class EntryMapper:
    """Efficient entry lookup using sparse offset tables."""

    def __init__(self, data_dir: Path, entries_file: Path):
        """
        Initialize mapper by loading offset and line list data.

        Args:
            data_dir: Directory containing entry_offsets.bin and entry_line_lists.json
            entries_file: Path to wikt.jsonl file
        """
        self.data_dir = data_dir
        self.entries_file = entries_file

        # Load offsets (binary)
        offsets_file = data_dir / "entry_offsets.bin"
        with open(offsets_file, 'rb') as f:
            offset_data = f.read()
            self.entry_offsets = struct.unpack(f'<{len(offset_data) // 4}I', offset_data)

        # Load sparse line lists (JSON)
        lists_file = data_dir / "entry_line_lists.json"
        with open(lists_file, 'r', encoding='utf-8') as f:
            raw_lists = json.load(f)
            # Convert string keys back to integers
            self.entry_line_lists = {int(k): v for k, v in raw_lists.items()}

        # Cache for random access to entries file
        self._entries_cache: Dict[int, Any] = {}
        self._entries_file_handle: Optional[Any] = None
        self._line_offsets: Optional[List[int]] = None

        print(f"Loaded mapping for {len(self.entry_offsets):,} words")
        print(f"Multi-entry words: {len(self.entry_line_lists):,}")

    def _build_line_index(self):
        """Build index of file offsets for each line (for random access)."""
        if self._line_offsets is not None:
            return

        print("Building line index...", end='', flush=True)
        self._line_offsets = [0]  # Line 0 starts at byte 0

        with open(self.entries_file, 'rb') as f:
            while f.readline():
                self._line_offsets.append(f.tell())

        print(f" done ({len(self._line_offsets) - 1:,} lines)")

    def get_entry_count(self, word_ordinal: int) -> int:
        """
        Get number of entries for a word.

        Args:
            word_ordinal: Trie ordinal for the word

        Returns:
            Number of entries (default 1 for single-entry words)
        """
        if word_ordinal < 0 or word_ordinal >= len(self.entry_offsets):
            raise ValueError(f"Invalid word ordinal: {word_ordinal}")

        # Multi-entry words have explicit line lists
        if word_ordinal in self.entry_line_lists:
            return len(self.entry_line_lists[word_ordinal])
        else:
            return 1

    def get_entries(self, word_ordinal: int) -> List[Dict[str, Any]]:
        """
        Get all entries for a word ordinal.

        Args:
            word_ordinal: Trie ordinal for the word

        Returns:
            List of entry dictionaries
        """
        if word_ordinal < 0 or word_ordinal >= len(self.entry_offsets):
            raise ValueError(f"Invalid word ordinal: {word_ordinal}")

        # Build line index if needed
        self._build_line_index()

        # Get line numbers to read
        if word_ordinal in self.entry_line_lists:
            # Multi-entry word: use explicit line list
            line_numbers = self.entry_line_lists[word_ordinal]
        else:
            # Single-entry word: use offset directly
            line_numbers = [self.entry_offsets[word_ordinal]]

        # Read entries
        entries = []
        with open(self.entries_file, 'r', encoding='utf-8') as f:
            for line_num in line_numbers:
                # Seek to line
                f.seek(self._line_offsets[line_num])
                line = f.readline()

                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)

        return entries

    def get_word_ordinal(self, word: str) -> Optional[int]:
        """
        Find ordinal for a word (requires scanning entries file).

        This is slower than lookup by ordinal. In production, you'd use
        the trie to get the ordinal first.

        Args:
            word: Word string to find

        Returns:
            Ordinal if found, None otherwise
        """
        # Build reverse index if needed
        if not hasattr(self, '_word_to_ordinal'):
            print("Building word-to-ordinal index...", end='', flush=True)
            self._word_to_ordinal = {}

            with open(self.entries_file, 'r', encoding='utf-8') as f:
                seen_words = set()
                ordinal = 0

                for line_num, line in enumerate(f):
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        w = entry.get('word')

                        if w and w not in seen_words:
                            self._word_to_ordinal[w] = ordinal
                            seen_words.add(w)
                            ordinal += 1

                    except json.JSONDecodeError:
                        continue

            print(f" done ({len(self._word_to_ordinal):,} words)")

        return self._word_to_ordinal.get(word)


def format_entry(entry: Dict[str, Any], index: int = 0) -> str:
    """Format an entry for display."""
    lines = []

    if index > 0:
        lines.append(f"\n--- Entry {index + 1} ---")

    word = entry.get('word', '?')
    pos = entry.get('pos', [])
    labels = entry.get('labels', {})

    lines.append(f"Word: {word}")

    if pos:
        lines.append(f"POS:  {', '.join(pos)}")

    # Labels
    for label_type in ['register', 'temporal', 'domain', 'region']:
        if label_type in labels and labels[label_type]:
            vals = labels[label_type]
            lines.append(f"{label_type.capitalize()}: {', '.join(vals)}")

    # Boolean flags
    flags = []
    for flag in ['is_vulgar', 'is_archaic', 'is_rare', 'is_informal', 'is_technical', 'is_regional']:
        if entry.get(flag):
            flags.append(flag.replace('is_', ''))

    if flags:
        lines.append(f"Flags: {', '.join(flags)}")

    # Syllables
    syllables = entry.get('syllables')
    if syllables:
        lines.append(f"Syllables: {syllables}")

    # Morphology
    morphology = entry.get('morphology', {})
    if morphology:
        morph_parts = []
        if morphology.get('is_compound'):
            morph_parts.append("compound")
        morph_type = morphology.get('type')
        if morph_type:
            morph_parts.append(f"type={morph_type}")

        if morph_parts:
            lines.append(f"Morphology: {', '.join(morph_parts)}")

    return '\n'.join(lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Lookup Wiktionary entries using sparse offset mapping'
    )
    parser.add_argument('--ordinal', type=int, help='Word ordinal to lookup')
    parser.add_argument('--word', type=str, help='Word string to lookup')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    parser.add_argument('--data-dir', type=Path,
                        default=Path('data/intermediate'),
                        help='Directory with mapping files')
    parser.add_argument('--entries', type=Path,
                        default=Path('data/intermediate/en-wikt.jsonl'),
                        help='Path to wikt.jsonl')

    args = parser.parse_args()

    # Check files exist
    if not args.entries.exists():
        print(f"Error: Entries file not found: {args.entries}")
        print("Run 'make build-wiktionary-json' first.")
        return 1

    offsets_file = args.data_dir / "entry_offsets.bin"
    if not offsets_file.exists():
        print(f"Error: Mapping files not found in {args.data_dir}/")
        print("Run 'python tools/wikt_entry_mapper.py' first to build mapping.")
        return 1

    # Initialize mapper
    print(f"Loading mapping from {args.data_dir}/")
    mapper = EntryMapper(args.data_dir, args.entries)
    print()

    # Interactive mode
    if args.interactive:
        print("Interactive lookup mode (type 'quit' to exit)")
        print("Commands:")
        print("  ordinal N    - Lookup by ordinal")
        print("  word WORD    - Lookup by word string")
        print("  quit         - Exit")
        print()

        while True:
            try:
                cmd = input("> ").strip()

                if cmd == 'quit':
                    break

                parts = cmd.split(maxsplit=1)
                if len(parts) != 2:
                    print("Invalid command. Use: ordinal N  or  word WORD")
                    continue

                cmd_type, arg = parts

                if cmd_type == 'ordinal':
                    ordinal = int(arg)
                    entries = mapper.get_entries(ordinal)

                    print(f"\nFound {len(entries)} entry/entries for ordinal {ordinal}:")
                    for i, entry in enumerate(entries):
                        print(format_entry(entry, i))
                    print()

                elif cmd_type == 'word':
                    word = arg
                    ordinal = mapper.get_word_ordinal(word)

                    if ordinal is None:
                        print(f"Word '{word}' not found")
                    else:
                        entries = mapper.get_entries(ordinal)
                        print(f"\nFound {len(entries)} entry/entries for '{word}' (ordinal {ordinal}):")
                        for i, entry in enumerate(entries):
                            print(format_entry(entry, i))
                    print()

                else:
                    print("Unknown command. Use: ordinal N  or  word WORD")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

        return 0

    # Single lookup mode
    if args.ordinal is not None:
        ordinal = args.ordinal
        entries = mapper.get_entries(ordinal)

        print(f"Lookup ordinal {ordinal}:")
        print(f"Found {len(entries)} entry/entries:\n")

        for i, entry in enumerate(entries):
            print(format_entry(entry, i))

    elif args.word is not None:
        word = args.word
        ordinal = mapper.get_word_ordinal(word)

        if ordinal is None:
            print(f"Word '{word}' not found")
            return 1

        entries = mapper.get_entries(ordinal)
        print(f"Lookup word '{word}' (ordinal {ordinal}):")
        print(f"Found {len(entries)} entry/entries:\n")

        for i, entry in enumerate(entries):
            print(format_entry(entry, i))

    else:
        parser.print_help()
        print("\nError: Must specify --ordinal, --word, or --interactive")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
