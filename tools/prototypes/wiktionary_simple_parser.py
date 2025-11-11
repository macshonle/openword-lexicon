#!/usr/bin/env python3
"""
wiktionary_simple_parser.py - Fast Wiktionary XML parser without Lua

Extracts words, POS tags, and labels using simple regex patterns.
No Lua evaluation, no complex dependencies, 10-100x faster than wiktextract.

Usage:
    python wiktionary_simple_parser.py INPUT.xml.bz2 OUTPUT.jsonl [--limit N]
"""

import bz2
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Set
import xml.etree.ElementTree as ET


class BZ2StreamReader:
    """
    Streaming BZ2 decompressor with progress feedback.

    Wraps a .bz2 file and decompresses in fixed-size chunks,
    providing progress updates during decompression. This avoids
    the long silent period with bz2.open() + ET.iterparse().
    """

    def __init__(self, filepath: Path, chunk_size: int = 256 * 1024):
        """
        Initialize streaming reader.

        Args:
            filepath: Path to .bz2 file
            chunk_size: Size of chunks to read (default 256 KB)
        """
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
        """
        Read decompressed data.

        Args:
            size: Number of bytes to read (-1 for all available)

        Returns:
            Decompressed bytes
        """
        # If size not specified or buffer has enough, return from buffer
        if size == -1:
            # Read all remaining
            while not self.decompressor.eof:
                self._decompress_chunk()
            result = self.buffer
            self.buffer = b''
            return result

        # Build buffer until we have enough
        while len(self.buffer) < size and not self.decompressor.eof:
            self._decompress_chunk()

        # Return requested amount
        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result

    def _decompress_chunk(self):
        """Decompress one chunk and update progress."""
        if self.decompressor.eof:
            return

        # Read compressed chunk
        compressed = self.file.read(self.chunk_size)
        if not compressed:
            return

        self.total_compressed += len(compressed)

        # Decompress
        decompressed = self.decompressor.decompress(compressed)
        self.buffer += decompressed
        self.total_decompressed += len(decompressed)

        # Show progress every 50 MB decompressed (less frequent for full extraction)
        if self.total_decompressed - self.last_progress >= 50 * 1024 * 1024:
            elapsed = time.time() - self.start_time
            rate_mb = (self.total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            print(f"  Decompressing: {self.total_decompressed / (1024*1024):.0f} MB "
                  f"({rate_mb:.1f} MB/s)")
            sys.stdout.flush()
            self.last_progress = self.total_decompressed

    def close(self):
        """Close underlying file."""
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Regex patterns for extraction
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)
CONTEXT_LABEL = re.compile(r'\{\{(?:lb|label|context)\|en\|([^}]+)\}\}', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:English\s+([^\]]+)\]\]', re.IGNORECASE)

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

# POS mapping (MediaWiki header → our schema)
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
    'contraction': 'verb',  # Include contractions!
}

# Label classification
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
    """Extract POS tags from section headers."""
    pos_tags = []
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        if header in POS_MAP:
            pos_tags.append(POS_MAP[header])
    return sorted(set(pos_tags))


def extract_labels(text: str) -> Dict[str, List[str]]:
    """Extract context labels from templates and categorize them."""
    labels = {
        'register': set(),
        'temporal': set(),
        'domain': set(),
        'region': set(),
    }

    # Extract from {{lb|en|...}} templates
    for match in CONTEXT_LABEL.finditer(text):
        label_text = match.group(1)
        # Split on | for multiple labels
        for label in label_text.split('|'):
            label = label.strip().lower()

            if label in REGISTER_LABELS:
                labels['register'].add(label)
            elif label in TEMPORAL_LABELS:
                labels['temporal'].add(label)
            elif label in DOMAIN_LABELS:
                labels['domain'].add(label)
            # Check regional labels
            elif label in REGION_LABELS:
                labels['region'].add(REGION_LABELS[label])

    # Extract from categories
    for match in CATEGORY.finditer(text):
        cat = match.group(1).lower()

        # Extract labels from category names
        if 'informal' in cat or 'colloquial' in cat:
            labels['register'].add('informal')
        if 'slang' in cat:
            labels['register'].add('slang')
        if 'vulgar' in cat:
            labels['register'].add('vulgar')
        if 'offensive' in cat or 'derogatory' in cat:
            labels['register'].add('offensive')
        if 'obsolete' in cat:
            labels['temporal'].add('obsolete')
        if 'archaic' in cat:
            labels['temporal'].add('archaic')

        # Check regional in categories
        for region_key, region_code in REGION_LABELS.items():
            if region_key in cat:
                labels['region'].add(region_code)
                break

    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in labels.items() if v}


def is_valid_entry(title: str, text: str) -> bool:
    """Check if entry should be included."""
    # Skip if no English section
    if not ENGLISH_SECTION.search(text):
        return False

    # Skip special pages
    if ':' in title:  # Wiktionary:, Template:, etc.
        return False

    # Skip if title has non-ASCII letters (except for loan words)
    # This is conservative but fast
    if not all(c.isalnum() or c in " '-" for c in title):
        # Could relax this to allow more characters
        return False

    return True


def parse_entry(title: str, text: str) -> Dict:
    """Parse a single Wiktionary page."""
    # Normalize title
    word = title.lower().strip()

    # Extract data
    pos_tags = extract_pos_tags(text)
    labels = extract_labels(text)
    is_phrase = ' ' in word

    entry = {
        'word': word,
        'pos': pos_tags,
        'labels': labels,
        'is_phrase': is_phrase,
        'sources': ['wikt'],
    }

    return entry


def parse_wiktionary_dump(xml_path: Path, output_path: Path, limit: int = None):
    """Parse Wiktionary XML dump and write JSONL output."""

    print(f"Parsing: {xml_path}")
    print(f"Output: {output_path}")
    if limit:
        print(f"Limit: {limit:,} entries")
    print()

    # Determine if file is compressed
    print("Initializing streaming decompressor...")
    print("(Progress shown every 50 MB decompressed)")
    sys.stdout.flush()

    if str(xml_path).endswith('.bz2'):
        # Use streaming decompressor with progress feedback
        file_obj = BZ2StreamReader(xml_path, chunk_size=256 * 1024)
    else:
        file_obj = open(xml_path, 'rb')

    # MediaWiki XML namespace
    ns = '{http://www.mediawiki.org/xml/export-0.10/}'

    entries_processed = 0
    entries_written = 0
    entries_skipped = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with file_obj as f, open(output_path, 'w', encoding='utf-8') as out:
        # Iterative parsing for memory efficiency
        for event, elem in ET.iterparse(f, events=('end',)):
            if elem.tag != f'{ns}page':
                continue

            entries_processed += 1

            # Extract title and text
            title_elem = elem.find(f'{ns}title')
            revision_elem = elem.find(f'{ns}revision')

            if title_elem is None or revision_elem is None:
                elem.clear()
                continue

            title = title_elem.text
            text_elem = revision_elem.find(f'{ns}text')

            if text_elem is None or text_elem.text is None:
                elem.clear()
                continue

            text = text_elem.text

            # Validate entry
            if not is_valid_entry(title, text):
                entries_skipped += 1
                elem.clear()
                continue

            # Parse entry
            try:
                entry = parse_entry(title, text)

                # Only write if we got POS tags (minimum requirement)
                if entry['pos']:
                    out.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    entries_written += 1
                else:
                    entries_skipped += 1

            except Exception as e:
                print(f"Error parsing {title}: {e}", file=sys.stderr)
                entries_skipped += 1

            # Clear element to free memory
            elem.clear()

            # Progress with explicit flush for real-time output
            if entries_processed % 5000 == 0:
                print(f"  Processed: {entries_processed:,} | "
                      f"Written: {entries_written:,} | "
                      f"Skipped: {entries_skipped:,}")
                sys.stdout.flush()
                out.flush()  # Flush output file buffer

            # Check limit
            if limit and entries_written >= limit:
                print(f"\nReached limit of {limit:,} entries")
                break

    print()
    print("=" * 60)
    print(f"Total processed: {entries_processed:,}")
    print(f"Total written: {entries_written:,}")
    print(f"Total skipped: {entries_skipped:,}")
    print(f"Success rate: {entries_written/entries_processed*100:.1f}%")
    print("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Fast Wiktionary XML parser (no Lua)'
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

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    parse_wiktionary_dump(args.input, args.output, args.limit)


if __name__ == '__main__':
    main()
