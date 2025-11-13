#!/usr/bin/env python3
"""
filter_game_words.py - Filter and score words for games like 20 Questions

Combines multiple metadata dimensions to identify suitable game words:
- Concrete nouns (things you can see/touch)
- Common/familiar (high frequency)
- Age appropriate (family-friendly)
- Avoid adult content (sexual, drugs, violence)
- Avoid jargon (technical/specialized)

Outputs ranked word lists for manual review and use.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


# Adult/inappropriate domains to exclude
ADULT_DOMAINS = {
    'sexuality', 'sex', 'pornography', 'prostitution', 'erotica',
    'drugs', 'narcotics', 'cannabis', 'recreational drugs',
}

# Adult/inappropriate keywords in glosses or categories
ADULT_KEYWORDS = {
    'sexual', 'sex', 'genital', 'penis', 'vagina', 'breast', 'anus',
    'condom', 'dildo', 'vibrator', 'pornography', 'porn', 'erotic',
    'drug', 'cocaine', 'heroin', 'marijuana', 'cannabis', 'narcotic',
    'alcohol', 'beer', 'wine', 'vodka', 'whiskey', 'drunk',
    'violence', 'weapon', 'gun', 'rifle', 'pistol', 'bomb', 'explosive',
    'slur', 'racial', 'ethnic', 'offensive',
}

# Technical/jargon domains to deprioritize
JARGON_DOMAINS = {
    'mathematics', 'chemistry', 'physics', 'medicine', 'anatomy',
    'biology', 'botany', 'zoology', 'geology', 'astronomy',
    'computing', 'programming', 'networking', 'database',
    'law', 'legal', 'military', 'nautical', 'aviation',
}

# Registers to exclude
EXCLUDE_REGISTERS = {
    'vulgar', 'offensive', 'derogatory', 'slang', 'euphemistic'
}

# Temporal labels to deprioritize
ARCHAIC_TEMPORAL = {
    'archaic', 'obsolete', 'dated', 'historical'
}


def load_metadata(meta_path: Path) -> Dict[str, Dict]:
    """Load metadata JSON (array format, convert to dict)."""
    if not meta_path.exists():
        return {}

    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    # Convert list to dict keyed by word
    return {entry['word']: entry for entry in metadata_list}


def is_concrete_noun(entry: Dict) -> bool:
    """Check if entry is a concrete noun."""
    # Must be a noun
    if 'noun' not in entry.get('pos', []):
        return False

    # Check concreteness field
    concreteness = entry.get('concreteness')
    if concreteness == 'concrete':
        return True
    elif concreteness == 'abstract':
        return False

    # If concreteness not set, use heuristics
    # Proper nouns are usually concrete
    labels = entry.get('labels', {})

    # Abstract concepts often have these domains
    domain = set(labels.get('domain', []))
    if domain & {'philosophy', 'religion', 'psychology', 'emotion'}:
        return False

    # Default: assume concrete if no clear abstract indicators
    return True


def is_age_appropriate(entry: Dict) -> bool:
    """Check if word is age appropriate (family-friendly)."""
    word = entry.get('word', '')
    labels = entry.get('labels', {})

    # Check register labels
    register = set(labels.get('register', []))
    if register & EXCLUDE_REGISTERS:
        return False

    # Check domain labels
    domain = set(labels.get('domain', []))
    if domain & ADULT_DOMAINS:
        return False

    # Check for adult keywords in word itself
    word_lower = word.lower()
    if any(kw in word_lower for kw in ADULT_KEYWORDS):
        return False

    return True


def get_frequency_score(entry: Dict) -> int:
    """Score based on frequency tier (higher = more common)."""
    tier = entry.get('frequency_tier', 'rare')

    tier_scores = {
        'top10': 100,
        'top100': 90,
        'top1k': 80,
        'top10k': 70,
        'top100k': 50,
        'rare': 10,
    }

    return tier_scores.get(tier, 0)


def get_jargon_penalty(entry: Dict) -> int:
    """Penalty for technical/jargon words (higher = more jargon)."""
    labels = entry.get('labels', {})

    # Check domain labels
    domain = set(labels.get('domain', []))
    if domain & JARGON_DOMAINS:
        return -30

    # Check temporal labels (archaic = less familiar)
    temporal = set(labels.get('temporal', []))
    if temporal & ARCHAIC_TEMPORAL:
        return -20

    return 0


def calculate_game_score(entry: Dict) -> int:
    """Calculate overall suitability score for game word."""
    score = 0

    # Frequency score (0-100)
    score += get_frequency_score(entry)

    # Concreteness bonus
    if entry.get('concreteness') == 'concrete':
        score += 20

    # Jargon penalty
    score += get_jargon_penalty(entry)

    # Word length penalty (too long = harder to guess)
    word_len = len(entry.get('word', ''))
    if word_len > 12:
        score -= 10
    elif word_len > 15:
        score -= 20

    return score


def filter_game_words(
    meta_path: Path,
    min_score: int = 50,
    max_words: int = 1000
) -> List[Tuple[str, int, Dict]]:
    """
    Filter and score words suitable for games.

    Returns:
        List of (word, score, entry) tuples, sorted by score descending
    """
    metadata = load_metadata(meta_path)

    candidates = []

    for word, entry in metadata.items():
        # Hard filters
        if not is_concrete_noun(entry):
            continue

        if not is_age_appropriate(entry):
            continue

        # Skip multi-word phrases for 20 questions
        if entry.get('is_phrase', False):
            continue

        # Calculate score
        score = calculate_game_score(entry)

        if score >= min_score:
            candidates.append((word, score, entry))

    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Return top N
    return candidates[:max_words]


def generate_report(
    candidates: List[Tuple[str, int, Dict]],
    output_path: Path
):
    """Generate markdown report for manual review."""
    report = "# Game Word List - Manual Review\n\n"
    report += "Generated by `tools/filter_game_words.py`\n\n"
    report += "Words filtered and scored for suitability in games like 20 Questions.\n\n"
    report += f"**Total candidates:** {len(candidates)}\n\n"
    report += "---\n\n"

    # Score distribution
    score_ranges = defaultdict(int)
    for _, score, _ in candidates:
        if score >= 90:
            score_ranges['90-100'] += 1
        elif score >= 80:
            score_ranges['80-89'] += 1
        elif score >= 70:
            score_ranges['70-79'] += 1
        elif score >= 60:
            score_ranges['60-69'] += 1
        else:
            score_ranges['50-59'] += 1

    report += "## Score Distribution\n\n"
    report += "| Score Range | Count |\n"
    report += "|-------------|------:|\n"
    for range_name in ['90-100', '80-89', '70-79', '60-69', '50-59']:
        count = score_ranges.get(range_name, 0)
        report += f"| {range_name} | {count} |\n"
    report += "\n---\n\n"

    # Top candidates
    report += "## Top Candidates (Score 90+)\n\n"
    report += "Review these first - highest quality words.\n\n"

    for word, score, entry in candidates[:100]:
        if score < 90:
            break

        freq = entry.get('frequency_tier', 'unknown')
        concrete = entry.get('concreteness', 'unknown')
        sources = ', '.join(entry.get('sources', []))

        report += f"### `{word}` (Score: {score})\n\n"
        report += f"- **Frequency:** {freq}\n"
        report += f"- **Concreteness:** {concrete}\n"
        report += f"- **Sources:** {sources}\n"

        labels = entry.get('labels', {})
        if labels:
            report += f"- **Labels:** {labels}\n"

        report += "\n"

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Report written to {output_path}")


def export_wordlist(
    candidates: List[Tuple[str, int, Dict]],
    output_path: Path,
    with_scores: bool = False
):
    """Export simple word list for use."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for word, score, _ in candidates:
            if with_scores:
                f.write(f"{word}\t{score}\n")
            else:
                f.write(f"{word}\n")

    print(f"Word list written to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Filter and score words for games like 20 Questions'
    )

    parser.add_argument(
        '--distribution',
        choices=['core', 'plus'],
        default='core',
        help='Which distribution to filter (default: core)'
    )

    parser.add_argument(
        '--min-score',
        type=int,
        default=50,
        help='Minimum score threshold (default: 50)'
    )

    parser.add_argument(
        '--max-words',
        type=int,
        default=1000,
        help='Maximum words to output (default: 1000)'
    )

    parser.add_argument(
        '--output-wordlist',
        type=Path,
        required=True,
        help='Output path for plain word list'
    )

    parser.add_argument(
        '--output-scored',
        type=Path,
        required=True,
        help='Output path for scored word list'
    )

    parser.add_argument(
        '--output-review',
        type=Path,
        required=True,
        help='Output path for review report'
    )

    args = parser.parse_args()

    # Determine paths
    dist = args.distribution
    meta_path = Path(f'data/build/{dist}/{dist}.meta.json')

    if not meta_path.exists():
        print(f"Metadata not found: {meta_path}")
        print(f"  Run 'make build-{dist}' first")
        return 1

    print(f"Filtering game words from {dist} distribution...")
    print(f"  Min score: {args.min_score}")
    print(f"  Max words: {args.max_words}")
    print()

    # Filter and score
    candidates = filter_game_words(meta_path, args.min_score, args.max_words)

    print(f"Found {len(candidates)} candidates")
    print()

    # Generate outputs
    wordlist_path = args.output_wordlist
    scored_path = args.output_scored
    report_path = args.output_review

    # Report for manual review
    generate_report(candidates, report_path)

    # Word list (plain)
    export_wordlist(candidates, wordlist_path, with_scores=False)

    # Word list with scores
    export_wordlist(candidates, scored_path, with_scores=True)

    print()
    print("=" * 60)
    print("Next steps:")
    print("1. Review:", report_path)
    print("2. Manually verify top candidates")
    print("3. Adjust filters/scores as needed")
    print("4. Use word list:", wordlist_path)
    print("=" * 60)


if __name__ == '__main__':
    exit(main())
