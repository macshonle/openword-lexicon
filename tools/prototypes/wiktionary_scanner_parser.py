#!/usr/bin/env python3
"""
wiktionary_scanner_parser.py - Lightweight scanner-based Wiktionary parser

Uses simple string scanning to find <page> boundaries instead of full XML
parsing. Much faster than ET.iterparse() for predictable MediaWiki format.

No XML validation, no DOM building, no namespace overhead - just fast
extraction of the data we need.

Usage:
    python wiktionary_scanner_parser.py INPUT.xml.bz2 OUTPUT.jsonl [--limit N]
"""

import bz2
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Optional


class BZ2StreamReader:
    """Streaming BZ2 decompressor with progress feedback."""

    def __init__(self, filepath: Path, chunk_size: int = 256 * 1024):
        self.filepath = filepath
        self.chunk_size = chunk_size
        self.file = open(filepath, 'rb')
        self.decompressor = bz2.BZ2Decompressor()
        self.buffer = b''
        self.total_compressed = 0
        self.total_decompressed = 0
        self.last_progress = 0
        self.start_time = time.time()

    def read(self, size: int = -1) -> bytes:
        """Read decompressed data."""
        if size == -1:
            while not self.decompressor.eof:
                self._decompress_chunk()
            result = self.buffer
            self.buffer = b''
            return result

        while len(self.buffer) < size and not self.decompressor.eof:
            self._decompress_chunk()

        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result

    def _decompress_chunk(self):
        """Decompress one chunk and update progress."""
        if self.decompressor.eof:
            return

        compressed = self.file.read(self.chunk_size)
        if not compressed:
            return

        self.total_compressed += len(compressed)
        decompressed = self.decompressor.decompress(compressed)
        self.buffer += decompressed
        self.total_decompressed += len(decompressed)

        if self.total_decompressed - self.last_progress >= 50 * 1024 * 1024:
            elapsed = time.time() - self.start_time
            rate_mb = (self.total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            elapsed_min = int(elapsed / 60)
            elapsed_sec = int(elapsed % 60)
            print(f"  Decompressing: {self.total_decompressed / (1024*1024):.0f} MB "
                  f"({rate_mb:.1f} MB/s, {elapsed_min}m {elapsed_sec}s elapsed)",
                  end='\r', flush=True)
            self.last_progress = self.total_decompressed

    def finish_progress(self):
        """Print newline to commit final progress line."""
        if self.total_decompressed > 0:
            elapsed = time.time() - self.start_time
            elapsed_min = int(elapsed / 60)
            elapsed_sec = int(elapsed % 60)
            print(f"  Decompression complete: {self.total_decompressed / (1024*1024):.0f} MB "
                  f"in {elapsed_min}m {elapsed_sec}s")
            sys.stdout.flush()

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Regex patterns for extraction
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)
# Fallback: extract POS from {{head|en|POS}} templates when section headers missing
HEAD_TEMPLATE = re.compile(r'\{\{(?:head|en-head)\|en\|([^}|]+)', re.IGNORECASE)
CONTEXT_LABEL = re.compile(r'\{\{(?:lb|label|context)\|en\|([^}]+)\}\}', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:English\s+([^\]]+)\]\]', re.IGNORECASE)

# Simple extraction patterns (no full XML parsing)
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
REDIRECT_PATTERN = re.compile(r'<redirect\s+title="[^"]+"')

# Known special page prefixes (build this list as we discover them)
SPECIAL_PAGE_PREFIXES = (
    'Wiktionary:',
    'Appendix:',
    'Help:',
    'Template:',
    'Reconstruction:',  # Proto-language reconstructions
)

# Regional label patterns
REGION_LABELS = {
    'british': 'en-GB',
    'uk': 'en-GB',
    'us': 'en-US',
    'american': 'en-US',
    'canadian': 'en-CA',
    'australia': 'en-AU',
    'australian': 'en-AU',
    'new zealand': 'en-NZ',
    'ireland': 'en-IE',
    'irish': 'en-IE',
    'south africa': 'en-ZA',
    'india': 'en-IN',
    'indian': 'en-IN',
}

# POS mapping
POS_MAP = {
    'noun': 'noun',
    'proper noun': 'noun',
    'verb': 'verb',
    'adjective': 'adjective',
    'adverb': 'adverb',
    'pronoun': 'pronoun',
    'preposition': 'preposition',
    'conjunction': 'conjunction',
    'interjection': 'interjection',
    'determiner': 'determiner',
    'particle': 'particle',
    'auxiliary': 'auxiliary',
    'contraction': 'verb',
    'prefix': 'affix',
    'suffix': 'affix',
    'phrase': 'phrase',      # NEW: Multi-word expressions
    'proverb': 'phrase',     # NEW: Proverbs treated as phrases
    'numeral': 'numeral',    # NEW: Numbers (thirteen, centillion, etc.)
}

# Label classifications
REGISTER_LABELS = {
    'informal', 'colloquial', 'slang', 'vulgar', 'offensive',
    'derogatory', 'formal', 'euphemistic', 'humorous', 'literary'
}

TEMPORAL_LABELS = {
    'archaic', 'obsolete', 'dated', 'historical', 'rare'
}

DOMAIN_LABELS = {
    'computing', 'mathematics', 'medicine', 'biology', 'chemistry',
    'physics', 'law', 'military', 'nautical', 'aviation', 'sports'
}


def extract_pos_tags(text: str) -> List[str]:
    """Extract POS tags from section headers and {{head}} templates."""
    pos_tags = []

    # Primary: Extract from section headers (===Noun===, etc.)
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        if header in POS_MAP:
            pos_tags.append(POS_MAP[header])

    # Fallback: If no section headers found, try {{head|en|POS}} templates
    if not pos_tags:
        for match in HEAD_TEMPLATE.finditer(text):
            pos = match.group(1).lower().strip()
            if pos in POS_MAP:
                pos_tags.append(POS_MAP[pos])
            # Handle special cases
            elif pos == 'phrase':
                pos_tags.append('phrase')
            elif pos == 'proverb':
                pos_tags.append('phrase')
            elif pos == 'numeral':
                pos_tags.append('numeral')

    return sorted(set(pos_tags))


def extract_labels(text: str) -> Dict[str, List[str]]:
    """Extract context labels from templates and categorize them."""
    labels = {
        'register': set(),
        'temporal': set(),
        'domain': set(),
        'region': set(),
        'categories': set(),  # NEW: Track all categories (including prefixes/suffixes)
    }

    # Extract from {{lb|en|...}} templates
    for match in CONTEXT_LABEL.finditer(text):
        label_text = match.group(1)
        for label in label_text.split('|'):
            label = label.strip().lower()

            if label in REGISTER_LABELS:
                labels['register'].add(label)
            elif label in TEMPORAL_LABELS:
                labels['temporal'].add(label)
            elif label in DOMAIN_LABELS:
                labels['domain'].add(label)
            elif label in REGION_LABELS:
                labels['region'].add(REGION_LABELS[label])

    # Extract from categories
    for match in CATEGORY.finditer(text):
        cat = match.group(1)  # Keep original case for categories
        cat_lower = cat.lower()

        # Store the category itself
        labels['categories'].add(cat)

        if 'informal' in cat_lower or 'colloquial' in cat_lower:
            labels['register'].add('informal')
        if 'slang' in cat_lower:
            labels['register'].add('slang')
        if 'vulgar' in cat_lower:
            labels['register'].add('vulgar')
        if 'offensive' in cat_lower or 'derogatory' in cat_lower:
            labels['register'].add('offensive')
        if 'obsolete' in cat_lower:
            labels['temporal'].add('obsolete')
        if 'archaic' in cat_lower:
            labels['temporal'].add('archaic')

        for region_key, region_code in REGION_LABELS.items():
            if region_key in cat_lower:
                labels['region'].add(region_code)
                break

    return {k: sorted(v) for k, v in labels.items() if v}


def extract_page_content(page_xml: str) -> Optional[tuple]:
    """
    Extract title and text from page XML using simple regex.
    Returns (title, text) or None if not found.
    Special pages (known prefixes only) return ('SPECIAL_PAGE', title).
    Redirects return None (skipped).
    """
    # Extract title
    title_match = TITLE_PATTERN.search(page_xml)
    if not title_match:
        return None
    title = title_match.group(1)

    # Skip redirects (e.g., "grain of salt" → "with a grain of salt")
    if REDIRECT_PATTERN.search(page_xml):
        return None

    # Track known special pages separately
    if title.startswith(SPECIAL_PAGE_PREFIXES):
        return ('SPECIAL_PAGE', title)

    # Extract text
    text_match = TEXT_PATTERN.search(page_xml)
    if not text_match:
        return None
    text = text_match.group(1)

    # Check for English section
    if not ENGLISH_SECTION.search(text):
        return None

    return (title, text)


def parse_entry(title: str, text: str) -> Optional[Dict]:
    """Parse a single Wiktionary page."""
    word = title.lower().strip()

    # Allow unicode letters (café, naïve), digits, apostrophes, hyphens, spaces,
    # periods (i.e., e.g., A.M.), and slashes (w/)
    # Unicode categories: L* = letters, N* = numbers
    valid_word = all(
        unicodedata.category(c)[0] in 'LN' or c in " '-./"
        for c in word
    )
    if not valid_word:
        return None

    pos_tags = extract_pos_tags(text)
    if not pos_tags:
        return None

    labels = extract_labels(text)
    is_phrase = ' ' in word

    return {
        'word': word,
        'pos': pos_tags,
        'labels': labels,
        'is_phrase': is_phrase,
        'sources': ['wikt'],
    }


def scan_pages(file_obj, chunk_size: int = 1024 * 1024):
    """
    Scan for <page> boundaries and yield complete page XML.

    This is much faster than ET.iterparse() because:
    - No XML DOM building
    - No namespace handling
    - No validation
    - Simple string scanning
    """
    buffer = ""
    page_start_marker = "<page>"
    page_end_marker = "</page>"

    while True:
        # Read chunk
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break

        # Decode to string
        try:
            buffer += chunk.decode('utf-8')
        except UnicodeDecodeError:
            buffer += chunk.decode('utf-8', errors='ignore')

        # Find complete pages in buffer
        while True:
            start = buffer.find(page_start_marker)
            if start == -1:
                # No page start found, keep last bit in case it's partial
                buffer = buffer[-len(page_start_marker):]
                break

            end = buffer.find(page_end_marker, start)
            if end == -1:
                # Page incomplete, keep from start
                buffer = buffer[start:]
                break

            # Extract complete page (include closing tag)
            end += len(page_end_marker)
            page_xml = buffer[start:end]
            buffer = buffer[end:]

            yield page_xml


def parse_wiktionary_dump(xml_path: Path, output_path: Path, limit: int = None, diagnostic_mode: bool = False):
    """Parse Wiktionary XML dump using lightweight scanning."""

    print(f"Parsing: {xml_path}")
    print(f"Output: {output_path}")
    print(f"Method: Lightweight scanner (no full XML parsing)")
    if limit:
        print(f"Limit: {limit:,} entries")
    if diagnostic_mode:
        print(f"Diagnostic mode: Will stop after 1000 skips and show samples")
    print()

    print("Initializing streaming decompressor...")
    sys.stdout.flush()

    if str(xml_path).endswith('.bz2'):
        file_obj = BZ2StreamReader(xml_path, chunk_size=256 * 1024)
    else:
        file_obj = open(xml_path, 'rb')

    entries_processed = 0
    entries_written = 0
    entries_skipped = 0
    special_pages_found = 0  # NEW: Track special pages separately
    first_page_seen = False

    # Diagnostic tracking (special pages not included - they're expected)
    skip_reasons = {
        'no_content_extracted': [],  # extract_page_content returned None
        'parse_entry_none': [],      # parse_entry returned None
        'parse_entry_exception': []  # parse_entry threw exception
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    with file_obj as f, open(output_path, 'w', encoding='utf-8') as out:
        # Scan for pages (much faster than XML parsing)
        for page_xml in scan_pages(f, chunk_size=1024 * 1024):
            entries_processed += 1

            if not first_page_seen:
                first_page_seen = True
                if isinstance(file_obj, BZ2StreamReader):
                    file_obj.finish_progress()
                print("✓ First page found, scanning...")
                sys.stdout.flush()

            # Extract title and text using simple regex
            result = extract_page_content(page_xml)
            if not result:
                entries_skipped += 1
                if diagnostic_mode and len(skip_reasons['no_content_extracted']) < 10:
                    # Extract what we can for diagnostic
                    title_match = TITLE_PATTERN.search(page_xml)
                    title = title_match.group(1) if title_match else "NO_TITLE"
                    skip_reasons['no_content_extracted'].append({
                        'title': title,
                        'page_preview': page_xml[:500]
                    })

                # Check diagnostic stop condition
                if diagnostic_mode and entries_skipped >= 1000:
                    break
                continue

            # Handle special pages (known prefixes - expected, no diagnostic needed)
            if result[0] == 'SPECIAL_PAGE':
                special_pages_found += 1
                continue

            title, text = result

            # Parse entry
            try:
                entry = parse_entry(title, text)
                if entry:
                    out.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    entries_written += 1
                else:
                    entries_skipped += 1
                    if diagnostic_mode and len(skip_reasons['parse_entry_none']) < 10:
                        skip_reasons['parse_entry_none'].append({
                            'title': title,
                            'text_preview': text[:500] if len(text) > 500 else text
                        })

                    # Check diagnostic stop condition
                    if diagnostic_mode and entries_skipped >= 1000:
                        break
            except Exception as e:
                entries_skipped += 1
                if diagnostic_mode and len(skip_reasons['parse_entry_exception']) < 10:
                    skip_reasons['parse_entry_exception'].append({
                        'title': title,
                        'exception': str(e),
                        'text_preview': text[:500] if len(text) > 500 else text
                    })

                # Check diagnostic stop condition
                if diagnostic_mode and entries_skipped >= 1000:
                    break

            # Progress
            if entries_processed % 1000 == 0:
                if entries_processed % 5000 == 0:
                    elapsed = time.time() - start_time
                    rate = entries_processed / elapsed if elapsed > 0 else 0
                    print(f"  Processed: {entries_processed:,} | "
                          f"Written: {entries_written:,} | "
                          f"Special: {special_pages_found:,} | "
                          f"Skipped: {entries_skipped:,} | "
                          f"Rate: {rate:.0f} pages/sec")
                    out.flush()
                else:
                    print(f"  Processed: {entries_processed:,} | "
                          f"Written: {entries_written:,}...",
                          end='\r', flush=True)

            if limit and entries_written >= limit:
                print(f"\nReached limit of {limit:,} entries")
                break

    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)

    print()
    print("=" * 60)
    print(f"Total processed: {entries_processed:,}")
    print(f"Total written: {entries_written:,}")
    print(f"Special pages: {special_pages_found:,}")
    print(f"Total skipped: {entries_skipped:,}")
    print(f"Success rate: {entries_written/entries_processed*100:.1f}%")
    print(f"Time: {elapsed_min}m {elapsed_sec}s")
    print(f"Rate: {entries_processed / elapsed:.0f} pages/sec")
    print("=" * 60)

    # Print diagnostic information if in diagnostic mode
    if diagnostic_mode:
        print()
        print("=" * 60)
        print("DIAGNOSTIC REPORT: Skip Reasons Breakdown")
        print("=" * 60)
        print()

        # Count skip reasons
        total_no_content = len(skip_reasons['no_content_extracted'])
        total_parse_none = len(skip_reasons['parse_entry_none'])
        total_exceptions = len(skip_reasons['parse_entry_exception'])

        print(f"Skip reason counts (showing up to 10 samples each):")
        print(f"  1. No content extracted (no title/text or not English): {total_no_content} samples")
        print(f"  2. parse_entry returned None (validation failed): {total_parse_none} samples")
        print(f"  3. parse_entry threw exception: {total_exceptions} samples")
        print()
        print(f"Note: Special pages ({', '.join(SPECIAL_PAGE_PREFIXES)}) are")
        print(f"      counted separately and not included in diagnostic samples.")
        print()

        # Print samples for each category
        if skip_reasons['no_content_extracted']:
            print("-" * 60)
            print("SAMPLES: No content extracted")
            print("-" * 60)
            for i, sample in enumerate(skip_reasons['no_content_extracted'][:10], 1):
                print(f"\n{i}. Title: {sample['title']}")
                print(f"   Page preview (first 500 chars):")
                print(f"   {sample['page_preview'][:500]}")
                print()

        if skip_reasons['parse_entry_none']:
            print("-" * 60)
            print("SAMPLES: parse_entry returned None")
            print("-" * 60)
            for i, sample in enumerate(skip_reasons['parse_entry_none'][:10], 1):
                print(f"\n{i}. Title: {sample['title']}")
                print(f"   Text preview (first 500 chars):")
                print(f"   {sample['text_preview'][:500]}")
                print()

        if skip_reasons['parse_entry_exception']:
            print("-" * 60)
            print("SAMPLES: parse_entry threw exception")
            print("-" * 60)
            for i, sample in enumerate(skip_reasons['parse_entry_exception'][:10], 1):
                print(f"\n{i}. Title: {sample['title']}")
                print(f"   Exception: {sample['exception']}")
                print(f"   Text preview (first 500 chars):")
                print(f"   {sample['text_preview'][:500]}")
                print()

        print("=" * 60)
        print("GOAL: Reach fixed point (no samples in any category)")
        print("=" * 60)
        print()
        print("Action items based on samples:")
        print()
        print("1. 'no_content_extracted' samples:")
        print("   - Look for unknown special page prefixes (add to SPECIAL_PAGE_PREFIXES)")
        print("   - Check for pages with ':' that aren't English words (e.g., 'talk:', 'user:')")
        print("   - Identify any regex pattern issues")
        print()
        print("2. 'parse_entry_none' samples:")
        print("   - Check if missing POS tags for valid entries")
        print("   - Check for character validation issues")
        print("   - Identify entries that should be extracted")
        print()
        print("3. 'parse_entry_exception' samples:")
        print("   - Fix code bugs causing exceptions")
        print("   - Add error handling for edge cases")
        print()
        print("Fixed point achieved when all sample lists are empty!")
        print("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Fast scanner-based Wiktionary XML parser (no full XML parsing)'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input XML file (.xml or .xml.bz2)'
    )

    parser.add_argument(
        'output',
        type=Path,
        help='Output JSONL file'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of entries to extract (for testing)'
    )

    parser.add_argument(
        '--diagnostic',
        action='store_true',
        help='Diagnostic mode: stop after 1000 skips and show sample entries from each skip category'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    parse_wiktionary_dump(args.input, args.output, args.limit, args.diagnostic)


if __name__ == '__main__':
    main()
