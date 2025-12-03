#!/usr/bin/env python3
"""
Ad-hoc POS collector: Scans Wiktionary dump to collect ALL unique parts of speech
from English sections - without filtering through POS_MAP.

This helps us discover what POS types actually exist in Wiktionary.

Usage:
    uv run python tools/collect_pos.py INPUT.xml.bz2 [--limit N] [--stats-output FILE]

When --stats-output is provided, writes machine-readable stats to that file
for automated markdown updates. The file format uses sections like:

    === SECTION_NAME ===
    key<TAB>value
    ...

Sections: OVERVIEW, HEADERS, TEMPLATE_POS, CATEGORIES
"""

import argparse
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

# Import infrastructure from existing scanner
from wiktionary_scanner_parser import (
    BZ2StreamReader,
    scan_pages,
    find_head_template_pos_values,  # Proper parsing function
)

# Patterns for extraction
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')

# What we're collecting
ALL_HEADERS = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)
# NOTE: HEAD_TEMPLATE regex is kept for reference but NOT USED
# The old regex-based approach incorrectly captured named params like "head=..."
# Use find_head_template_pos_values() instead for proper bracket-aware parsing
HEAD_TEMPLATE_DEPRECATED = re.compile(r'\{\{(?:head|en-head|head-lite)\|en\|([^}|]+)', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:English\s+([^\]]+)\]\]', re.IGNORECASE)


def extract_english_section(text: str) -> str | None:
    """Extract just the English section from page text."""
    match = ENGLISH_SECTION.search(text)
    if not match:
        return None

    start = match.end()

    # Find next language section
    for lang_match in LANGUAGE_SECTION.finditer(text[start:]):
        lang = lang_match.group(1).strip()
        if lang.lower() != 'english':
            return text[start:start + lang_match.start()]

    return text[start:]


def main():
    parser = argparse.ArgumentParser(description='Collect all POS types from Wiktionary dump')
    parser.add_argument('input', type=Path, help='Input XML file (.xml.bz2)')
    parser.add_argument('--limit', type=int, help='Limit number of pages to process')
    parser.add_argument('--stats-output', type=Path,
                        help='Write machine-readable stats to FILE for markdown updates')
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {args.input}")
    if args.limit:
        print(f"Limit: {args.limit:,} pages")
    print()

    # Counters
    header_counts = Counter()
    template_counts = Counter()
    category_counts = Counter()

    pages_processed = 0
    english_pages = 0
    start_time = time.time()

    # Open file
    if str(args.input).endswith('.bz2'):
        file_obj = BZ2StreamReader(args.input, chunk_size=256 * 1024)
    else:
        file_obj = open(args.input, 'rb')

    with file_obj as f:
        for page_xml in scan_pages(f):
            pages_processed += 1

            # Progress
            if pages_processed % 50000 == 0:
                elapsed = time.time() - start_time
                rate = pages_processed / elapsed
                print(f"  {pages_processed:,} pages, {english_pages:,} English, {rate:.0f} pages/sec")

            # Check limit
            if args.limit and pages_processed >= args.limit:
                break

            # Skip non-main namespace
            ns_match = NS_PATTERN.search(page_xml)
            if ns_match and int(ns_match.group(1)) != 0:
                continue

            # Extract text
            text_match = TEXT_PATTERN.search(page_xml)
            if not text_match:
                continue
            text = text_match.group(1)

            # Extract English section
            english_text = extract_english_section(text)
            if not english_text:
                continue

            english_pages += 1

            # Collect headers (normalized to lowercase)
            for match in ALL_HEADERS.finditer(english_text):
                header = match.group(1).strip().lower()
                header = ' '.join(header.split())  # Normalize whitespace
                header_counts[header] += 1

            # Collect template POS values using PROPER bracket-aware parsing
            # This correctly handles:
            # - Named params like head=... (skips them to find positional POS)
            # - Nested templates {{...}}
            # - Wikilinks [[...]] in parameters
            for pos in find_head_template_pos_values(english_text):
                template_counts[pos] += 1

            # Collect categories
            for match in CATEGORY.finditer(english_text):
                cat = match.group(1).strip()
                category_counts[cat] += 1

    elapsed = time.time() - start_time

    # Output results
    print()
    print("=" * 70)
    print(f"Pages processed: {pages_processed:,}")
    print(f"English pages: {english_pages:,}")
    print(f"Time: {elapsed:.1f}s ({pages_processed / elapsed:.0f} pages/sec)")
    print("=" * 70)

    print()
    print("=== SECTION HEADERS (from ===Header===) ===")
    print(f"Unique headers: {len(header_counts):,}")
    print()
    for header, count in header_counts.most_common():
        print(f"  {count:8,}  {header}")

    print()
    print("=== TEMPLATE POS (from {{head|en|...}}) ===")
    print(f"Unique POS values: {len(template_counts):,}")
    print()
    for pos, count in template_counts.most_common():
        print(f"  {count:8,}  {pos}")

    print()
    print("=== CATEGORIES (from [[Category:English ...]]) ===")
    print(f"Unique categories: {len(category_counts):,}")
    print()
    for cat, count in category_counts.most_common():
        print(f"  {count:8,}  {cat}")

    # Write machine-readable stats file if requested
    if args.stats_output:
        write_stats_file(
            args.stats_output,
            pages_processed=pages_processed,
            english_pages=english_pages,
            header_counts=header_counts,
            template_counts=template_counts,
            category_counts=category_counts,
        )
        print()
        print(f"Stats written to: {args.stats_output}")


def write_stats_file(
    output_path: Path,
    pages_processed: int,
    english_pages: int,
    header_counts: Counter,
    template_counts: Counter,
    category_counts: Counter,
) -> None:
    """
    Write machine-readable stats file for markdown updates.

    Format:
        === SECTION_NAME ===
        key<TAB>value
        ...

    This format is easy to parse with shell tools (grep, awk, sed).
    """
    with open(output_path, 'w') as f:
        # Overview section
        f.write("=== OVERVIEW ===\n")
        f.write(f"last_updated\t{date.today().isoformat()}\n")
        f.write(f"pages_processed\t{pages_processed}\n")
        f.write(f"english_pages\t{english_pages}\n")
        f.write(f"unique_headers\t{len(header_counts)}\n")
        f.write(f"unique_template_pos\t{len(template_counts)}\n")

        # All headers (sorted by count descending)
        f.write("\n=== HEADERS ===\n")
        for header, count in header_counts.most_common():
            f.write(f"{count}\t{header}\n")

        # Template POS values
        f.write("\n=== TEMPLATE_POS ===\n")
        for pos, count in template_counts.most_common():
            f.write(f"{count}\t{pos}\n")

        # Categories
        f.write("\n=== CATEGORIES ===\n")
        for cat, count in category_counts.most_common():
            f.write(f"{count}\t{cat}\n")


if __name__ == '__main__':
    main()
