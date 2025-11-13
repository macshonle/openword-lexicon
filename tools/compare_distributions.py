#!/usr/bin/env python3
"""
compare_distributions.py - Compare core and plus distributions

Identifies unique words, overlaps, and metadata differences between
the two distributions.
"""
import json
import random
from pathlib import Path
import marisa_trie
from typing import Set, Dict, Any


def load_trie(trie_path: Path) -> marisa_trie.Trie:
    """Load MARISA trie."""
    trie = marisa_trie.Trie()
    if trie_path.exists():
        trie.load(str(trie_path))
    return trie


def load_metadata(meta_path: Path) -> Dict[str, Any]:
    """Load metadata JSON (stored as array, convert to dict)."""
    if not meta_path.exists():
        return {}

    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    # Convert list to dict keyed by word
    return {entry['word']: entry for entry in metadata_list}


def compare_wordlists(core_words: Set[str], plus_words: Set[str]) -> str:
    """Compare word lists between distributions."""
    overlap = core_words & plus_words
    core_only = core_words - plus_words
    plus_only = plus_words - core_words

    report = "## Word List Comparison\n\n"
    report += f"**Core total:** {len(core_words):,}  \n"
    report += f"**Plus total:** {len(plus_words):,}  \n"
    report += f"**Overlap:** {len(overlap):,}  \n"
    report += f"**Core-only:** {len(core_only):,}  \n"
    report += f"**Plus-only:** {len(plus_only):,}  \n"
    report += "\n"

    # Sample core-only words
    if core_only:
        sample = random.sample(sorted(core_only), min(20, len(core_only)))
        report += "### Sample Core-Only Words\n\n"
        report += ', '.join(f'`{w}`' for w in sample) + "\n\n"

    # Sample plus-only words
    if plus_only:
        sample = random.sample(sorted(plus_only), min(20, len(plus_only)))
        report += "### Sample Plus-Only Words\n\n"
        report += ', '.join(f'`{w}`' for w in sample) + "\n\n"

    return report


def compare_metadata(core_meta: Dict, plus_meta: Dict, overlap_words: Set[str]) -> str:
    """Compare metadata for overlapping words."""
    # Count metadata differences
    diff_freq_tier = 0
    diff_sources = 0
    diff_labels = 0

    examples = []

    for word in sorted(overlap_words):
        if word not in core_meta or word not in plus_meta:
            continue

        core_entry = core_meta[word]
        plus_entry = plus_meta[word]

        has_diff = False
        diffs = []

        # Compare frequency tier
        if core_entry.get('frequency_tier') != plus_entry.get('frequency_tier'):
            diff_freq_tier += 1
            has_diff = True
            diffs.append(f"freq_tier: {core_entry.get('frequency_tier')} -> {plus_entry.get('frequency_tier')}")

        # Compare sources
        core_sources = set(core_entry.get('sources', []))
        plus_sources = set(plus_entry.get('sources', []))
        if core_sources != plus_sources:
            diff_sources += 1
            has_diff = True
            diffs.append(f"sources: {core_sources} -> {plus_sources}")

        # Compare labels
        core_labels = core_entry.get('labels', {})
        plus_labels = plus_entry.get('labels', {})
        if core_labels != plus_labels:
            diff_labels += 1
            has_diff = True

        if has_diff and len(examples) < 10:
            examples.append({
                'word': word,
                'diffs': diffs,
                'core': core_entry,
                'plus': plus_entry
            })

    report = "## Metadata Comparison (Overlapping Words)\n\n"
    report += f"**Words with different frequency tiers:** {diff_freq_tier:,}  \n"
    report += f"**Words with different sources:** {diff_sources:,}  \n"
    report += f"**Words with different labels:** {diff_labels:,}  \n"
    report += "\n"

    if examples:
        report += "### Example Differences\n\n"
        for ex in examples:
            report += f"**`{ex['word']}`**\n"
            for diff in ex['diffs']:
                report += f"- {diff}\n"
            report += "\n"

    return report


def analyze_sources(core_meta: Dict, plus_meta: Dict) -> str:
    """Analyze source differences."""
    from collections import Counter

    core_sources = Counter()
    plus_sources = Counter()

    for meta in core_meta.values():
        for src in meta.get('sources', []):
            core_sources[src] += 1

    for meta in plus_meta.values():
        for src in meta.get('sources', []):
            plus_sources[src] += 1

    report = "## Source Usage Comparison\n\n"
    report += "| Source | Core | Plus | Difference |\n"
    report += "|--------|-----:|-----:|-----------:|\n"

    all_sources = set(core_sources.keys()) | set(plus_sources.keys())

    for source in sorted(all_sources):
        core_count = core_sources.get(source, 0)
        plus_count = plus_sources.get(source, 0)
        diff = plus_count - core_count

        diff_str = f"+{diff:,}" if diff > 0 else f"{diff:,}"
        report += f"| {source} | {core_count:,} | {plus_count:,} | {diff_str} |\n"

    report += "\n"
    return report


def generate_report():
    """Generate distribution comparison report."""
    random.seed(42)  # Reproducible samples

    report = "# Distribution Comparison Report\n\n"
    report += "Generated by `tools/compare_distributions.py`\n\n"
    report += "This report compares the core and plus distributions.\n\n"
    report += "---\n\n"

    # Load tries
    core_trie_path = Path('data/build/core/core.trie')
    plus_trie_path = Path('data/build/plus/plus.trie')

    core_meta_path = Path('data/build/core/core.meta.json')
    plus_meta_path = Path('data/build/plus/plus.meta.json')

    if not core_trie_path.exists():
        report += "⚠️ Core trie not found. Run `make build-core` first.\n"
        return

    if not plus_trie_path.exists():
        report += "⚠️ Plus trie not found. Run `make build-plus` first.\n"
        return

    # Load data
    core_trie = load_trie(core_trie_path)
    plus_trie = load_trie(plus_trie_path)

    core_meta = load_metadata(core_meta_path)
    plus_meta = load_metadata(plus_meta_path)

    # Get word sets
    core_words = set(core_trie)
    plus_words = set(plus_trie)
    overlap = core_words & plus_words

    # Generate comparisons
    report += compare_wordlists(core_words, plus_words)
    report += "\n---\n\n"

    report += compare_metadata(core_meta, plus_meta, overlap)
    report += "\n---\n\n"

    report += analyze_sources(core_meta, plus_meta)

    # Write report
    output_path = Path('reports/distribution_comparison.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Distribution comparison report written to {output_path}")
    return output_path


if __name__ == '__main__':
    generate_report()
