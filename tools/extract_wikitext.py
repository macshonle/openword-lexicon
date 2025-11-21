#!/usr/bin/env python3
"""
Extract raw wikitext from Wiktionary XML dump for specific words.

This tool scans through the .xml.bz2 file and extracts the complete
<page>...</page> XML for specified words, writing each to a separate file.

Usage:
    python tools/extract_wikitext.py INPUT.xml.bz2 OUTPUT_DIR WORD1 [WORD2 ...]
    python tools/extract_wikitext.py INPUT.xml.bz2 OUTPUT_DIR --words-file WORDLIST.txt

Examples:
    # Extract specific words
    python tools/extract_wikitext.py data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        tests/wikitext-samples acronym dialect four

    # Extract from hotspot list
    python tools/extract_wikitext.py data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        tests/wikitext-samples --words-file tests/hotspot-words.txt
"""

import bz2
import re
import sys
from pathlib import Path


def load_words_from_file(filepath):
    """Load words from a text file, one per line, ignoring comments."""
    words = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                words.append(line)
    return words


def scan_and_extract(xml_path, output_dir, target_words):
    """Scan XML dump and extract pages for target words."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to set for fast lookup (lowercase for case-insensitive matching)
    target_set = {word.lower() for word in target_words}
    found_words = set()

    print(f"Scanning: {xml_path}")
    print(f"Output directory: {output_dir}")
    print(f"Looking for {len(target_words)} words...")
    print()

    # Patterns for extraction
    title_pattern = re.compile(r'<title>([^<]+)</title>')
    page_start = '<page>'
    page_end = '</page>'

    buffer = ""
    pages_scanned = 0
    pages_extracted = 0

    # Open bz2 file
    with bz2.open(xml_path, 'rt', encoding='utf-8') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), ''):
            buffer += chunk

            # Extract complete pages
            while True:
                start = buffer.find(page_start)
                if start == -1:
                    # Keep last bit in case it's a partial tag
                    buffer = buffer[-len(page_start):]
                    break

                end = buffer.find(page_end, start)
                if end == -1:
                    # Incomplete page, keep from start
                    buffer = buffer[start:]
                    break

                # Extract complete page
                end += len(page_end)
                page_xml = buffer[start:end]
                buffer = buffer[end:]

                pages_scanned += 1
                if pages_scanned % 100000 == 0:
                    print(f"Scanned {pages_scanned:,} pages, extracted {pages_extracted}...")

                # Check if this is a target word
                title_match = title_pattern.search(page_xml)
                if title_match:
                    title = title_match.group(1)
                    title_lower = title.lower()

                    if title_lower in target_set and title_lower not in found_words:
                        # Extract and save
                        output_file = output_dir / f"{title_lower}.xml"
                        with open(output_file, 'w', encoding='utf-8') as out:
                            out.write(page_xml)

                        found_words.add(title_lower)
                        pages_extracted += 1
                        print(f"✓ Extracted: {title} -> {output_file.name}")

                        # Stop if we've found all target words
                        if len(found_words) == len(target_set):
                            print()
                            print(f"All {len(target_set)} target words found!")
                            return found_words

    print()
    print(f"Scan complete. Scanned {pages_scanned:,} pages.")
    print(f"Extracted {pages_extracted} of {len(target_words)} target words.")

    # Report missing words
    missing = target_set - found_words
    if missing:
        print()
        print(f"⚠️  Missing words ({len(missing)}):")
        for word in sorted(missing):
            print(f"  - {word}")

    return found_words


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not xml_path.exists():
        print(f"Error: Input file not found: {xml_path}")
        sys.exit(1)

    # Parse words from arguments or file
    if len(sys.argv) > 3 and sys.argv[3] == '--words-file':
        if len(sys.argv) < 5:
            print("Error: --words-file requires a filename argument")
            sys.exit(1)
        words_file = Path(sys.argv[4])
        if not words_file.exists():
            print(f"Error: Words file not found: {words_file}")
            sys.exit(1)
        target_words = load_words_from_file(words_file)
        print(f"Loaded {len(target_words)} words from {words_file}")
    else:
        target_words = sys.argv[3:]

    if not target_words:
        print("Error: No words specified")
        sys.exit(1)

    scan_and_extract(xml_path, output_dir, target_words)


if __name__ == '__main__':
    main()
