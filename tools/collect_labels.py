#!/usr/bin/env python3
"""
Ad-hoc label collector: Scans Wiktionary dump to collect ALL unique labels
from {{lb|en|...}} and {{label|en|...}} templates in English sections.

This helps us discover what grammatical labels are actually used in Wiktionary
and prioritize which label → category mappings to port.

Usage:
    uv run python tools/collect_labels.py INPUT.xml.bz2 [--limit N]
"""

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path

# Import infrastructure from scanner package
from wiktionary_scanner_python.scanner import BZ2StreamReader, scan_pages

# Patterns for extraction
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')

# Label templates: {{lb|en|label1|label2|...}} or {{label|en|...}}
# Also {{lbl|en|...}} as alias
LABEL_TEMPLATE = re.compile(
    r'\{\{(?:lb|label|lbl)\|en\|([^}]+)\}\}',
    re.IGNORECASE
)

# Context templates: {{cx|en|...}} - older format
CONTEXT_TEMPLATE = re.compile(
    r'\{\{cx\|en\|([^}]+)\}\}',
    re.IGNORECASE
)


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


def extract_labels(text: str) -> list[str]:
    """Extract all labels from template calls."""
    labels = []

    for pattern in [LABEL_TEMPLATE, CONTEXT_TEMPLATE]:
        for match in pattern.finditer(text):
            params = match.group(1)
            # Split by pipe, normalize
            for param in params.split('|'):
                param = param.strip().lower()
                # Skip empty, underscores (connectors), and named params
                if param and param != '_' and '=' not in param:
                    labels.append(param)

    return labels


def main():
    parser = argparse.ArgumentParser(description='Collect all labels from Wiktionary dump')
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
    label_counts = Counter()

    pages_processed = 0
    english_pages = 0
    pages_with_labels = 0
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
                      f"{pages_with_labels:,} with labels, {rate:.0f} pages/sec")

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

            # Collect labels
            labels = extract_labels(english_text)
            if labels:
                pages_with_labels += 1
                for label in labels:
                    label_counts[label] += 1

    elapsed = time.time() - start_time

    # Output results
    print()
    print("=" * 70)
    print(f"Pages processed: {pages_processed:,}")
    print(f"English pages: {english_pages:,}")
    print(f"Pages with labels: {pages_with_labels:,}")
    print(f"Unique labels: {len(label_counts):,}")
    print(f"Time: {elapsed:.1f}s ({pages_processed / elapsed:.0f} pages/sec)")
    print("=" * 70)

    print()
    print("=== TOP 100 LABELS (from {{lb|en|...}}) ===")
    print()
    for label, count in label_counts.most_common(100):
        print(f"  {count:8,}  {label}")

    print()
    print("=== GRAMMATICALLY INTERESTING LABELS ===")
    print()
    interesting = [
        'transitive', 'intransitive', 'ambitransitive', 'ditransitive',
        'countable', 'uncountable', 'comparable', 'not comparable',
        'plural only', 'singular only', 'usually plural', 'usually singular',
        'auxiliary', 'modal', 'copulative', 'reflexive', 'reciprocal',
        'impersonal', 'ergative', 'stative', 'causative', 'inchoative',
        'abbreviation', 'acronym', 'initialism',
        'collective', 'abstract', 'concrete',
    ]
    for label in interesting:
        if label in label_counts:
            print(f"  {label_counts[label]:8,}  {label}")


if __name__ == '__main__':
    main()
