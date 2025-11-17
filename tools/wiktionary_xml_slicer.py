#!/usr/bin/env python3
"""
wiktionary_xml_slicer.py - Extract diagnostic XML slices from Wiktionary dump

Creates ~1KB slices of XML at strategic points during parsing to enable
deep analysis of Wiktionary data format without loading the full dump.

Slicing strategy:
1. First 10 entries (baseline format)
2. Every 10,000th entry (statistical sampling)
3. Entries with specific characteristics:
   - Has POS tags but no categories
   - Has categories but no POS tags
   - Multi-word entries
   - Entries with syllable data
   - Entries with labels
4. Random samples from different file positions

Output:
- data/diagnostic/wikt_slices/OFFSET_LEN.xml
  where OFFSET is hex position, LEN is decimal byte length
"""

import bz2
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
import random


class XMLSlicer:
    """Extract diagnostic slices from XML stream."""

    def __init__(self, output_dir: Path, max_slices: int = 50):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_slices = max_slices
        self.slices_written = 0
        self.entry_count = 0
        self.byte_offset = 0

        # Track what we've sampled
        self.sampled_types: Set[str] = set()
        self.position_samples = 0

        # Patterns for analysis
        self.has_pos_pattern = re.compile(r'===+\s*(?:Noun|Verb|Adjective|Adverb)', re.IGNORECASE)
        self.has_category_pattern = re.compile(r'\[\[Category:English\s+', re.IGNORECASE)
        self.has_syllable_pattern = re.compile(r'\{\{(?:hyphenation|hyph)\|', re.IGNORECASE)
        self.has_label_pattern = re.compile(r'\{\{(?:lb|label|context)\|en\|', re.IGNORECASE)

    def should_sample(self, page_xml: str, title: str) -> Optional[str]:
        """Determine if this entry should be sampled and why."""

        if self.slices_written >= self.max_slices:
            return None

        # First 10 entries (baseline)
        if self.entry_count < 10:
            return "baseline"

        # Every 10,000th entry (statistical)
        if self.entry_count % 10000 == 0:
            return f"every10k_{self.entry_count}"

        # Multi-word entries
        if ' ' in title and 'multiword' not in self.sampled_types:
            if random.random() < 0.3:  # 30% chance to avoid too many
                self.sampled_types.add('multiword')
                return "multiword"

        # Characteristic-based sampling
        has_pos = bool(self.has_pos_pattern.search(page_xml))
        has_cat = bool(self.has_category_pattern.search(page_xml))
        has_syll = bool(self.has_syllable_pattern.search(page_xml))
        has_label = bool(self.has_label_pattern.search(page_xml))

        # POS but no categories - important edge case
        if has_pos and not has_cat and 'pos_no_cat' not in self.sampled_types:
            if random.random() < 0.1:
                self.sampled_types.add('pos_no_cat')
                return "pos_no_cat"

        # Categories but no POS - another edge case
        if has_cat and not has_pos and 'cat_no_pos' not in self.sampled_types:
            if random.random() < 0.1:
                self.sampled_types.add('cat_no_pos')
                return "cat_no_pos"

        # Has syllable data
        if has_syll and 'syllable' not in self.sampled_types:
            if random.random() < 0.2:
                self.sampled_types.add('syllable')
                return "syllable"

        # Has labels
        if has_label and 'labels' not in self.sampled_types:
            if random.random() < 0.2:
                self.sampled_types.add('labels')
                return "labels"

        # Random position-based samples (spread across file)
        if self.position_samples < 10 and random.random() < 0.0001:
            self.position_samples += 1
            return f"position_{self.position_samples}"

        return None

    def write_slice(self, page_xml: str, title: str, reason: str):
        """Write a slice to disk."""

        # Trim to ~4KiB if needed (larger slices help detect malformed tags and edge cases)
        max_len = 4 * 1024
        if len(page_xml) > max_len:
            # Try to cut at a reasonable boundary
            truncated = page_xml[:max_len]
            last_newline = truncated.rfind('\n')
            if last_newline > max_len * 0.8:  # If we can cut at a line
                page_xml = truncated[:last_newline] + "\n... [truncated]"
            else:
                page_xml = truncated + "\n... [truncated]"

        # Generate filename: offset in hex, length in decimal
        offset_hex = f"{self.byte_offset:08x}"
        length_dec = len(page_xml)
        filename = f"{offset_hex}_{length_dec}_{reason}_{title[:30]}.xml"

        # Sanitize filename
        filename = re.sub(r'[^\w\-_\.]', '_', filename)

        filepath = self.output_dir / filename
        filepath.write_text(page_xml, encoding='utf-8')

        self.slices_written += 1
        print(f"Slice {self.slices_written}/{self.max_slices}: {filename}")

    def process_page(self, page_xml: str, byte_offset: int):
        """Process a single page and potentially sample it."""
        self.byte_offset = byte_offset
        self.entry_count += 1

        # Extract title
        title_match = re.search(r'<title>([^<]+)</title>', page_xml)
        if not title_match:
            return
        title = title_match.group(1)

        # Check if we should sample
        reason = self.should_sample(page_xml, title)
        if reason:
            self.write_slice(page_xml, title, reason)


def extract_pages_with_slicing(input_path: Path, output_dir: Path):
    """Extract diagnostic slices while scanning the XML."""

    print(f"Extracting slices from {input_path}")
    print(f"Output directory: {output_dir}")

    slicer = XMLSlicer(output_dir)

    # Read the bz2 file
    with bz2.open(input_path, 'rt', encoding='utf-8') as f:
        page_buffer = []
        in_page = False
        byte_offset = 0

        for line in f:
            byte_offset += len(line.encode('utf-8'))

            if '<page>' in line:
                in_page = True
                page_buffer = [line]
            elif in_page:
                page_buffer.append(line)
                if '</page>' in line:
                    page_xml = ''.join(page_buffer)
                    slicer.process_page(page_xml, byte_offset - len(page_xml.encode('utf-8')))
                    in_page = False
                    page_buffer = []

                    # Stop if we've collected enough
                    if slicer.slices_written >= slicer.max_slices:
                        break

    print(f"\nCompleted: {slicer.slices_written} slices written")
    print(f"Total entries scanned: {slicer.entry_count}")

    # Write metadata about the slicing run
    metadata = {
        'slices_written': slicer.slices_written,
        'entries_scanned': slicer.entry_count,
        'sampled_types': sorted(slicer.sampled_types),
        'source_file': str(input_path),
    }

    metadata_path = output_dir / '_metadata.json'
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata written to {metadata_path}")


def main():
    """Main entry point."""

    if len(sys.argv) < 2:
        print("Usage: python wiktionary_xml_slicer.py INPUT.xml.bz2 [OUTPUT_DIR]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('data/diagnostic/wikt_slices')

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    extract_pages_with_slicing(input_path, output_dir)


if __name__ == '__main__':
    main()
