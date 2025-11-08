#!/usr/bin/env python3
"""
export_wordlist_filtered.py - Export wordlist with phrase filtering

Exports trie to plain text with configurable filters to exclude
very long multi-word phrases while retaining useful idioms.
"""
import marisa_trie
import argparse
from pathlib import Path


def filter_word(word: str, max_words: int = None, max_chars: int = None) -> bool:
    """
    Determine if word should be included based on filters.

    Args:
        word: The word/phrase to check
        max_words: Maximum number of space-separated words (None = no limit)
        max_chars: Maximum character length (None = no limit)

    Returns:
        True if word should be included, False if filtered out
    """
    if max_words is not None:
        word_count = word.count(' ') + 1
        if word_count > max_words:
            return False

    if max_chars is not None:
        if len(word) > max_chars:
            return False

    return True


def export_filtered_wordlist(
    trie_path: Path,
    output_path: Path,
    max_words: int = None,
    max_chars: int = None,
    verbose: bool = False
) -> tuple:
    """
    Export trie to plain text with filters.

    Returns:
        (total_words, kept_words, filtered_words)
    """
    # Load trie
    trie = marisa_trie.Trie()
    trie.load(str(trie_path))

    # Get all words
    all_words = list(trie)
    total = len(all_words)

    # Apply filters
    kept_words = []
    filtered_words = []

    for word in all_words:
        if filter_word(word, max_words, max_chars):
            kept_words.append(word)
        else:
            filtered_words.append(word)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for word in kept_words:
            f.write(word + '\n')

    return total, len(kept_words), len(filtered_words)


def main():
    parser = argparse.ArgumentParser(
        description='Export trie to plain text with phrase filtering'
    )

    parser.add_argument(
        '--distribution',
        choices=['core', 'plus'],
        default='plus',
        help='Which distribution to export (default: plus)'
    )

    parser.add_argument(
        '--max-words',
        type=int,
        default=None,
        help='Maximum number of words in a phrase (e.g., 3 for "kick the bucket")'
    )

    parser.add_argument(
        '--max-chars',
        type=int,
        default=None,
        help='Maximum character length (e.g., 50 to exclude long proverbs)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path (default: data/build/{dist}/wordlist.filtered.txt)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show filtered words'
    )

    args = parser.parse_args()

    # Determine paths
    dist = args.distribution
    trie_path = Path(f'data/build/{dist}/{dist}.trie')

    if args.output:
        output_path = Path(args.output)
    else:
        if args.max_words or args.max_chars:
            suffix = []
            if args.max_words:
                suffix.append(f'w{args.max_words}')
            if args.max_chars:
                suffix.append(f'c{args.max_chars}')
            suffix_str = '-'.join(suffix)
            output_path = Path(f'data/build/{dist}/wordlist-{suffix_str}.txt')
        else:
            output_path = Path(f'data/build/{dist}/wordlist.txt')

    if not trie_path.exists():
        print(f"✗ Trie not found: {trie_path}")
        print(f"  Run 'make build-{dist}' first")
        return 1

    print(f"Exporting {dist} wordlist with filters:")
    if args.max_words:
        print(f"  - Max words: {args.max_words}")
    if args.max_chars:
        print(f"  - Max chars: {args.max_chars}")
    if not args.max_words and not args.max_chars:
        print(f"  - No filters (exporting all)")
    print()

    # Export
    total, kept, filtered = export_filtered_wordlist(
        trie_path,
        output_path,
        args.max_words,
        args.max_chars,
        args.verbose
    )

    # Report
    print(f"✓ Exported to {output_path}")
    print()
    print(f"Total words:     {total:,}")
    print(f"Kept:            {kept:,} ({kept/total*100:.2f}%)")
    print(f"Filtered:        {filtered:,} ({filtered/total*100:.2f}%)")

    if args.verbose and filtered > 0:
        print()
        print("Filtered words:")
        # Load filtered words for display
        trie = marisa_trie.Trie()
        trie.load(str(trie_path))

        all_words = list(trie)
        filtered_list = [
            w for w in all_words
            if not filter_word(w, args.max_words, args.max_chars)
        ]

        # Show up to 50 examples
        for word in filtered_list[:50]:
            word_count = word.count(' ') + 1
            print(f"  [{len(word)} chars, {word_count} words] {word}")

        if len(filtered_list) > 50:
            print(f"  ... and {len(filtered_list) - 50} more")

    return 0


if __name__ == '__main__':
    exit(main())
