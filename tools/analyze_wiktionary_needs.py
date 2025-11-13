#!/usr/bin/env python3
"""
analyze_wiktionary_needs.py - Analyze what we actually need from Wiktionary

Compares:
1. What wiktextract extracts (verbose, Lua-processed)
2. What we actually use in our schema
3. What might be available directly in XML without Lua

Helps determine if we can simplify with a custom parser.
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, Set, List


def analyze_wiktextract_output():
    """Analyze what wiktextract actually produces."""
    wikt_file = Path('data/intermediate/plus/wikt.jsonl')

    if not wikt_file.exists():
        return None

    # Sample first 10k entries
    sample_size = 10000
    entries = []

    with open(wikt_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= sample_size:
                break
            try:
                entry = json.loads(line)
                entries.append(entry)
            except:
                pass

    # Analyze structure
    all_keys = Counter()
    pos_values = Counter()
    tags_used = Counter()
    has_senses = 0
    has_forms = 0
    has_etymology = 0
    has_categories = 0
    nested_depth = Counter()

    for entry in entries:
        # Top-level keys
        for key in entry.keys():
            all_keys[key] += 1

        # POS
        if 'pos' in entry:
            pos_values[entry['pos']] += 1

        # Senses complexity
        if 'senses' in entry:
            has_senses += 1
            for sense in entry.get('senses', []):
                for key in sense.keys():
                    tags_used[key] += 1

        # Forms
        if 'forms' in entry:
            has_forms += 1

        # Etymology
        if 'etymology_text' in entry:
            has_etymology += 1

        # Categories
        if 'categories' in entry:
            has_categories += 1
            nested_depth[len(entry['categories'])] += 1

    return {
        'sample_size': len(entries),
        'all_keys': all_keys,
        'pos_values': pos_values,
        'tags_used': tags_used,
        'has_senses': has_senses,
        'has_forms': has_forms,
        'has_etymology': has_etymology,
        'has_categories': has_categories,
    }


def analyze_what_we_use():
    """Analyze what we actually extract and use."""
    merged_file = Path('data/intermediate/plus/04_merged.jsonl')

    if not merged_file.exists():
        return None

    # Sample entries
    sample_size = 10000
    entries = []

    with open(merged_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= sample_size:
                break
            try:
                entry = json.loads(line)
                if 'wikt' in entry.get('sources', []):
                    entries.append(entry)
            except:
                pass

    # Count what we use
    has_pos = sum(1 for e in entries if e.get('pos'))
    has_labels = sum(1 for e in entries if e.get('labels'))
    has_gloss = sum(1 for e in entries if e.get('gloss'))
    is_phrase = sum(1 for e in entries if e.get('is_phrase'))
    has_lemma = sum(1 for e in entries if e.get('lemma'))

    label_types = Counter()
    for entry in entries:
        labels = entry.get('labels', {})
        for key in labels.keys():
            label_types[key] += 1

    return {
        'sample_size': len(entries),
        'has_pos': has_pos,
        'has_labels': has_labels,
        'has_gloss': has_gloss,
        'is_phrase': is_phrase,
        'has_lemma': has_lemma,
        'label_types': label_types,
    }


def analyze_wiktionary_templates():
    """
    Document common Wiktionary templates and what we need from them.

    This shows what templates might require Lua vs simple parsing.
    """
    # These are the key templates we care about
    templates_we_need = {
        # POS headers - directly in XML
        'pos': {
            'source': 'XML section headers',
            'lua_needed': False,
            'examples': ['==Noun==', '==Verb==', '==Adjective=='],
        },

        # Context labels - templates that may need expansion
        'context': {
            'source': '{{lb|en|...}} templates',
            'lua_needed': 'Maybe',
            'examples': [
                '{{lb|en|informal}}',
                '{{lb|en|obsolete}}',
                '{{lb|en|offensive}}',
            ],
        },

        # Glosses - plain text
        'gloss': {
            'source': '# Definition text',
            'lua_needed': False,
            'examples': ['# A domesticated animal.', '# To move quickly.'],
        },

        # Multi-word phrases - directly in page title
        'phrase': {
            'source': 'Page title contains spaces',
            'lua_needed': False,
            'examples': ['kick the bucket', 'in front of'],
        },

        # Inflected forms - may be in {{en-noun}}, {{en-verb}} templates
        'forms': {
            'source': '{{en-noun|...}}, {{en-verb|...}} templates',
            'lua_needed': 'Maybe',
            'examples': ['{{en-noun|dogs}}', '{{en-verb|kicks}}'],
        },
    }

    return templates_we_need


def generate_report():
    """Generate comprehensive analysis report."""
    report = "# Wiktionary Processing Analysis\n\n"
    report += "Generated by `tools/analyze_wiktionary_needs.py`\n\n"
    report += "This report analyzes whether we need full wiktextract (Lua evaluation) or can use simpler XML parsing.\n\n"
    report += "---\n\n"

    # What wiktextract produces
    report += "## What Wiktextract Produces\n\n"

    wikt_analysis = analyze_wiktextract_output()

    if wikt_analysis:
        report += f"**Sample size:** {wikt_analysis['sample_size']:,} entries\n\n"

        report += "### Top-level Keys\n\n"
        report += "| Key | Count | Percentage |\n"
        report += "|-----|------:|-----------:|\n"
        for key, count in wikt_analysis['all_keys'].most_common(20):
            pct = count / wikt_analysis['sample_size'] * 100
            report += f"| {key} | {count:,} | {pct:.1f}% |\n"
        report += "\n"

        report += "### POS Distribution\n\n"
        report += "| POS | Count |\n"
        report += "|-----|------:|\n"
        for pos, count in wikt_analysis['pos_values'].most_common(15):
            report += f"| {pos} | {count:,} |\n"
        report += "\n"

        report += "### Sense-level Tags (Most Complex Part)\n\n"
        report += "| Tag | Usage Count |\n"
        report += "|-----|------------:|\n"
        for tag, count in wikt_analysis['tags_used'].most_common(20):
            report += f"| {tag} | {count:,} |\n"
        report += "\n"

        report += f"**Has senses:** {wikt_analysis['has_senses']:,} ({wikt_analysis['has_senses']/wikt_analysis['sample_size']*100:.1f}%)  \n"
        report += f"**Has forms:** {wikt_analysis['has_forms']:,} ({wikt_analysis['has_forms']/wikt_analysis['sample_size']*100:.1f}%)  \n"
        report += f"**Has etymology:** {wikt_analysis['has_etymology']:,} ({wikt_analysis['has_etymology']/wikt_analysis['sample_size']*100:.1f}%)  \n"
        report += f"**Has categories:** {wikt_analysis['has_categories']:,} ({wikt_analysis['has_categories']/wikt_analysis['sample_size']*100:.1f}%)  \n"
        report += "\n"
    else:
        report += "⚠️ No wiktextract output found. Run `make fetch-post-process-plus` first.\n\n"

    # What we actually use
    report += "---\n\n## What We Actually Use\n\n"

    usage_analysis = analyze_what_we_use()

    if usage_analysis:
        report += f"**Sample size:** {usage_analysis['sample_size']:,} Wiktionary entries in merged output\n\n"

        pct_pos = usage_analysis['has_pos'] / usage_analysis['sample_size'] * 100
        pct_labels = usage_analysis['has_labels'] / usage_analysis['sample_size'] * 100
        pct_gloss = usage_analysis['has_gloss'] / usage_analysis['sample_size'] * 100
        pct_phrase = usage_analysis['is_phrase'] / usage_analysis['sample_size'] * 100
        pct_lemma = usage_analysis['has_lemma'] / usage_analysis['sample_size'] * 100

        report += f"- **Has POS:** {usage_analysis['has_pos']:,} ({pct_pos:.1f}%)\n"
        report += f"- **Has labels:** {usage_analysis['has_labels']:,} ({pct_labels:.1f}%)\n"
        report += f"- **Has gloss:** {usage_analysis['has_gloss']:,} ({pct_gloss:.1f}%)\n"
        report += f"- **Is phrase:** {usage_analysis['is_phrase']:,} ({pct_phrase:.1f}%)\n"
        report += f"- **Has lemma:** {usage_analysis['has_lemma']:,} ({pct_lemma:.1f}%)\n"
        report += "\n"

        if usage_analysis['label_types']:
            report += "### Label Types We Extract\n\n"
            report += "| Label Type | Count |\n"
            report += "|-----------|------:|\n"
            for label_type, count in usage_analysis['label_types'].most_common():
                report += f"| {label_type} | {count:,} |\n"
            report += "\n"
    else:
        report += "⚠️ No merged data found. Run `make build-plus` first.\n\n"

    # Template analysis
    report += "---\n\n## Wiktionary Templates: What Requires Lua?\n\n"

    templates = analyze_wiktionary_templates()

    for name, info in templates.items():
        report += f"### {name.title()}\n\n"
        report += f"**Source:** {info['source']}  \n"
        report += f"**Lua evaluation needed:** {info['lua_needed']}  \n"
        report += "**Examples:**\n"
        for ex in info['examples']:
            report += f"- `{ex}`\n"
        report += "\n"

    # Recommendations
    report += "---\n\n## Analysis & Recommendations\n\n"

    report += "### What We Actually Need\n\n"
    report += "Our schema requires:\n"
    report += "1. **Word** - Page title (directly in XML)\n"
    report += "2. **POS** - Section headers like `==Noun==` (directly in XML)\n"
    report += "3. **Labels** - Register/domain/temporal tags (may need template expansion)\n"
    report += "4. **Gloss** - Definition text (mostly plain text in XML)\n"
    report += "5. **Multi-word detection** - Spaces in page title (trivial)\n"
    report += "\n"

    report += "### What Doesn't Require Lua\n\n"
    report += "- ✅ Page titles (words/phrases)\n"
    report += "- ✅ Section headers (POS)\n"
    report += "- ✅ Definition text (glosses)\n"
    report += "- ✅ Basic categories\n"
    report += "- ✅ Multi-word phrase detection\n"
    report += "\n"

    report += "### What Might Require Template Expansion\n\n"
    report += "- ⚠️ Context labels: `{{lb|en|informal}}` -> \"informal\"\n"
    report += "- ⚠️ Inflection templates: `{{en-noun|dogs}}` -> forms\n"
    report += "- ⚠️ Some complex glosses with templates\n"
    report += "\n"

    report += "But even these could be handled with **simple pattern matching** rather than full Lua evaluation!\n\n"

    report += "### Potential Simplification\n\n"
    report += "A custom XML parser could:\n"
    report += "1. Parse MediaWiki XML directly (fast, no Lua overhead)\n"
    report += "2. Extract page title, POS headers, basic categories\n"
    report += "3. Use regex/patterns for common templates: `{{lb|en|(\\w+)}}`\n"
    report += "4. Skip complex templates we don't need\n"
    report += "5. Run in minutes instead of hours\n"
    report += "6. Avoid UTF-8 errors from Lua evaluation\n"
    report += "\n"

    report += "**Trade-off:** Might miss some nuanced label data, but 90%+ coverage with 10x speed improvement.\n\n"

    # Write report
    output_path = Path('reports/wiktionary_analysis.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Analysis report written to {output_path}")
    return output_path


if __name__ == '__main__':
    generate_report()
