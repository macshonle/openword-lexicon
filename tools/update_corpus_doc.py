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
    'pseudo_pos_analysis',
    'phrase_types',
    'aggregate_groups',
    'unknown_pos',
    'header_typos',
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
    """Generate structural (non-POS) headers table.

    Groups numbered variants (etymology 1, etymology 2, etc.) into a single
    'etymology (all)' entry with combined count.
    """
    headers = stats.get('HEADERS', [])

    # Non-POS headers to include (excluding etymology/pronunciation base forms
    # which we'll handle specially)
    structural_headers = {
        'anagrams', 'translations',
        'derived terms', 'alternative forms', 'references', 'related terms',
        'see also', 'further reading', 'synonyms', 'statistics',
        'usage notes', 'antonyms', 'coordinate terms', 'hypernyms',
        'hyponyms', 'descendants', 'quotations', 'conjugation', 'meronyms',
        'holonyms', 'collocations', 'notes', 'abbreviations', 'gallery',
        'trivia', 'paronyms', 'external links', 'troponyms', 'citations',
        'multiple parts of speech',
    }
    # Patterns for numbered variants
    etymology_pattern = re.compile(r'^etymology( \d+)?$')
    pronunciation_pattern = re.compile(r'^pronunciation( \d+)?$')

    # First pass: aggregate etymology and pronunciation counts
    etymology_total = 0
    pronunciation_total = 0
    other_structural = []

    for line in headers:
        count, header = line.split('\t', 1)
        count_int = int(count)

        if etymology_pattern.match(header):
            etymology_total += count_int
        elif pronunciation_pattern.match(header):
            pronunciation_total += count_int
        elif header in structural_headers:
            other_structural.append((count_int, header))

    # Build output with aggregated entries first, then others sorted by count
    lines = ['| Count | Header |', '|------:|--------|']

    # Add aggregated entries
    if etymology_total > 0:
        lines.append(f'| {format_number(etymology_total)} | etymology (all) |')
    if pronunciation_total > 0:
        lines.append(f'| {format_number(pronunciation_total)} | pronunciation (all) |')

    # Add other structural headers sorted by count (descending)
    for count_int, header in sorted(other_structural, key=lambda x: -x[0]):
        lines.append(f'| {format_number(count_int)} | {header} |')

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


def generate_pseudo_pos_analysis(stats: dict) -> str:
    """Generate pseudo-POS analysis section."""
    pseudo_data = stats.get('PSEUDO_POS_ONLY', [])

    lines = [
        'Pages that have **only** pseudo-POS headers (no real POS like noun, verb, etc.):',
        '',
        '| Pseudo-POS | Count | Sample Entries |',
        '|------------|------:|----------------|',
    ]

    for line in pseudo_data:
        parts = line.split('\t')
        if len(parts) >= 2:
            pseudo_type = parts[0]
            count = int(parts[1])
            samples = parts[2] if len(parts) > 2 else ''
            # Show first 5 samples
            sample_list = samples.split(',')[:5] if samples else []
            samples_str = ', '.join(sample_list) if sample_list else '(none)'
            lines.append(f'| {pseudo_type} | {format_number(count)} | {samples_str} |')

    return '\n'.join(lines) + '\n'


def generate_phrase_types(stats: dict) -> str:
    """Generate phrase type breakdown section."""
    phrase_data = stats.get('PHRASE_TYPES', [])

    lines = [
        '| Phrase Type | Count |',
        '|-------------|------:|',
    ]

    for line in phrase_data:
        parts = line.split('\t')
        if len(parts) >= 2:
            phrase_type = parts[0]
            count = int(parts[1])
            lines.append(f'| {phrase_type} | {format_number(count)} |')

    return '\n'.join(lines) + '\n'


def generate_aggregate_groups(stats: dict) -> str:
    """Generate aggregate groupings section."""
    agg_data = stats.get('AGGREGATE_GROUPS', [])

    # Parse into dict
    agg_dict = {}
    for line in agg_data:
        parts = line.split('\t')
        if len(parts) >= 2:
            agg_dict[parts[0]] = int(parts[1])

    lines = [
        'Potential groupings for normalization:',
        '',
        '| Grouping | Components | Total |',
        '|----------|------------|------:|',
        f"| Affix | prefix, suffix, infix, interfix, circumfix, affix | {format_number(agg_dict.get('affix', 0))} |",
        f"| Symbol | symbol, punctuation mark, diacritical mark | {format_number(agg_dict.get('symbol', 0))} |",
        f"| Determiner | determiner, article | {format_number(agg_dict.get('determiner', 0))} |",
        f"| Determiner/Numeral | determiner, article, numeral | {format_number(agg_dict.get('determiner_numeral', 0))} |",
    ]

    return '\n'.join(lines) + '\n'


def generate_unknown_pos(stats: dict) -> str:
    """Generate unknown POS entries section."""
    unknown_data = stats.get('UNKNOWN_POS', [])

    # Parse count and samples
    count = 0
    samples = []
    for line in unknown_data:
        parts = line.split('\t', 1)
        if parts[0] == 'count':
            count = int(parts[1]) if len(parts) > 1 else 0
        elif parts[0] == 'samples':
            samples = parts[1].split(',') if len(parts) > 1 else []

    lines = [
        f'Pages with section headers but no recognized POS: **{format_number(count)}**',
        '',
    ]

    if samples:
        lines.append('Sample entries: ' + ', '.join(samples[:10]))
    else:
        lines.append('No samples collected.')

    return '\n'.join(lines) + '\n'


def generate_header_typos(stats: dict) -> str:
    """Generate header typos table with page lists for wiki editing."""
    typo_data = stats.get('HEADER_TYPOS', [])

    lines = [
        '| Count | Header | Likely Intended | Pages |',
        '|------:|--------|-----------------|-------|',
    ]

    # Parse typo data: typo<TAB>intended<TAB>count<TAB>pages
    typos_with_pages = []
    for line in typo_data:
        parts = line.split('\t')
        if len(parts) >= 3:
            typo = parts[0]
            intended = parts[1]
            count = int(parts[2])
            pages = parts[3].split(',') if len(parts) > 3 and parts[3] else []
            if count > 0:
                typos_with_pages.append((count, typo, intended, pages))

    # Sort by count descending
    for count, typo, intended, pages in sorted(typos_with_pages, key=lambda x: -x[0]):
        # Format pages as wiki links
        page_links = ', '.join(f'[[{p}]]' for p in pages)
        lines.append(f'| {count} | {typo} | {intended} | {page_links} |')

    if len(lines) == 2:  # Only header rows
        lines.append('| - | (none found) | - | - |')

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
        'pseudo_pos_analysis': generate_pseudo_pos_analysis,
        'phrase_types': generate_phrase_types,
        'aggregate_groups': generate_aggregate_groups,
        'unknown_pos': generate_unknown_pos,
        'header_typos': generate_header_typos,
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
