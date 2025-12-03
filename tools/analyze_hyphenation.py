#!/usr/bin/env python3
"""
Analyze hyphenation templates in Wiktionary dump.

Checks for:
1. Hyphenation template usage patterns
2. Edge cases our scanner might miss
3. Potential bugs in Wiktionary data (incomplete entries)

Usage:
    uv run python tools/analyze_hyphenation.py INPUT.xml.bz2 [--limit N]
"""

import argparse
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Import infrastructure from existing scanner
from wiktionary_scanner_parser import BZ2StreamReader, scan_pages

# Patterns
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')

# Hyphenation template: {{hyphenation|en|...}} or {{hyph|en|...}}
HYPH_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}', re.IGNORECASE)


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


def analyze_hyph_template(content: str, word: str) -> dict:
    """Analyze a single hyphenation template content."""
    result = {
        'word': word,
        'raw': content,
        'has_alternatives': '||' in content,
        'has_params': '=' in content,
        'syllable_count': 0,
        'syllables': [],
        'issues': [],
    }

    # Handle alternatives - use first
    alternatives = content.split('||')
    first_alt = alternatives[0]

    # Parse parts
    parts = first_alt.split('|')
    syllables = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '=' in part:
            continue
        syllables.append(part)

    result['syllables'] = syllables
    result['syllable_count'] = len(syllables)

    # Check for issues
    if len(syllables) == 1 and len(syllables[0]) > 3:
        result['issues'].append('single_unseparated_long_word')

    if len(syllables) == 0:
        result['issues'].append('empty_template')

    # Check if syllables when joined match the word
    joined = ''.join(syllables).lower()
    word_lower = word.lower().replace('-', '').replace(' ', '')
    if joined and joined != word_lower:
        result['issues'].append(f'mismatch: {joined} vs {word_lower}')

    return result


def main():
    parser = argparse.ArgumentParser(description='Analyze hyphenation templates')
    parser.add_argument('input', type=Path, help='Input XML file (.xml.bz2)')
    parser.add_argument('--limit', type=int, help='Limit number of pages')
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing hyphenation in: {args.input}")
    if args.limit:
        print(f"Limit: {args.limit:,} pages")
    print()

    # Counters
    pages_processed = 0
    english_pages = 0
    pages_with_hyph = 0
    template_count = 0

    # Issue tracking
    issue_counts = Counter()
    issue_examples = defaultdict(list)

    # Syllable count distribution
    syllable_dist = Counter()

    start_time = time.time()

    if str(args.input).endswith('.bz2'):
        file_obj = BZ2StreamReader(args.input, chunk_size=256 * 1024)
    else:
        file_obj = open(args.input, 'rb')

    with file_obj as f:
        for page_xml in scan_pages(f):
            pages_processed += 1

            if pages_processed % 100000 == 0:
                elapsed = time.time() - start_time
                rate = pages_processed / elapsed
                print(f"  {pages_processed:,} pages, {english_pages:,} English, "
                      f"{pages_with_hyph:,} with hyphenation, {rate:.0f} pages/sec")

            if args.limit and pages_processed >= args.limit:
                break

            ns_match = NS_PATTERN.search(page_xml)
            if ns_match and int(ns_match.group(1)) != 0:
                continue

            title_match = TITLE_PATTERN.search(page_xml)
            if not title_match:
                continue
            word = title_match.group(1)

            text_match = TEXT_PATTERN.search(page_xml)
            if not text_match:
                continue
            text = text_match.group(1)

            english_text = extract_english_section(text)
            if not english_text:
                continue

            english_pages += 1

            # Find all hyphenation templates
            templates = HYPH_TEMPLATE.findall(english_text)
            if templates:
                pages_with_hyph += 1
                template_count += len(templates)

                for content in templates:
                    analysis = analyze_hyph_template(content, word)
                    syllable_dist[analysis['syllable_count']] += 1

                    for issue in analysis['issues']:
                        issue_counts[issue] += 1
                        if len(issue_examples[issue]) < 5:
                            issue_examples[issue].append({
                                'word': word,
                                'syllables': analysis['syllables'],
                                'raw': content[:100],
                            })

    elapsed = time.time() - start_time

    # Output results
    print()
    print("=" * 70)
    print(f"Pages processed: {pages_processed:,}")
    print(f"English pages: {english_pages:,}")
    print(f"Pages with hyphenation: {pages_with_hyph:,} ({100*pages_with_hyph/english_pages:.1f}%)")
    print(f"Total templates: {template_count:,}")
    print(f"Time: {elapsed:.1f}s")
    print("=" * 70)

    print()
    print("=== SYLLABLE COUNT DISTRIBUTION ===")
    for count in sorted(syllable_dist.keys()):
        pct = 100 * syllable_dist[count] / template_count
        print(f"  {count} syllables: {syllable_dist[count]:,} ({pct:.1f}%)")

    print()
    print("=== POTENTIAL ISSUES ===")
    for issue, count in issue_counts.most_common():
        print(f"\n{issue}: {count:,} occurrences")
        for ex in issue_examples[issue]:
            print(f"  - {ex['word']!r}: {ex['syllables']} (raw: {ex['raw']})")


if __name__ == '__main__':
    main()
