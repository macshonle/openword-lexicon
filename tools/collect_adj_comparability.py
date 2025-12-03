#!/usr/bin/env python3
"""
Ad-hoc scanner: Collects adjective comparability patterns from Wiktionary dump.

Scans for {{en-adj}}, {{en-adv}} templates to find:
- Uncomparable adjectives/adverbs (first param is "-")
- Comparative-only forms (componly parameter)
- Superlative-only forms (suponly parameter)
- Regular comparable forms

This helps us understand the distribution and prioritize implementation.

Usage:
    uv run python tools/collect_adj_comparability.py INPUT.xml.bz2 [--limit N]
"""

import argparse
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Import infrastructure from scanner package
from wiktionary_scanner_python.scanner import BZ2StreamReader, scan_pages

# Patterns for extraction
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\\s*==$', re.MULTILINE)
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')

# Templates for adjectives and adverbs
# {{en-adj|...}} or {{en-adv|...}}
EN_ADJ_TEMPLATE = re.compile(
    r'\{\{en-adj\|([^}]*)\}\}',
    re.IGNORECASE
)
EN_ADV_TEMPLATE = re.compile(
    r'\{\{en-adv\|([^}]*)\}\}',
    re.IGNORECASE
)


def extract_english_section(text: str) -> str | None:
    """Extract just the English section from page text."""
    match = ENGLISH_SECTION.search(text)
    if not match:
        return None

    start = match.end()

    for lang_match in LANGUAGE_SECTION.finditer(text[start:]):
        lang = lang_match.group(1).strip()
        if lang.lower() != 'english':
            return text[start:start + lang_match.start()]

    return text[start:]


def analyze_adj_template(params: str) -> dict:
    """
    Analyze parameters of {{en-adj}} or {{en-adv}} template.

    Returns dict with keys:
    - uncomparable: True if first param is "-" and no other forms
    - componly: True if componly parameter is present
    - suponly: True if suponly parameter is present
    - comparable: True if has comparative forms
    - params: raw params string
    """
    result = {
        'uncomparable': False,
        'componly': False,
        'suponly': False,
        'comparable': False,
        'has_more': False,
        'has_suffix': False,
        'params': params,
    }

    # Split by pipe
    parts = params.split('|')

    positional = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for named parameters
        if '=' in part:
            key = part.split('=')[0].strip().lower()
            if key == 'componly':
                result['componly'] = True
            elif key == 'suponly':
                result['suponly'] = True
            continue

        # Positional parameter
        positional.append(part)

    # First positional is the comparative form indicator
    if positional:
        first = positional[0]
        if first == '-':
            # Check if there are more positional args (not uncomparable then)
            if len(positional) == 1:
                result['uncomparable'] = True
            else:
                # Has "-" but also other comparatives
                result['comparable'] = True
        elif first == '+' or first == 'more':
            result['has_more'] = True
            result['comparable'] = True
        elif first == 'er' or first.endswith('er'):
            result['has_suffix'] = True
            result['comparable'] = True
        else:
            result['comparable'] = True

    return result


def main():
    parser = argparse.ArgumentParser(description='Collect adjective comparability patterns')
    parser.add_argument('input', type=Path, help='Input XML file (.xml.bz2)')
    parser.add_argument('--limit', type=int, help='Limit number of pages to process')
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {args.input}")
    if args.limit:
        print(f"Limit: {args.limit:,} pages")
    print()

    # Counters
    pages_processed = 0
    english_pages = 0

    adj_stats = {
        'total': 0,
        'uncomparable': 0,
        'componly': 0,
        'suponly': 0,
        'comparable': 0,
        'has_more': 0,
        'has_suffix': 0,
    }

    adv_stats = {
        'total': 0,
        'uncomparable': 0,
        'componly': 0,
        'suponly': 0,
        'comparable': 0,
        'has_more': 0,
        'has_suffix': 0,
    }

    # Examples
    examples = defaultdict(list)

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
            if pages_processed % 100000 == 0:
                elapsed = time.time() - start_time
                rate = pages_processed / elapsed
                print(f"  {pages_processed:,} pages, {english_pages:,} English, "
                      f"{adj_stats['total']:,} adj, {adv_stats['total']:,} adv, {rate:.0f} pages/sec")

            # Check limit
            if args.limit and pages_processed >= args.limit:
                break

            # Skip non-main namespace
            ns_match = NS_PATTERN.search(page_xml)
            if ns_match and int(ns_match.group(1)) != 0:
                continue

            # Extract title
            title_match = TITLE_PATTERN.search(page_xml)
            if not title_match:
                continue
            word = title_match.group(1)

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

            # Find adjective templates
            for match in EN_ADJ_TEMPLATE.finditer(english_text):
                params = match.group(1)
                analysis = analyze_adj_template(params)

                adj_stats['total'] += 1
                if analysis['uncomparable']:
                    adj_stats['uncomparable'] += 1
                    if len(examples['adj_uncomparable']) < 5:
                        examples['adj_uncomparable'].append((word, params))
                if analysis['componly']:
                    adj_stats['componly'] += 1
                    if len(examples['adj_componly']) < 5:
                        examples['adj_componly'].append((word, params))
                if analysis['suponly']:
                    adj_stats['suponly'] += 1
                    if len(examples['adj_suponly']) < 5:
                        examples['adj_suponly'].append((word, params))
                if analysis['comparable']:
                    adj_stats['comparable'] += 1
                if analysis['has_more']:
                    adj_stats['has_more'] += 1
                if analysis['has_suffix']:
                    adj_stats['has_suffix'] += 1

            # Find adverb templates
            for match in EN_ADV_TEMPLATE.finditer(english_text):
                params = match.group(1)
                analysis = analyze_adj_template(params)

                adv_stats['total'] += 1
                if analysis['uncomparable']:
                    adv_stats['uncomparable'] += 1
                    if len(examples['adv_uncomparable']) < 5:
                        examples['adv_uncomparable'].append((word, params))
                if analysis['componly']:
                    adv_stats['componly'] += 1
                    if len(examples['adv_componly']) < 5:
                        examples['adv_componly'].append((word, params))
                if analysis['suponly']:
                    adv_stats['suponly'] += 1
                    if len(examples['adv_suponly']) < 5:
                        examples['adv_suponly'].append((word, params))
                if analysis['comparable']:
                    adv_stats['comparable'] += 1
                if analysis['has_more']:
                    adv_stats['has_more'] += 1
                if analysis['has_suffix']:
                    adv_stats['has_suffix'] += 1

    elapsed = time.time() - start_time

    # Output results
    print()
    print("=" * 70)
    print(f"Pages processed: {pages_processed:,}")
    print(f"English pages: {english_pages:,}")
    print(f"Time: {elapsed:.1f}s ({pages_processed / elapsed:.0f} pages/sec)")
    print("=" * 70)

    print()
    print("=== ADJECTIVE COMPARABILITY ({{en-adj}}) ===")
    print(f"  Total templates: {adj_stats['total']:,}")
    print(f"  Uncomparable (-): {adj_stats['uncomparable']:,}")
    print(f"  Comparative-only: {adj_stats['componly']:,}")
    print(f"  Superlative-only: {adj_stats['suponly']:,}")
    print(f"  Comparable: {adj_stats['comparable']:,}")
    print(f"    - with 'more': {adj_stats['has_more']:,}")
    print(f"    - with -er suffix: {adj_stats['has_suffix']:,}")

    print()
    print("=== ADVERB COMPARABILITY ({{en-adv}}) ===")
    print(f"  Total templates: {adv_stats['total']:,}")
    print(f"  Uncomparable (-): {adv_stats['uncomparable']:,}")
    print(f"  Comparative-only: {adv_stats['componly']:,}")
    print(f"  Superlative-only: {adv_stats['suponly']:,}")
    print(f"  Comparable: {adv_stats['comparable']:,}")
    print(f"    - with 'more': {adv_stats['has_more']:,}")
    print(f"    - with -er suffix: {adv_stats['has_suffix']:,}")

    print()
    print("=== EXAMPLES ===")
    for key, items in examples.items():
        if items:
            print(f"\n{key}:")
            for word, params in items:
                print(f"  - {word!r}: {{{{en-adj|{params}}}}}")


if __name__ == '__main__':
    main()
