#!/usr/bin/env python3
"""
Analyze frequency data structure and propose tier boundaries.

Reads the FrequencyWords en_50k.txt file and analyzes:
- Distribution of frequencies
- Proposed tier boundaries (10, 100, 1000, 10000, etc.)
- Coverage statistics
- Sample words at each tier boundary

Output: reports/frequency_analysis.md
"""

import sys
from pathlib import Path
from typing import List, Tuple
import json


def parse_frequency_file(freq_file: Path) -> List[Tuple[str, int]]:
    """Parse frequency file into list of (word, frequency) tuples."""
    entries = []

    with open(freq_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) >= 2:
                word = parts[0]
                try:
                    freq = int(parts[1])
                    entries.append((word, freq))
                except ValueError:
                    continue

    return entries


def analyze_tiers(entries: List[Tuple[str, int]]) -> dict:
    """Analyze tier boundaries and statistics."""
    tier_boundaries = [10, 100, 1000, 10000, 50000]

    tiers = {}
    total_freq = sum(freq for _, freq in entries)

    for i, boundary in enumerate(tier_boundaries):
        tier_name = f"tier_{i+1}"
        if i == 0:
            tier_words = entries[:boundary]
            tier_label = f"Top {boundary}"
        else:
            prev_boundary = tier_boundaries[i-1]
            tier_words = entries[prev_boundary:boundary]
            tier_label = f"{prev_boundary+1} to {boundary}"

        if not tier_words:
            continue

        tier_freq = sum(freq for _, freq in tier_words)
        tier_pct = (tier_freq / total_freq * 100) if total_freq > 0 else 0

        # Sample words (first 10 and last 10)
        sample_words = []
        if len(tier_words) <= 20:
            sample_words = [w for w, _ in tier_words]
        else:
            sample_words = [w for w, _ in tier_words[:10]] + ['...'] + [w for w, _ in tier_words[-10:]]

        tiers[tier_name] = {
            'label': tier_label,
            'boundary': boundary,
            'count': len(tier_words),
            'total_frequency': tier_freq,
            'coverage_percent': tier_pct,
            'sample_words': sample_words,
            'freq_range': (tier_words[-1][1], tier_words[0][1]) if tier_words else (0, 0)
        }

    # Everything else is "rare"
    if len(entries) > tier_boundaries[-1]:
        rare_words = entries[tier_boundaries[-1]:]
        rare_freq = sum(freq for _, freq in rare_words)
        rare_pct = (rare_freq / total_freq * 100) if total_freq > 0 else 0

        sample_words = []
        if len(rare_words) <= 20:
            sample_words = [w for w, _ in rare_words]
        else:
            sample_words = [w for w, _ in rare_words[:10]] + ['...']

        tiers['tier_rare'] = {
            'label': f"{tier_boundaries[-1]+1}+",
            'boundary': len(entries),
            'count': len(rare_words),
            'total_frequency': rare_freq,
            'coverage_percent': rare_pct,
            'sample_words': sample_words,
            'freq_range': (rare_words[-1][1], rare_words[0][1]) if rare_words else (0, 0)
        }

    return tiers


def generate_report(entries: List[Tuple[str, int]], tiers: dict, output_path: Path):
    """Generate markdown report."""
    total_words = len(entries)
    total_freq = sum(freq for _, freq in entries)

    lines = [
        "# Frequency Data Analysis",
        "",
        "## Overview",
        "",
        f"- **Total words**: {total_words:,}",
        f"- **Total frequency count**: {total_freq:,}",
        f"- **Source**: FrequencyWords (OpenSubtitles 2018)",
        "",
        "## Proposed Frequency Tiers",
        "",
        "Tiers based on orders of magnitude:",
        ""
    ]

    # Table header
    lines.extend([
        "| Tier | Rank Range | Word Count | Frequency Sum | Coverage % | Freq Range |",
        "|------|------------|------------|---------------|------------|------------|"
    ])

    # Table rows
    for tier_name in sorted(tiers.keys()):
        tier = tiers[tier_name]
        lines.append(
            f"| {tier['label']} | {tier['boundary']:,} | {tier['count']:,} | "
            f"{tier['total_frequency']:,} | {tier['coverage_percent']:.2f}% | "
            f"{tier['freq_range'][0]:,} - {tier['freq_range'][1]:,} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- **Top 10**: Ultra-common function words (the, of, and, to, etc.)",
        "- **Top 100**: Core vocabulary for basic communication",
        "- **Top 1,000**: Common everyday words",
        "- **Top 10,000**: Standard educated vocabulary",
        "- **Top 50,000**: Extensive vocabulary including technical terms",
        "- **Rare**: Everything else (not in top 50k)",
        "",
        "## Sample Words by Tier",
        ""
    ])

    for tier_name in sorted(tiers.keys()):
        tier = tiers[tier_name]
        lines.extend([
            f"### {tier['label']}",
            "",
            "Sample words:",
            "```"
        ])
        lines.extend(tier['sample_words'])
        lines.extend([
            "```",
            ""
        ])

    lines.extend([
        "## Usage in Filtering",
        "",
        "For kids' word lists:",
        "- Focus on **Top 1,000** to **Top 10,000** tiers",
        "- Combine with concrete noun categories from Wiktionary/WordNet",
        "- Filter out vulgar words even if high frequency",
        "",
        "For game word lists:",
        "- Include **Top 10,000** for common words",
        "- Optionally extend to **Top 50,000** for variety",
        "- Exclude archaic/obsolete even if they appear in frequency data",
        "",
        "## Integration Strategy",
        "",
        "1. Parse en_50k.txt into frequency tiers (1-5 + rare)",
        "2. During word list export, join on word",
        "3. Apply tier-based filters (e.g., `frequency_tier <= 4` for kids)",
        "4. Combine with existing POS, label, and category filters",
        ""
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_frequency_data.py <frequency_file>")
        print("Example: analyze_frequency_data.py data/raw/plus/en_50k.txt")
        sys.exit(1)

    freq_file = Path(sys.argv[1])
    if not freq_file.exists():
        print(f"Error: File not found: {freq_file}")
        sys.exit(1)

    print(f"-> Analyzing frequency data: {freq_file}")

    entries = parse_frequency_file(freq_file)
    print(f"  Parsed {len(entries):,} word entries")

    tiers = analyze_tiers(entries)
    print(f"  Generated {len(tiers)} frequency tiers")

    output_path = Path("reports/frequency_analysis.md")
    generate_report(entries, tiers, output_path)
    print(f"Report saved: {output_path}")

    # Also save tier data as JSON for programmatic use
    tier_json_path = Path("reports/frequency_tiers.json")
    tier_json = {
        tier_name: {
            'label': tier['label'],
            'rank_boundary': tier['boundary'],
            'word_count': tier['count'],
            'coverage_percent': tier['coverage_percent']
        }
        for tier_name, tier in tiers.items()
    }
    tier_json_path.write_text(json.dumps(tier_json, indent=2), encoding='utf-8')
    print(f"Tier data saved: {tier_json_path}")


if __name__ == '__main__':
    main()
