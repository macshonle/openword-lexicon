#!/usr/bin/env python3
"""
Update WIKTIONARY-CORPUS.md with stats from collect_pos.py output.

Reads a stats file produced by `collect_pos.py --stats-output` and updates
the marked sections in the markdown file.

Marker format:
    <!-- AUTO:section_name -->
    ... content to be replaced ...
    <!-- /AUTO:section_name -->

Usage:
    uv run python tools/update_corpus_doc.py STATS_FILE MARKDOWN_FILE

The script will:
1. Parse the stats file
2. Find all AUTO markers in the markdown
3. Replace content between matching markers
4. Warn if expected sections are missing
"""

import argparse
import re
import sys
from pathlib import Path

# Expected AUTO sections that should exist in the markdown
EXPECTED_SECTIONS = {
    'last_updated',
    'overview',
    'headers_pos',
    'headers_structural',
    'template_pos',
    'categories',
}

# POS headers - these go in headers_pos section
POS_HEADERS = {
    'noun', 'verb', 'proper noun', 'adjective', 'adverb', 'phrase',
    'interjection', 'prepositional phrase', 'prefix', 'proverb', 'suffix',
    'pronoun', 'preposition', 'contraction', 'symbol', 'numeral',
    'conjunction', 'determiner', 'letter', 'particle', 'punctuation mark',
    'infix', 'interfix', 'participle', 'article', 'diacritical mark',
    'idiom', 'verb phrase', 'circumfix', 'postposition', 'verb form',
    'adverbial phrase', 'noun phrase', 'affix',
}


def parse_stats_file(path: Path) -> dict:
    """Parse the stats file into sections."""
    sections = {}
    current_section = None
    current_data = []

    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('=== ') and line.endswith(' ==='):
                # Save previous section
                if current_section:
                    sections[current_section] = current_data
                # Start new section
                current_section = line[4:-4].strip()
                current_data = []
            elif line and current_section:
                current_data.append(line)

    # Save last section
    if current_section:
        sections[current_section] = current_data

    return sections


def format_number(n: int) -> str:
    """Format number with thousands separators."""
    return f'{n:,}'


def generate_last_updated(stats: dict) -> str:
    """Generate last_updated section content."""
    overview = dict(line.split('\t', 1) for line in stats.get('OVERVIEW', []))
    date_str = overview.get('last_updated', 'unknown')
    return f'**Last updated:** {date_str}\n'


def generate_overview(stats: dict) -> str:
    """Generate overview table."""
    overview = dict(line.split('\t', 1) for line in stats.get('OVERVIEW', []))

    pages = int(overview.get('pages_processed', 0))
    english = int(overview.get('english_pages', 0))
    headers = int(overview.get('unique_headers', 0))
    template_pos = int(overview.get('unique_template_pos', 0))

    return f"""| Metric | Value |
|--------|-------|
| Total pages scanned | {format_number(pages)} |
| English pages | {format_number(english)} |
| Unique section headers | {headers} |
| Unique template POS values | {template_pos} |
"""


def generate_headers_pos(stats: dict) -> str:
    """Generate POS headers table."""
    headers = stats.get('HEADERS', [])

    lines = ['| Count | Header | Notes |', '|------:|--------|-------|']
    for line in headers:
        count, header = line.split('\t', 1)
        if header in POS_HEADERS:
            # Add notes for special cases
            notes = ''
            if header == 'phrase':
                notes = 'Generic multi-word'
            elif header == 'verb form':
                notes = 'As section header (rare)'
            elif header == 'adverbial phrase':
                notes = 'Only "on all fours"'
            lines.append(f'| {format_number(int(count))} | {header} | {notes} |')

    return '\n'.join(lines) + '\n'


def generate_headers_structural(stats: dict) -> str:
    """Generate structural (non-POS) headers table."""
    headers = stats.get('HEADERS', [])

    # Non-POS headers to include
    structural_headers = {
        'etymology', 'anagrams', 'translations', 'pronunciation',
        'derived terms', 'alternative forms', 'references', 'related terms',
        'see also', 'further reading', 'synonyms', 'statistics',
        'usage notes', 'antonyms', 'coordinate terms', 'hypernyms',
        'hyponyms', 'descendants', 'quotations', 'conjugation', 'meronyms',
        'holonyms', 'collocations', 'notes', 'abbreviations', 'gallery',
        'trivia', 'paronyms', 'external links', 'troponyms', 'citations',
        'multiple parts of speech',
    }
    # Also include etymology N and pronunciation N patterns
    etymology_pattern = re.compile(r'^etymology \d+$')
    pronunciation_pattern = re.compile(r'^pronunciation \d+$')

    lines = ['| Count | Header |', '|------:|--------|']
    for line in headers:
        count, header = line.split('\t', 1)
        is_structural = (
            header in structural_headers or
            etymology_pattern.match(header) or
            pronunciation_pattern.match(header)
        )
        if is_structural:
            lines.append(f'| {format_number(int(count))} | {header} |')

    return '\n'.join(lines) + '\n'


def generate_template_pos(stats: dict) -> str:
    """Generate template POS table."""
    template_pos = stats.get('TEMPLATE_POS', [])

    lines = ['| Count | Template POS | Notes |', '|------:|--------------|-------|']
    for line in template_pos:
        count, pos = line.split('\t', 1)
        # Add notes for common cases
        notes = ''
        if pos == 'noun form':
            notes = 'Plural/possessive forms'
        elif pos == 'verb form':
            notes = 'Conjugated forms'
        elif pos == 'noun':
            notes = 'Lemma entries'
        elif pos in ('verb forms', 'prefixes'):
            notes = '(plural variant)'
        lines.append(f'| {format_number(int(count))} | {pos} | {notes} |')

    return '\n'.join(lines) + '\n'


def generate_categories(stats: dict) -> str:
    """Generate categories table."""
    categories = stats.get('CATEGORIES', [])

    lines = ['| Count | Category |', '|------:|----------|']
    for line in categories:
        count, cat = line.split('\t', 1)
        lines.append(f'| {format_number(int(count))} | {cat} |')

    return '\n'.join(lines) + '\n'


def update_markdown(content: str, section: str, new_content: str) -> tuple[str, bool]:
    """
    Replace content between AUTO markers.

    Returns (updated_content, found) where found indicates if the marker was found.
    """
    start_marker = f'<!-- AUTO:{section} -->'
    end_marker = f'<!-- /AUTO:{section} -->'

    start_idx = content.find(start_marker)
    if start_idx == -1:
        return content, False

    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        return content, False

    # Find the newline after start marker
    content_start = content.find('\n', start_idx) + 1

    # Build new content
    new = (
        content[:content_start] +
        new_content +
        content[end_idx:]
    )
    return new, True


def main():
    parser = argparse.ArgumentParser(
        description='Update WIKTIONARY-CORPUS.md with stats from collect_pos.py'
    )
    parser.add_argument('stats_file', type=Path, help='Stats file from collect_pos.py')
    parser.add_argument('markdown_file', type=Path, help='Markdown file to update')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print updated content instead of writing')
    args = parser.parse_args()

    if not args.stats_file.exists():
        print(f"Error: Stats file not found: {args.stats_file}", file=sys.stderr)
        sys.exit(1)

    if not args.markdown_file.exists():
        print(f"Error: Markdown file not found: {args.markdown_file}", file=sys.stderr)
        sys.exit(1)

    # Parse stats
    stats = parse_stats_file(args.stats_file)
    print(f"Parsed stats: {list(stats.keys())}")

    # Read markdown
    content = args.markdown_file.read_text()

    # Generate and update each section
    generators = {
        'last_updated': generate_last_updated,
        'overview': generate_overview,
        'headers_pos': generate_headers_pos,
        'headers_structural': generate_headers_structural,
        'template_pos': generate_template_pos,
        'categories': generate_categories,
    }

    missing_sections = []
    updated_sections = []

    for section, generator in generators.items():
        new_content = generator(stats)
        content, found = update_markdown(content, section, new_content)
        if found:
            updated_sections.append(section)
        else:
            missing_sections.append(section)

    # Report results
    if updated_sections:
        print(f"Updated sections: {', '.join(updated_sections)}")

    if missing_sections:
        print(f"WARNING: Missing sections in markdown: {', '.join(missing_sections)}",
              file=sys.stderr)

    # Write or print
    if args.dry_run:
        print("\n--- DRY RUN: Updated content ---\n")
        print(content)
    else:
        args.markdown_file.write_text(content)
        print(f"Updated: {args.markdown_file}")


if __name__ == '__main__':
    main()
