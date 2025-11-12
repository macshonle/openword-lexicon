#!/usr/bin/env python3
"""
Analyze syllable data availability in Wiktionary dump.

Scans Wiktionary XML to find entries with explicit syllable information:
- {{hyphenation|...}} templates
- IPA pronunciations with syllable markers (.)
- Explicit syllable count annotations

Output: reports/syllable_analysis.md
"""

import sys
import re
import bz2
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple


# Patterns to detect syllable information
HYPHENATION_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|([^}]+)\}\}', re.IGNORECASE)
IPA_SYLLABLE = re.compile(r'\{\{IPA\|([^}]+)\}\}', re.IGNORECASE)
SYLLABLE_MARKER = re.compile(r'[ˈˌ\.]')  # Primary stress, secondary stress, syllable boundary


def extract_page_content(xml_file: Path, sample_size: int = 10000) -> List[Tuple[str, str]]:
    """Extract sample pages from Wiktionary dump."""
    pages = []
    current_title = None
    current_text = []
    in_text = False

    count = 0

    # Read BZ2 compressed file
    with bz2.open(xml_file, 'rt', encoding='utf-8') as f:
        for line in f:
            if '<title>' in line:
                current_title = line.split('<title>')[1].split('</title>')[0]
            elif '<text' in line:
                in_text = True
                # Check if text content is on same line
                if '</text>' in line:
                    text_content = line.split('>')[1].split('</text>')[0]
                    current_text = [text_content]
                    in_text = False
                else:
                    # Extract any text on this line after the tag
                    parts = line.split('>', 1)
                    if len(parts) > 1:
                        current_text = [parts[1].rstrip('\n')]
            elif '</text>' in line:
                in_text = False
                current_text.append(line.split('</text>')[0])

                if current_title:
                    pages.append((current_title, ''.join(current_text)))
                    count += 1

                    if count >= sample_size:
                        break

                current_title = None
                current_text = []
            elif in_text:
                current_text.append(line)

    return pages


def analyze_syllable_info(pages: List[Tuple[str, str]]) -> Dict:
    """Analyze syllable information in pages."""
    stats = {
        'total_pages': len(pages),
        'with_hyphenation': 0,
        'with_ipa_syllables': 0,
        'with_either': 0,
        'hyphenation_examples': [],
        'ipa_examples': [],
        'hyphenation_formats': Counter(),
    }

    for title, text in pages:
        has_hyphenation = False
        has_ipa = False

        # Check for hyphenation templates
        hyphenation_matches = HYPHENATION_TEMPLATE.findall(text)
        if hyphenation_matches:
            has_hyphenation = True
            stats['with_hyphenation'] += 1

            # Store examples (up to 20)
            if len(stats['hyphenation_examples']) < 20:
                for match in hyphenation_matches:
                    stats['hyphenation_examples'].append((title, match))
                    # Count separator formats
                    if '|' in match:
                        stats['hyphenation_formats']['pipe_separated'] += 1
                    if '·' in match or '•' in match:
                        stats['hyphenation_formats']['dot_separated'] += 1

        # Check for IPA with syllable markers
        ipa_matches = IPA_SYLLABLE.findall(text)
        for ipa in ipa_matches:
            if SYLLABLE_MARKER.search(ipa):
                has_ipa = True
                if len(stats['ipa_examples']) < 20:
                    stats['ipa_examples'].append((title, ipa))

        if has_ipa:
            stats['with_ipa_syllables'] += 1

        if has_hyphenation or has_ipa:
            stats['with_either'] += 1

    return stats


def generate_report(stats: Dict, output_path: Path):
    """Generate markdown report."""
    lines = [
        "# Syllable Data Analysis",
        "",
        "## Overview",
        "",
        f"Analyzed {stats['total_pages']:,} Wiktionary pages for syllable information.",
        "",
        "## Availability",
        "",
        f"- **Pages with hyphenation templates**: {stats['with_hyphenation']:,} ({stats['with_hyphenation']/stats['total_pages']*100:.2f}%)",
        f"- **Pages with IPA syllable markers**: {stats['with_ipa_syllables']:,} ({stats['with_ipa_syllables']/stats['total_pages']*100:.2f}%)",
        f"- **Pages with either**: {stats['with_either']:,} ({stats['with_either']/stats['total_pages']*100:.2f}%)",
        "",
        "## Hyphenation Template Formats",
        ""
    ]

    if stats['hyphenation_formats']:
        for fmt, count in stats['hyphenation_formats'].most_common():
            lines.append(f"- **{fmt}**: {count:,} occurrences")
    else:
        lines.append("No hyphenation formats found.")

    lines.extend([
        "",
        "## Hyphenation Examples",
        "",
        "Sample words with hyphenation templates:",
        ""
    ])

    for title, hyphenation in stats['hyphenation_examples'][:20]:
        # Try to parse syllable count
        parts = hyphenation.split('|')
        syllable_parts = [p for p in parts if p and 'lang=' not in p.lower()]
        lines.append(f"- **{title}**: `{hyphenation}` ({len(syllable_parts)} syllables)")

    lines.extend([
        "",
        "## IPA Syllable Examples",
        "",
        "Sample words with IPA syllable markers:",
        ""
    ])

    for title, ipa in stats['ipa_examples'][:20]:
        lines.append(f"- **{title}**: `{ipa}`")

    lines.extend([
        "",
        "## Extraction Strategy",
        "",
        "### Recommended Approach",
        "",
        "1. **Use hyphenation templates when available**",
        "   - Extract `{{hyphenation|...}}` content",
        "   - Count pipe-separated segments (excluding lang= parameters)",
        "   - Store as explicit syllable count",
        "",
        "2. **Only include explicit data**",
        "   - Do NOT estimate syllable counts",
        "   - Only store count when hyphenation template exists",
        "   - Leave syllable field null/absent for words without explicit data",
        "",
        "3. **Integration with scanner parser**",
        "   - Add optional `syllables` field to JSONL output",
        "   - Only populate when hyphenation template found",
        "   - Format: `\"syllables\": 3` (integer count)",
        "",
        "### Implementation",
        "",
        "```python",
        "# In wiktionary_scanner_parser.py",
        "HYPHENATION_RE = re.compile(r'\\{\\{(?:hyphenation|hyph)\\|([^}]+)\\}\\}', re.I)",
        "",
        "def extract_syllable_count(text: str) -> Optional[int]:",
        "    \"\"\"Extract syllable count from hyphenation template.\"\"\"",
        "    match = HYPHENATION_RE.search(text)",
        "    if not match:",
        "        return None",
        "    ",
        "    # Parse hyphenation content",
        "    content = match.group(1)",
        "    parts = content.split('|')",
        "    ",
        "    # Count syllables (exclude parameters like lang=en)",
        "    syllables = [p for p in parts if p.strip() and '=' not in p]",
        "    ",
        "    return len(syllables) if syllables else None",
        "```",
        "",
        "### Output Format",
        "",
        "Enhanced JSONL with optional syllable field:",
        "",
        "```json",
        "{",
        "  \"word\": \"example\",",
        "  \"pos\": [\"noun\"],",
        "  \"labels\": {...},",
        "  \"is_phrase\": false,",
        "  \"syllables\": 3,  // Only present when hyphenation template found",
        "  \"sources\": [\"wikt\"]",
        "}",
        "```",
        ""
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_syllable_data.py <wiktionary_dump.xml.bz2> [sample_size]")
        print("Example: analyze_syllable_data.py data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 10000")
        sys.exit(1)

    dump_file = Path(sys.argv[1])
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10000

    if not dump_file.exists():
        print(f"Error: File not found: {dump_file}")
        sys.exit(1)

    print(f"→ Analyzing syllable data from Wiktionary dump")
    print(f"  Sample size: {sample_size:,} pages")

    pages = extract_page_content(dump_file, sample_size)
    print(f"  Extracted {len(pages):,} pages")

    stats = analyze_syllable_info(pages)
    print(f"  Found syllable data in {stats['with_either']:,} pages")

    output_path = Path("reports/syllable_analysis.md")
    generate_report(stats, output_path)
    print(f"✓ Report saved: {output_path}")


if __name__ == '__main__':
    main()
