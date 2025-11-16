#!/usr/bin/env python3
"""
inspect_metadata.py - Explore metadata sidecar

Analyzes frequency tiers, labels, sources, and other metadata.
Useful for understanding data quality and distribution.
"""
import json
import random
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, Any


def load_metadata(meta_path: Path) -> Dict[str, Any]:
    """Load metadata JSON (stored as array, convert to dict)."""
    if not meta_path.exists():
        return {}

    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    # Convert list to dict keyed by word
    return {entry['word']: entry for entry in metadata_list}


def analyze_frequency_tiers(metadata: Dict[str, Any]) -> str:
    """Analyze frequency tier distribution."""
    tier_counts = Counter()

    for word, meta in metadata.items():
        tier = meta.get('frequency_tier')
        tier_counts[tier] += 1

    report = "## Frequency Tier Distribution\n\n"
    report += "| Tier | Count | Percentage |\n"
    report += "|------|------:|-----------:|\n"

    total = sum(tier_counts.values())

    # Sort by tier number (None at end)
    sorted_tiers = sorted([t for t in tier_counts.keys() if t is not None])
    if None in tier_counts:
        sorted_tiers.append(None)

    for tier in sorted_tiers:
        count = tier_counts[tier]
        pct = (count / total * 100) if total > 0 else 0
        tier_display = tier if tier is not None else 'N/A'
        report += f"| {tier_display} | {count:,} | {pct:.1f}% |\n"

    report += "\n"

    # Sample words from each tier
    report += "### Sample Words by Tier\n\n"

    for tier in sorted_tiers[:5]:  # Top 5 tiers
        tier_words = [w for w, m in metadata.items() if m.get('frequency_tier') == tier]
        sample = random.sample(tier_words, min(5, len(tier_words)))

        tier_display = tier if tier is not None else 'N/A'
        report += f"**Tier {tier_display}:** {', '.join(f'`{w}`' for w in sample)}  \n"

    report += "\n"
    return report


def analyze_sources(metadata: Dict[str, Any]) -> str:
    """Analyze source distribution."""
    source_counts = Counter()
    source_combos = Counter()

    for word, meta in metadata.items():
        sources = meta.get('sources', [])
        for source in sources:
            source_counts[source] += 1

        # Track source combinations
        combo = tuple(sorted(sources))
        source_combos[combo] += 1

    report = "## Source Distribution\n\n"
    report += "### Individual Sources\n\n"
    report += "| Source | Words |\n"
    report += "|--------|------:|\n"

    for source, count in source_counts.most_common():
        report += f"| {source} | {count:,} |\n"

    report += "\n### Source Combinations\n\n"
    report += "| Sources | Words |\n"
    report += "|---------|------:|\n"

    for combo, count in source_combos.most_common(10):
        combo_str = ', '.join(combo) if combo else 'None'
        report += f"| {combo_str} | {count:,} |\n"

    report += "\n"
    return report


def analyze_labels(metadata: Dict[str, Any]) -> str:
    """Analyze label distribution."""
    pos_counts = Counter()
    register_counts = Counter()
    domain_counts = Counter()

    for word, meta in metadata.items():
        labels = meta.get('labels', {})

        for pos in labels.get('pos', []):
            pos_counts[pos] += 1

        for reg in labels.get('register', []):
            register_counts[reg] += 1

        for dom in labels.get('domain', []):
            domain_counts[dom] += 1

    report = "## Label Distribution\n\n"

    if pos_counts:
        report += "### Part of Speech\n\n"
        report += "| POS | Words |\n"
        report += "|-----|------:|\n"
        for pos, count in pos_counts.most_common(15):
            report += f"| {pos} | {count:,} |\n"
        report += "\n"

    if register_counts:
        report += "### Register Labels\n\n"
        report += "| Register | Words |\n"
        report += "|----------|------:|\n"
        for reg, count in register_counts.most_common(15):
            report += f"| {reg} | {count:,} |\n"
        report += "\n"

    if domain_counts:
        report += "### Domain Labels\n\n"
        report += "| Domain | Words |\n"
        report += "|--------|------:|\n"
        for dom, count in domain_counts.most_common(15):
            report += f"| {dom} | {count:,} |\n"
        report += "\n"

    return report


def sample_rich_entries(metadata: Dict[str, Any]) -> str:
    """Sample entries with rich metadata."""
    # Find entries with lots of metadata
    rich_entries = []

    for word, meta in metadata.items():
        score = 0
        score += len(meta.get('sources', []))
        score += len(meta.get('labels', {}).get('pos', []))
        score += len(meta.get('labels', {}).get('domain', []))
        score += 1 if meta.get('frequency_tier') else 0
        score += 1 if meta.get('gloss') else 0

        if score >= 5:  # Threshold for "rich"
            rich_entries.append((word, meta, score))

    # Sort by richness score
    rich_entries.sort(key=lambda x: x[2], reverse=True)

    report = "## Sample Rich Entries\n\n"
    report += "These entries have extensive metadata (multiple sources, labels, glosses, etc.)\n\n"

    for word, meta, score in rich_entries[:10]:
        report += f"### `{word}` (richness: {score})\n\n"
        report += "```json\n"
        report += json.dumps(meta, indent=2, ensure_ascii=False)
        report += "\n```\n\n"

    return report


def generate_report(distribution: str = 'core'):
    """Generate metadata exploration report."""
    random.seed(42)  # Reproducible samples

    meta_path = Path(f'data/build/{distribution}/{distribution}.meta.json')

    report = f"# Metadata Exploration Report ({distribution.upper()})\n\n"
    report += f"Generated by `tools/inspect_metadata.py`\n\n"
    report += "This report analyzes the metadata sidecar in detail.\n\n"
    report += "---\n\n"

    # Load metadata
    metadata = load_metadata(meta_path)

    if not metadata:
        report += f"## Error\n\nMetadata not found at `{meta_path}`\n"
    else:
        report += f"**Total entries:** {len(metadata):,}\n\n"
        report += "---\n\n"

        report += analyze_frequency_tiers(metadata)
        report += "\n---\n\n"

        report += analyze_sources(metadata)
        report += "\n---\n\n"

        report += analyze_labels(metadata)
        report += "\n---\n\n"

        report += sample_rich_entries(metadata)

    # Write report
    output_path = Path(f'reports/metadata_exploration_{distribution}.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Metadata exploration report ({distribution}) written to {output_path}")
    return output_path


if __name__ == '__main__':
    import sys

    distribution = sys.argv[1] if len(sys.argv) > 1 else 'core'

    if distribution not in ['core', 'plus']:
        print(f"Error: distribution must be 'core' or 'plus', got '{distribution}'")
        sys.exit(1)

    generate_report(distribution)
