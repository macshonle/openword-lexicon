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

Sections:
  - OVERVIEW: Basic stats (pages processed, English pages, unique counts)
  - HEADERS: All section headers with counts
  - TEMPLATE_POS: POS values from {{head|en|...}} templates
  - CATEGORIES: Categories from [[Category:English ...]]
  - PSEUDO_POS_ONLY: Pages with ONLY pseudo-POS (participle, contraction, letter)
  - UNKNOWN_POS: Pages with headers but no recognized POS
  - PHRASE_TYPES: Individual phrase type counts
  - AGGREGATE_GROUPS: Combined totals for affix, symbol, determiner, determiner/numeral
  - HEADER_TYPOS: Known typos in headers with page lists for wiki editing
"""

import argparse
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

# Import infrastructure from scanner package
from wiktionary_scanner_python.scanner import (
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

# POS Classification Constants
# Real POS headers that represent actual parts of speech
REAL_POS_HEADERS = {
    'noun', 'verb', 'proper noun', 'adjective', 'adverb',
    'interjection', 'prefix', 'suffix', 'pronoun', 'preposition',
    'symbol', 'numeral', 'conjunction', 'determiner', 'particle',
    'punctuation mark', 'infix', 'interfix', 'article',
    'diacritical mark', 'circumfix', 'postposition', 'affix',
    'phrase', 'prepositional phrase', 'proverb', 'idiom',
    'verb phrase', 'adverbial phrase', 'noun phrase',
}

# Pseudo-POS headers that should have a real POS alongside them
PSEUDO_POS_HEADERS = {'participle', 'contraction', 'letter'}

# Individual phrase types (kept separate for analysis)
PHRASE_TYPES = {'phrase', 'prepositional phrase', 'proverb', 'idiom'}

# Aggregate groupings for analysis
AFFIX_TYPES = {'prefix', 'suffix', 'infix', 'interfix', 'circumfix', 'affix'}
SYMBOL_TYPES = {'symbol', 'punctuation mark', 'diacritical mark'}
DETERMINER_TYPES = {'determiner', 'article'}
DETERMINER_NUMERAL_TYPES = {'determiner', 'article', 'numeral'}

# Known typos/variants in section headers: {typo: likely_intended}
HEADER_TYPOS = {
    'pronounciation': 'pronunciation',
    'pronuciation': 'pronunciation',
    'pronuncation': 'pronunciation',
    'pronunciaation': 'pronunciation',
    'tranlsations': 'translations',
    'coordiante terms': 'coordinate terms',
    'synoynms': 'synonyms',
    'hyopernyms': 'hypernyms',
    'relatd terms': 'related terms',
    'alterative forms': 'alternative forms',
    'alernative forms': 'alternative forms',
    'eymology': 'etymology',
    'etymologyp': 'etymology',
    'proerp noun': 'proper noun',
}

# Maximum samples to retain per category
MAX_SAMPLES = 20


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

    # Per-page POS tracking for analysis
    # Track counts and samples for relevant categories (memory-efficient)
    pseudo_pos_only_counts = {pos: 0 for pos in PSEUDO_POS_HEADERS}
    pseudo_pos_only_samples = {pos: [] for pos in PSEUDO_POS_HEADERS}
    unknown_pos_count = 0
    unknown_pos_samples = []  # Pages with headers but no recognized POS

    # Typo tracking: {typo: [list of page titles]}
    typo_pages = {typo: [] for typo in HEADER_TYPOS}

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

            # Extract page title for sample tracking
            title_match = TITLE_PATTERN.search(page_xml)
            title = title_match.group(1) if title_match else f"page_{pages_processed}"

            # Collect headers (normalized to lowercase) - both global and per-page
            page_headers = set()
            for match in ALL_HEADERS.finditer(english_text):
                header = match.group(1).strip().lower()
                header = ' '.join(header.split())  # Normalize whitespace
                header_counts[header] += 1
                page_headers.add(header)

            # Analyze this page's POS headers
            has_real_pos = bool(page_headers & REAL_POS_HEADERS)
            has_pseudo_pos = bool(page_headers & PSEUDO_POS_HEADERS)

            # Track pages with ONLY pseudo-POS (no real POS)
            if has_pseudo_pos and not has_real_pos:
                for pseudo in PSEUDO_POS_HEADERS:
                    if pseudo in page_headers:
                        pseudo_pos_only_counts[pseudo] += 1
                        if len(pseudo_pos_only_samples[pseudo]) < MAX_SAMPLES:
                            pseudo_pos_only_samples[pseudo].append(title)

            # Track pages with headers but no recognized POS at all
            if page_headers and not has_real_pos and not has_pseudo_pos:
                unknown_pos_count += 1
                if len(unknown_pos_samples) < MAX_SAMPLES:
                    unknown_pos_samples.append(title)

            # Track pages with typo headers
            for typo in HEADER_TYPOS:
                if typo in page_headers:
                    typo_pages[typo].append(title)

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

    # Compute derived analysis data
    aggregate_totals = compute_aggregate_totals(header_counts)
    phrase_type_counts = extract_phrase_type_counts(header_counts)

    print()
    print("=== PSEUDO-POS ONLY ENTRIES ===")
    print("(Pages with ONLY pseudo-POS headers, no real POS)")
    for pseudo in sorted(PSEUDO_POS_HEADERS):
        count = pseudo_pos_only_counts[pseudo]
        samples = pseudo_pos_only_samples[pseudo]
        print(f"  {pseudo}: {count:,} pages")
        if samples:
            print(f"    Samples: {', '.join(samples[:10])}")

    print()
    print("=== UNKNOWN POS ENTRIES ===")
    print("(Pages with headers but no recognized POS)")
    print(f"  Count: {unknown_pos_count:,}")
    if unknown_pos_samples:
        print(f"  Samples: {', '.join(unknown_pos_samples[:10])}")

    print()
    print("=== PHRASE TYPE BREAKDOWN ===")
    for phrase_type in sorted(PHRASE_TYPES):
        print(f"  {phrase_type}: {phrase_type_counts[phrase_type]:,}")

    print()
    print("=== AGGREGATE GROUPINGS ===")
    print(f"  Affix (prefix, suffix, infix, interfix, circumfix, affix): {aggregate_totals['affix_total']:,}")
    print(f"  Symbol (symbol, punctuation mark, diacritical mark): {aggregate_totals['symbol_total']:,}")
    print(f"  Determiner (determiner, article): {aggregate_totals['determiner_total']:,}")
    print(f"  Determiner/Numeral (determiner, article, numeral): {aggregate_totals['determiner_numeral_total']:,}")

    print()
    print("=== HEADER TYPOS ===")
    typos_found = [(typo, pages) for typo, pages in typo_pages.items() if pages]
    if typos_found:
        for typo, pages in sorted(typos_found, key=lambda x: -len(x[1])):
            intended = HEADER_TYPOS[typo]
            print(f"  {typo} -> {intended}: {len(pages)} pages")
            print(f"    Pages: {', '.join(pages[:10])}")
    else:
        print("  (none found)")

    # Write machine-readable stats file if requested
    if args.stats_output:
        write_stats_file(
            args.stats_output,
            pages_processed=pages_processed,
            english_pages=english_pages,
            header_counts=header_counts,
            template_counts=template_counts,
            category_counts=category_counts,
            pseudo_pos_only_counts=pseudo_pos_only_counts,
            pseudo_pos_only_samples=pseudo_pos_only_samples,
            unknown_pos_count=unknown_pos_count,
            unknown_pos_samples=unknown_pos_samples,
            aggregate_totals=aggregate_totals,
            phrase_type_counts=phrase_type_counts,
            typo_pages=typo_pages,
        )
        print()
        print(f"Stats written to: {args.stats_output}")


def compute_aggregate_totals(header_counts: Counter) -> dict:
    """Compute aggregate totals for POS groupings."""
    def sum_group(group):
        return sum(header_counts.get(pos, 0) for pos in group)

    return {
        'affix_total': sum_group(AFFIX_TYPES),
        'symbol_total': sum_group(SYMBOL_TYPES),
        'determiner_total': sum_group(DETERMINER_TYPES),
        'determiner_numeral_total': sum_group(DETERMINER_NUMERAL_TYPES),
    }


def extract_phrase_type_counts(header_counts: Counter) -> dict:
    """Extract counts for each phrase type."""
    return {pt: header_counts.get(pt, 0) for pt in PHRASE_TYPES}


def write_stats_file(
    output_path: Path,
    pages_processed: int,
    english_pages: int,
    header_counts: Counter,
    template_counts: Counter,
    category_counts: Counter,
    pseudo_pos_only_counts: dict,
    pseudo_pos_only_samples: dict,
    unknown_pos_count: int,
    unknown_pos_samples: list,
    aggregate_totals: dict,
    phrase_type_counts: dict,
    typo_pages: dict,
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

        # Pseudo-POS only entries (pages with ONLY pseudo-POS, no real POS)
        f.write("\n=== PSEUDO_POS_ONLY ===\n")
        for pseudo in sorted(PSEUDO_POS_HEADERS):
            count = pseudo_pos_only_counts[pseudo]
            samples = pseudo_pos_only_samples[pseudo]
            samples_str = ','.join(samples) if samples else ''
            f.write(f"{pseudo}\t{count}\t{samples_str}\n")

        # Unknown POS entries (pages with headers but no recognized POS)
        f.write("\n=== UNKNOWN_POS ===\n")
        f.write(f"count\t{unknown_pos_count}\n")
        if unknown_pos_samples:
            f.write(f"samples\t{','.join(unknown_pos_samples)}\n")

        # Phrase type breakdown
        f.write("\n=== PHRASE_TYPES ===\n")
        for phrase_type in sorted(PHRASE_TYPES):
            f.write(f"{phrase_type}\t{phrase_type_counts[phrase_type]}\n")

        # Aggregate groupings
        f.write("\n=== AGGREGATE_GROUPS ===\n")
        f.write(f"affix\t{aggregate_totals['affix_total']}\n")
        f.write(f"symbol\t{aggregate_totals['symbol_total']}\n")
        f.write(f"determiner\t{aggregate_totals['determiner_total']}\n")
        f.write(f"determiner_numeral\t{aggregate_totals['determiner_numeral_total']}\n")

        # Header typos with page lists
        f.write("\n=== HEADER_TYPOS ===\n")
        for typo in sorted(HEADER_TYPOS.keys()):
            intended = HEADER_TYPOS[typo]
            pages = typo_pages.get(typo, [])
            pages_str = ','.join(pages) if pages else ''
            f.write(f"{typo}\t{intended}\t{len(pages)}\t{pages_str}\n")


if __name__ == '__main__':
    main()
