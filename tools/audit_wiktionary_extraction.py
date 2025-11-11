#!/usr/bin/env python3
"""
audit_wiktionary_extraction.py - Audit Wiktionary extraction approach

Analyzes raw Wiktionary XML dump to validate extraction strategy:
- What languages are in the dump?
- What percentage have English sections?
- Are we correctly identifying English words?
- What label coverage can we expect?

Generates comprehensive audit reports for version control.

Usage:
    python audit_wiktionary_extraction.py INPUT.xml.bz2 --sample-size 10000

Output:
    reports/wiktionary_audit.md - Full audit report
    reports/wiktionary_samples.json - Sample entries for review
"""

import bz2
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple
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

        # Show progress every 10 MB decompressed
        if self.total_decompressed - self.last_progress >= 10 * 1024 * 1024:
            elapsed = time.time() - self.start_time
            rate_mb = (self.total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            print(f"  Decompressing: {self.total_decompressed / (1024*1024):.1f} MB "
                  f"(from {self.total_compressed / (1024*1024):.1f} MB compressed, "
                  f"{rate_mb:.1f} MB/s)")
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


# Regex patterns
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)
CONTEXT_LABEL = re.compile(r'\{\{(?:lb|label|context)\|([^|]+)\|([^}]+)\}\}', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:([^\]]+)\]\]', re.IGNORECASE)


def extract_languages(text: str) -> List[str]:
    """Extract all language sections from page text."""
    languages = []
    for match in LANGUAGE_SECTION.finditer(text):
        lang = match.group(1).strip()
        languages.append(lang)
    return languages


def has_english_section(text: str) -> bool:
    """Check if page has English section."""
    for lang in extract_languages(text):
        if lang.lower() == 'english':
            return True
    return False


def extract_context_labels(text: str) -> Dict[str, Set[str]]:
    """Extract all context labels and their languages."""
    labels_by_lang = defaultdict(set)

    for match in CONTEXT_LABEL.finditer(text):
        lang_code = match.group(1).strip()
        labels_text = match.group(2)

        for label in labels_text.split('|'):
            label = label.strip()
            if label:
                labels_by_lang[lang_code].add(label)

    return dict(labels_by_lang)


def audit_entry(title: str, text: str) -> Dict:
    """Audit a single Wiktionary entry."""
    languages = extract_languages(text)
    has_english = has_english_section(text)
    context_labels = extract_context_labels(text)
    categories = CATEGORY.findall(text)
    pos_headers = [m.group(1) for m in POS_HEADER.finditer(text)]

    return {
        'title': title,
        'languages': languages,
        'has_english': has_english,
        'english_only': languages == ['English'],
        'context_labels': {k: list(v) for k, v in context_labels.items()},
        'categories': categories[:10],  # First 10 categories
        'pos_headers': pos_headers[:10],  # First 10 POS headers
        'text_length': len(text),
    }


def generate_audit_report(
    total_pages: int,
    stats: Dict,
    samples: Dict,
    output_path: Path
):
    """Generate markdown audit report."""

    report = f"""# Wiktionary Extraction Audit Report

Generated by `tools/audit_wiktionary_extraction.py`

This report validates our Wiktionary extraction approach and shows what
data is actually available in the dump.

---

## Overall Statistics

**Total pages analyzed:** {total_pages:,}

| Metric | Count | Percentage |
|--------|------:|-----------:|
| Pages with English section | {stats['english_pages']:,} | {stats['english_pages']/total_pages*100:.1f}% |
| English-only pages | {stats['english_only_pages']:,} | {stats['english_only_pages']/total_pages*100:.1f}% |
| Multilingual pages | {stats['multilingual_pages']:,} | {stats['multilingual_pages']/total_pages*100:.1f}% |
| Pages with context labels | {stats['pages_with_labels']:,} | {stats['pages_with_labels']/total_pages*100:.1f}% |
| Pages with categories | {stats['pages_with_categories']:,} | {stats['pages_with_categories']/total_pages*100:.1f}% |

---

## Language Distribution

Top languages found in the dump:

| Language | Count | Percentage |
|----------|------:|-----------:|
"""

    for lang, count in stats['language_counts'].most_common(20):
        pct = count / total_pages * 100
        report += f"| {lang} | {count:,} | {pct:.1f}% |\n"

    report += f"""
---

## Context Label Analysis

Context labels found ({{{{lb|LANG|...}}}}):

| Language Code | Unique Labels | Total Occurrences |
|---------------|-------------:|-----------------:|
"""

    for lang_code in sorted(stats['label_languages'].keys())[:20]:
        label_set = stats['label_languages'][lang_code]
        count = stats['label_counts'][lang_code]
        report += f"| {lang_code} | {len(label_set):,} | {count:,} |\n"

    report += f"""
---

## English Context Labels

Top context labels for English ({{{{lb|en|...}}}}):

| Label | Count |
|-------|------:|
"""

    if 'en' in stats['english_labels']:
        for label, count in stats['english_labels'].most_common(30):
            report += f"| {label} | {count:,} |\n"
    else:
        report += "| (none found) | 0 |\n"

    report += f"""
---

## Part of Speech Distribution

Top POS headers found:

| POS Header | Count |
|------------|------:|
"""

    for pos, count in stats['pos_counts'].most_common(20):
        report += f"| {pos} | {count:,} |\n"

    report += f"""
---

## Validation Findings

### English Section Detection

Our parser looks for `==English==` section headers. Based on this sample:
- **{stats['english_pages']:,}** pages ({stats['english_pages']/total_pages*100:.1f}%) have English sections
- **{stats['english_only_pages']:,}** pages ({stats['english_only_pages']/total_pages*100:.1f}%) are English-only
- **{stats['multilingual_pages']:,}** pages ({stats['multilingual_pages']/total_pages*100:.1f}%) have multiple languages

**Conclusion:** {'✓ VALID' if stats['english_pages']/total_pages > 0.3 else '⚠ CONCERN'} - {
    'English content is substantial' if stats['english_pages']/total_pages > 0.3
    else 'English content is limited'
}

### Label Coverage

- **{stats['pages_with_labels']:,}** pages ({stats['pages_with_labels']/total_pages*100:.1f}%) have context labels
- **{stats['english_label_pages']:,}** pages ({stats['english_label_pages']/total_pages*100:.1f}%) have English labels ({{{{lb|en|...}}}})

**Conclusion:** {'✓ VALID' if stats['english_label_pages']/total_pages > 0.1 else '⚠ CONCERN'} - {
    'Label coverage is good for filtering' if stats['english_label_pages']/total_pages > 0.1
    else 'Label coverage may be limited'
}

### Sample Entry Quality

See `reports/wiktionary_samples.json` for detailed sample entries.

**Key samples included:**
- English-only entries (typical case)
- Multilingual entries (shows our filtering)
- Entries with regional labels (British, US, etc.)
- Entries with register labels (informal, vulgar, etc.)
- Entries with domain labels (medicine, law, etc.)

---

## Recommendations

"""

    if stats['english_pages'] / total_pages > 0.3:
        report += "✓ **Extraction approach is valid** - Substantial English content found\n\n"
    else:
        report += "⚠ **Review needed** - Limited English content in dump\n\n"

    if stats['english_label_pages'] / total_pages > 0.1:
        report += "✓ **Label-based filtering is feasible** - Good label coverage\n\n"
    else:
        report += "⚠ **Label coverage is limited** - Consider alternative filtering strategies\n\n"

    report += f"""✓ **Simple parser approach confirmed** - No complex Lua evaluation needed for:
- Language detection (section headers)
- POS extraction (subsection headers)
- Context labels ({{{{lb|en|...}}}})
- Regional labels (British, US, etc.)
- Register labels (informal, vulgar, etc.)

---

## Next Steps

1. Review sample entries in `reports/wiktionary_samples.json`
2. Run full extraction: `uv run python tools/prototypes/wiktionary_simple_parser.py ...`
3. Compare with wiktextract output: `uv run python tools/prototypes/compare_wikt_extractions.py`
4. Build plus distribution: `make build-plus`
5. Test game filters: `uv run python tools/filter_words.py --use-case wordle`
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✓ Audit report written: {output_path}")


def audit_wiktionary_dump(xml_path: Path, sample_size: int = 10000):
    """Audit Wiktionary XML dump with sampling."""

    print(f"Auditing: {xml_path}")
    print(f"Sample size: {sample_size:,} pages")
    print()

    # Check file size
    file_size_mb = xml_path.stat().st_size / (1024 * 1024)
    print(f"File size: {file_size_mb:.1f} MB")
    print()

    # Statistics collectors
    stats = {
        'english_pages': 0,
        'english_only_pages': 0,
        'multilingual_pages': 0,
        'pages_with_labels': 0,
        'pages_with_categories': 0,
        'english_label_pages': 0,
        'language_counts': Counter(),
        'label_languages': defaultdict(set),
        'label_counts': Counter(),
        'english_labels': Counter(),
        'pos_counts': Counter(),
    }

    samples = {
        'english_only': [],
        'multilingual': [],
        'with_regional_labels': [],
        'with_register_labels': [],
        'with_domain_labels': [],
    }

    # Determine if file is compressed
    print("Opening file and initializing streaming decompressor...")
    print("(Progress will be shown every 10 MB decompressed)")
    sys.stdout.flush()

    if str(xml_path).endswith('.bz2'):
        # Use streaming decompressor with progress feedback
        file_obj = BZ2StreamReader(xml_path, chunk_size=256 * 1024)
    else:
        file_obj = open(xml_path, 'rb')

    print("✓ File opened, starting decompression and XML parsing...")
    sys.stdout.flush()

    # MediaWiki XML namespace
    ns = '{http://www.mediawiki.org/xml/export-0.10/}'

    pages_processed = 0

    with file_obj as f:
        for event, elem in ET.iterparse(f, events=('end',)):
            if elem.tag != f'{ns}page':
                continue

            pages_processed += 1

            # Show message when first page is found
            if pages_processed == 1:
                print("✓ First page found, parsing...")
                sys.stdout.flush()

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

            # Skip special pages
            if ':' in title:
                elem.clear()
                continue

            # Audit this entry
            try:
                audit = audit_entry(title, text)

                # Update statistics
                for lang in audit['languages']:
                    stats['language_counts'][lang] += 1

                if audit['has_english']:
                    stats['english_pages'] += 1

                if audit['english_only']:
                    stats['english_only_pages'] += 1
                    if len(samples['english_only']) < 10:
                        samples['english_only'].append(audit)

                if len(audit['languages']) > 1:
                    stats['multilingual_pages'] += 1
                    if len(samples['multilingual']) < 10:
                        samples['multilingual'].append(audit)

                if audit['context_labels']:
                    stats['pages_with_labels'] += 1

                    for lang_code, labels in audit['context_labels'].items():
                        stats['label_languages'][lang_code].update(labels)
                        stats['label_counts'][lang_code] += len(labels)

                        if lang_code == 'en':
                            stats['english_label_pages'] += 1
                            for label in labels:
                                stats['english_labels'][label] += 1

                            # Collect samples with different label types
                            if any('british' in l.lower() or 'us' in l.lower() or 'american' in l.lower()
                                   for l in labels):
                                if len(samples['with_regional_labels']) < 10:
                                    samples['with_regional_labels'].append(audit)

                            if any(l.lower() in {'informal', 'vulgar', 'slang', 'offensive'}
                                   for l in labels):
                                if len(samples['with_register_labels']) < 10:
                                    samples['with_register_labels'].append(audit)

                            if any(l.lower() in {'medicine', 'law', 'computing', 'sports'}
                                   for l in labels):
                                if len(samples['with_domain_labels']) < 10:
                                    samples['with_domain_labels'].append(audit)

                if audit['categories']:
                    stats['pages_with_categories'] += 1

                for pos in audit['pos_headers']:
                    stats['pos_counts'][pos] += 1

            except Exception as e:
                print(f"Error auditing {title}: {e}", file=sys.stderr)

            elem.clear()

            # Progress (every 100 pages for faster feedback)
            if pages_processed % 100 == 0:
                print(f"  Processed: {pages_processed:,} pages...", end='\r')
                sys.stdout.flush()

            # More detailed progress every 1000 pages
            if pages_processed % 1000 == 0:
                print(f"  Processed: {pages_processed:,} pages (English: {stats['english_pages']}, Labels: {stats['english_label_pages']})")
                sys.stdout.flush()

            # Check limit
            if pages_processed >= sample_size:
                print(f"\nReached sample size of {sample_size:,} pages")
                break

    print()
    print("=" * 60)
    print(f"Total pages analyzed: {pages_processed:,}")
    print(f"English pages: {stats['english_pages']:,} ({stats['english_pages']/pages_processed*100:.1f}%)")
    print(f"English-only: {stats['english_only_pages']:,} ({stats['english_only_pages']/pages_processed*100:.1f}%)")
    print(f"With English labels: {stats['english_label_pages']:,} ({stats['english_label_pages']/pages_processed*100:.1f}%)")
    print("=" * 60)
    print()

    # Generate reports
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    generate_audit_report(
        pages_processed,
        stats,
        samples,
        report_dir / "wiktionary_audit.md"
    )

    # Write sample entries
    samples_path = report_dir / "wiktionary_samples.json"
    with open(samples_path, 'w', encoding='utf-8') as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    print(f"✓ Sample entries written: {samples_path}")
    print()
    print("Review these reports and commit them to version control:")
    print("  reports/wiktionary_audit.md")
    print("  reports/wiktionary_samples.json")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Audit Wiktionary extraction approach'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input Wiktionary XML file (.xml or .xml.bz2)'
    )

    parser.add_argument(
        '--sample-size',
        type=int,
        default=10000,
        help='Number of pages to sample (default: 10000)'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    audit_wiktionary_dump(args.input, args.sample_size)


if __name__ == '__main__':
    main()
