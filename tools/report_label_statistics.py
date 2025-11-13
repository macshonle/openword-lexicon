#!/usr/bin/env python3
"""
report_label_statistics.py - Generate comprehensive label statistics report

Analyzes extracted Wiktionary JSONL to show:
- Regional label coverage (en-GB, en-US, etc.)
- Register label coverage (vulgar, informal, etc.)
- Temporal label coverage (archaic, obsolete, etc.)
- Domain label coverage (medical, legal, etc.)
- Cross-tabulations (e.g., British + informal)

Generates report for version control and validation.

Usage:
    python report_label_statistics.py data/intermediate/plus/wikt.jsonl

Output:
    reports/label_statistics.md - Full statistics report
    reports/label_examples.json - Example words for each label
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set


def load_entries(jsonl_path: Path) -> List[Dict]:
    """Load entries from JSONL file."""
    entries = []

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                print(f"  Loading: {line_num:,} entries...", end='\r')
                sys.stdout.flush()

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                print(f"\nWarning: Line {line_num}: {e}", file=sys.stderr)

    print(f"  Loaded: {len(entries):,} entries    ")
    return entries


def analyze_labels(entries: List[Dict]) -> Dict:
    """Analyze label coverage and distribution."""

    stats = {
        'total_entries': len(entries),
        'entries_with_any_label': 0,
        'entries_with_region': 0,
        'entries_with_register': 0,
        'entries_with_temporal': 0,
        'entries_with_domain': 0,
        'region_counts': Counter(),
        'register_counts': Counter(),
        'temporal_counts': Counter(),
        'domain_counts': Counter(),
        'region_examples': defaultdict(list),
        'register_examples': defaultdict(list),
        'temporal_examples': defaultdict(list),
        'domain_examples': defaultdict(list),
        'label_combinations': Counter(),
        'pos_distribution': Counter(),
        'phrase_count': 0,
    }

    for entry in entries:
        word = entry.get('word', '')
        labels = entry.get('labels', {})
        pos_tags = entry.get('pos', [])
        is_phrase = entry.get('is_phrase', False)

        if is_phrase:
            stats['phrase_count'] += 1

        for pos in pos_tags:
            stats['pos_distribution'][pos] += 1

        has_any_label = bool(labels)
        if has_any_label:
            stats['entries_with_any_label'] += 1

        # Regional labels
        region_labels = labels.get('region', [])
        if region_labels:
            stats['entries_with_region'] += 1
            for region in region_labels:
                stats['region_counts'][region] += 1
                if len(stats['region_examples'][region]) < 20:
                    stats['region_examples'][region].append(word)

        # Register labels
        register_labels = labels.get('register', [])
        if register_labels:
            stats['entries_with_register'] += 1
            for register in register_labels:
                stats['register_counts'][register] += 1
                if len(stats['register_examples'][register]) < 20:
                    stats['register_examples'][register].append(word)

        # Temporal labels
        temporal_labels = labels.get('temporal', [])
        if temporal_labels:
            stats['entries_with_temporal'] += 1
            for temporal in temporal_labels:
                stats['temporal_counts'][temporal] += 1
                if len(stats['temporal_examples'][temporal]) < 20:
                    stats['temporal_examples'][temporal].append(word)

        # Domain labels
        domain_labels = labels.get('domain', [])
        if domain_labels:
            stats['entries_with_domain'] += 1
            for domain in domain_labels:
                stats['domain_counts'][domain] += 1
                if len(stats['domain_examples'][domain]) < 20:
                    stats['domain_examples'][domain].append(word)

        # Track label combinations (for cross-tabulation)
        if labels:
            combo_parts = []
            if region_labels:
                combo_parts.append(f"region:{','.join(sorted(region_labels))}")
            if register_labels:
                combo_parts.append(f"register:{','.join(sorted(register_labels))}")
            if temporal_labels:
                combo_parts.append(f"temporal:{','.join(sorted(temporal_labels))}")
            if domain_labels:
                combo_parts.append(f"domain:{','.join(sorted(domain_labels))}")

            if combo_parts:
                combo = " + ".join(combo_parts)
                stats['label_combinations'][combo] += 1

    return stats


def generate_statistics_report(stats: Dict, output_path: Path):
    """Generate markdown statistics report."""

    total = stats['total_entries']

    report = f"""# Wiktionary Label Statistics Report

Generated by `tools/report_label_statistics.py`

This report shows label coverage in the extracted Wiktionary data,
which determines what filtering capabilities we have for game-specific
word lists.

---

## Overall Coverage

**Total entries:** {total:,}

| Label Category | Entries | Percentage |
|----------------|--------:|-----------:|
| Any labels | {stats['entries_with_any_label']:,} | {stats['entries_with_any_label']/total*100:.1f}% |
| Regional labels | {stats['entries_with_region']:,} | {stats['entries_with_region']/total*100:.1f}% |
| Register labels | {stats['entries_with_register']:,} | {stats['entries_with_register']/total*100:.1f}% |
| Temporal labels | {stats['entries_with_temporal']:,} | {stats['entries_with_temporal']/total*100:.1f}% |
| Domain labels | {stats['entries_with_domain']:,} | {stats['entries_with_domain']/total*100:.1f}% |

---

## Regional Label Distribution

Regional labels enable filtering for games like Wordle (exclude British English).

| Region | Count | Percentage | Examples |
|--------|------:|-----------:|----------|
"""

    for region, count in stats['region_counts'].most_common():
        pct = count / total * 100
        examples = ', '.join(stats['region_examples'][region][:5])
        report += f"| {region} | {count:,} | {pct:.2f}% | {examples} |\n"

    if not stats['region_counts']:
        report += "| (none found) | 0 | 0.0% | - |\n"

    report += f"""
**Filtering Impact:** {'Good' if stats['entries_with_region'] > total * 0.05 else 'Warning: Limited'} - {
    f"{stats['entries_with_region']:,} words can be filtered by region"
    if stats['entries_with_region'] > 0
    else "No regional filtering possible"
}

---

## Register Label Distribution

Register labels enable filtering for age-appropriate content.

| Register | Count | Percentage | Examples |
|----------|------:|-----------:|----------|
"""

    for register, count in stats['register_counts'].most_common():
        pct = count / total * 100
        examples = ', '.join(stats['register_examples'][register][:5])
        report += f"| {register} | {count:,} | {pct:.2f}% | {examples} |\n"

    if not stats['register_counts']:
        report += "| (none found) | 0 | 0.0% | - |\n"

    report += f"""
**Filtering Impact:** {'Good' if stats['entries_with_register'] > total * 0.01 else 'Warning: Limited'} - {
    f"{stats['entries_with_register']:,} words can be filtered by register"
    if stats['entries_with_register'] > 0
    else "No register filtering possible"
}

---

## Temporal Label Distribution

Temporal labels enable filtering out archaic/obsolete words.

| Temporal | Count | Percentage | Examples |
|----------|------:|-----------:|----------|
"""

    for temporal, count in stats['temporal_counts'].most_common():
        pct = count / total * 100
        examples = ', '.join(stats['temporal_examples'][temporal][:5])
        report += f"| {temporal} | {count:,} | {pct:.2f}% | {examples} |\n"

    if not stats['temporal_counts']:
        report += "| (none found) | 0 | 0.0% | - |\n"

    report += f"""
**Filtering Impact:** {'Good' if stats['entries_with_temporal'] > total * 0.01 else 'Warning: Limited'} - {
    f"{stats['entries_with_temporal']:,} archaic/obsolete words can be excluded"
    if stats['entries_with_temporal'] > 0
    else "No temporal filtering possible"
}

---

## Domain Label Distribution

Domain labels enable filtering technical/specialized terms.

| Domain | Count | Percentage | Examples |
|--------|------:|-----------:|----------|
"""

    for domain, count in stats['domain_counts'].most_common(20):
        pct = count / total * 100
        examples = ', '.join(stats['domain_examples'][domain][:5])
        report += f"| {domain} | {count:,} | {pct:.2f}% | {examples} |\n"

    if not stats['domain_counts']:
        report += "| (none found) | 0 | 0.0% | - |\n"

    report += f"""
**Filtering Impact:** {'Good' if stats['entries_with_domain'] > total * 0.05 else 'Warning: Limited'} - {
    f"{stats['entries_with_domain']:,} technical terms can be filtered"
    if stats['entries_with_domain'] > 0
    else "No domain filtering possible"
}

---

## Part of Speech Distribution

| POS | Count | Percentage |
|-----|------:|-----------:|
"""

    for pos, count in stats['pos_distribution'].most_common(15):
        pct = count / total * 100
        report += f"| {pos} | {count:,} | {pct:.1f}% |\n"

    report += f"""
---

## Label Combinations

Top label combinations (useful for understanding data patterns):

| Combination | Count |
|-------------|------:|
"""

    for combo, count in stats['label_combinations'].most_common(20):
        report += f"| {combo} | {count:,} |\n"

    if not stats['label_combinations']:
        report += "| (none found) | 0 |\n"

    report += f"""
---

## Phrase Detection

- **Phrases (multi-word):** {stats['phrase_count']:,} ({stats['phrase_count']/total*100:.1f}%)
- **Single words:** {total - stats['phrase_count']:,} ({(total - stats['phrase_count'])/total*100:.1f}%)

---

## Game-Specific Filtering Feasibility

Based on label coverage, here's what's feasible:

### Wordle Filter (5-letter, no British English)
"""

    if stats['entries_with_region'] > 0:
        report += f"**Feasible** - {stats['region_counts'].get('en-GB', 0):,} British English words can be excluded\n"
    else:
        report += "Warning: **Limited** - No regional labels found, cannot exclude British English\n"

    report += "\n### 20 Questions (concrete nouns, age-appropriate)\n"

    if stats['entries_with_register'] > 0:
        vulgar = stats['register_counts'].get('vulgar', 0)
        offensive = stats['register_counts'].get('offensive', 0)
        report += f"**Feasible** - {vulgar + offensive:,} inappropriate words can be excluded\n"
    else:
        report += "Warning: **Limited** - No register labels found, limited content filtering\n"

    report += "\n### Crossword (allow archaic, obscure words)\n"

    if stats['entries_with_temporal'] > 0:
        report += f"**Feasible** - {stats['entries_with_temporal']:,} archaic words available\n"
    else:
        report += "Warning: **Limited** - No temporal labels found\n"

    report += f"""
---

## Recommendations

"""

    if stats['entries_with_any_label'] / total > 0.2:
        report += "**Label coverage is excellent** - Advanced filtering is feasible\n\n"
    elif stats['entries_with_any_label'] / total > 0.05:
        report += "**Label coverage is good** - Most filtering use cases are supported\n\n"
    else:
        report += "Warning: **Label coverage is limited** - Consider supplementing with other data sources\n\n"

    if stats['entries_with_region'] > total * 0.05:
        report += "Regional filtering (British/US) is well-supported\n\n"
    else:
        report += "Warning: Regional filtering may have gaps - review examples carefully\n\n"

    if stats['entries_with_register'] > total * 0.01:
        report += "Content filtering (vulgar/offensive) is well-supported\n\n"
    else:
        report += "Warning: Content filtering may have gaps - consider manual review\n\n"

    report += """
---

## Next Steps

1. Review example words in `reports/label_examples.json`
2. Test filters: `uv run python tools/filter_words.py --use-case wordle`
3. Compare with wiktextract: `uv run python tools/prototypes/compare_wikt_extractions.py`
4. Build distributions: `make build-plus`
5. Generate final word lists for your games
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Statistics report written: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate label statistics report from extracted Wiktionary data'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input JSONL file (wikt.jsonl or wikt_entries.jsonl)'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    print(f"Analyzing: {args.input}")
    print()

    entries = load_entries(args.input)
    print()

    print("Computing statistics...")
    stats = analyze_labels(entries)
    print()

    # Generate report
    report_path = Path("reports") / "label_statistics.md"
    generate_statistics_report(stats, report_path)

    # Write examples
    examples_path = Path("reports") / "label_examples.json"
    examples = {
        'region': dict(stats['region_examples']),
        'register': dict(stats['register_examples']),
        'temporal': dict(stats['temporal_examples']),
        'domain': dict(stats['domain_examples']),
    }

    with open(examples_path, 'w', encoding='utf-8') as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)

    print(f"Example words written: {examples_path}")
    print()
    print("Review these reports and commit them to version control:")
    print("  reports/label_statistics.md")
    print("  reports/label_examples.json")


if __name__ == '__main__':
    main()
