#!/usr/bin/env python3
"""
filter_words.py - Flexible word filtering framework for different use cases

Supports multiple game/application types with different requirements:
- Wordle: 5 letters, common, no regional/derogatory
- 20 Questions: concrete nouns, common, age-appropriate
- Crossword: various lengths, can include proper nouns, obscure OK
- Scrabble: valid words, can be obscure, all lengths

Each use case has different filtering criteria. This framework makes it
easy to define and apply those criteria.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class UseCase(Enum):
    """Supported use cases with different filtering needs."""
    WORDLE = "wordle"
    TWENTY_QUESTIONS = "20q"
    CROSSWORD = "crossword"
    SCRABBLE = "scrabble"
    CUSTOM = "custom"


@dataclass
class FilterConfig:
    """Configuration for word filtering."""
    name: str
    description: str

    # Length constraints
    min_length: int = 1
    max_length: int = 100
    exact_length: int = None

    # POS constraints
    allowed_pos: Set[str] = field(default_factory=lambda: {'noun', 'verb', 'adjective', 'adverb'})
    require_primary_pos: bool = False

    # Concreteness (for nouns)
    require_concrete: bool = False
    allow_abstract: bool = True
    allow_mixed: bool = True

    # Frequency constraints
    min_frequency_tier: str = None  # 'top100k', 'top10k', etc.
    prefer_common: bool = True

    # Regional variants
    exclude_regional: bool = False  # Exclude words marked as regional
    allowed_regions: Set[str] = None  # If set, only allow these regions

    # Register constraints
    exclude_registers: Set[str] = field(default_factory=set)
    allowed_registers: Set[str] = None

    # Temporal constraints
    exclude_temporal: Set[str] = field(default_factory=lambda: {'obsolete', 'archaic'})

    # Domain constraints
    exclude_domains: Set[str] = field(default_factory=set)
    allowed_domains: Set[str] = None

    # Content filters
    exclude_offensive: bool = True
    exclude_vulgar: bool = True
    exclude_derogatory: bool = True
    exclude_slang: bool = False

    # Phrase handling
    allow_phrases: bool = False

    # Scoring weights
    frequency_weight: float = 1.0
    concreteness_weight: float = 0.5
    length_penalty_weight: float = 0.1


# Predefined configurations for common use cases
WORDLE_CONFIG = FilterConfig(
    name="wordle",
    description="5-letter words for Wordle-like games",
    exact_length=5,
    allowed_pos={'noun', 'verb', 'adjective', 'adverb'},
    allow_abstract=True,
    allow_mixed=True,
    require_concrete=False,
    min_frequency_tier='top100k',  # Want common words
    exclude_regional=True,  # No British-only or other regional variants
    exclude_offensive=True,
    exclude_vulgar=True,
    exclude_derogatory=True,
    exclude_slang=False,  # Wordle allows slang
    exclude_temporal={'obsolete', 'archaic', 'dated'},
    allow_phrases=False,
    prefer_common=True,
)

TWENTY_Q_CONFIG = FilterConfig(
    name="20questions",
    description="Concrete nouns for 20 Questions",
    min_length=3,
    max_length=15,
    allowed_pos={'noun'},
    require_primary_pos=True,
    require_concrete=True,
    min_frequency_tier='top100k',
    exclude_regional=False,  # Regional nouns are OK (like "lorry")
    exclude_offensive=True,
    exclude_vulgar=True,
    exclude_derogatory=True,
    exclude_slang=True,
    exclude_domains={'sexuality', 'drugs', 'pornography'},
    allow_phrases=False,
)

CROSSWORD_CONFIG = FilterConfig(
    name="crossword",
    description="Words for crossword puzzles",
    min_length=3,
    max_length=15,
    allowed_pos={'noun', 'verb', 'adjective', 'adverb'},
    allow_abstract=True,
    allow_mixed=True,
    require_concrete=False,
    min_frequency_tier=None,  # Crosswords can use obscure words
    exclude_regional=False,
    exclude_offensive=False,  # Crosswords might include if clued appropriately
    exclude_vulgar=True,
    exclude_derogatory=True,
    exclude_slang=False,
    exclude_temporal=set(),  # Archaic words are fair game
    allow_phrases=True,  # Multi-word answers common in crosswords
    prefer_common=False,
)

SCRABBLE_CONFIG = FilterConfig(
    name="scrabble",
    description="Valid words for Scrabble",
    min_length=2,
    max_length=15,
    allowed_pos=None,  # All POS allowed
    allow_abstract=True,
    allow_mixed=True,
    require_concrete=False,
    min_frequency_tier=None,  # Obscure words are strategic
    exclude_regional=False,
    exclude_offensive=False,  # Scrabble allows all dictionary words
    exclude_vulgar=False,
    exclude_derogatory=False,
    exclude_slang=False,
    exclude_temporal=set(),
    allow_phrases=False,  # No multi-word
    prefer_common=False,
)


def load_metadata(meta_path: Path) -> Dict[str, Dict]:
    """Load metadata JSON."""
    if not meta_path.exists():
        return {}

    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    return {entry['word']: entry for entry in metadata_list}


def passes_length_filter(word: str, config: FilterConfig) -> bool:
    """Check if word meets length requirements."""
    word_len = len(word)

    if config.exact_length is not None:
        return word_len == config.exact_length

    return config.min_length <= word_len <= config.max_length


def passes_pos_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets POS requirements."""
    if config.allowed_pos is None:
        return True  # All POS allowed

    pos_tags = entry.get('pos', [])

    if not pos_tags:
        return False  # Unknown POS

    # Check if any POS matches
    if not any(pos in config.allowed_pos for pos in pos_tags):
        return False

    # If require_primary_pos, check first tag
    if config.require_primary_pos and pos_tags[0] not in config.allowed_pos:
        return False

    return True


def passes_concreteness_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets concreteness requirements."""
    # Only applies to nouns
    if 'noun' not in entry.get('pos', []):
        return True

    concreteness = entry.get('concreteness', 'unknown')

    if config.require_concrete:
        return concreteness == 'concrete'

    # Check what's allowed
    if concreteness == 'concrete':
        return True
    if concreteness == 'abstract':
        return config.allow_abstract
    if concreteness == 'mixed':
        return config.allow_mixed

    return True  # Unknown is allowed


def passes_frequency_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets frequency requirements."""
    if config.min_frequency_tier is None:
        return True  # No minimum

    tier = entry.get('frequency_tier', 'rare')

    tier_order = ['top10', 'top100', 'top300', 'top500', 'top1k', 'top3k', 'top10k', 'top25k', 'top50k', 'rare']
    tier_index = {t: i for i, t in enumerate(tier_order)}

    min_index = tier_index.get(config.min_frequency_tier, 5)
    word_index = tier_index.get(tier, 5)

    return word_index <= min_index


def passes_regional_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets regional requirements."""
    labels = entry.get('labels', {})
    regions = set(labels.get('region', []))

    if not regions:
        return True  # No regional markers = OK

    # If exclude_regional, reject any regional markers
    if config.exclude_regional:
        return False

    # If allowed_regions specified, check membership
    if config.allowed_regions is not None:
        return bool(regions & config.allowed_regions)

    return True


def passes_register_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets register requirements."""
    labels = entry.get('labels', {})
    registers = set(labels.get('register', []))

    # Check exclusions
    if config.exclude_offensive and 'offensive' in registers:
        return False
    if config.exclude_vulgar and 'vulgar' in registers:
        return False
    if config.exclude_derogatory and 'derogatory' in registers:
        return False
    if config.exclude_slang and 'slang' in registers:
        return False

    # Check other exclusions
    if config.exclude_registers and (registers & config.exclude_registers):
        return False

    # Check allowed registers
    if config.allowed_registers is not None:
        if registers and not (registers & config.allowed_registers):
            return False

    return True


def passes_temporal_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets temporal requirements."""
    if not config.exclude_temporal:
        return True

    labels = entry.get('labels', {})
    temporal = set(labels.get('temporal', []))

    return not (temporal & config.exclude_temporal)


def passes_domain_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if word meets domain requirements."""
    labels = entry.get('labels', {})
    domains = set(labels.get('domain', []))

    # Check exclusions
    if config.exclude_domains and (domains & config.exclude_domains):
        return False

    # Check allowed domains
    if config.allowed_domains is not None:
        if domains and not (domains & config.allowed_domains):
            return False

    return True


def passes_phrase_filter(entry: Dict, config: FilterConfig) -> bool:
    """Check if phrases are allowed."""
    if config.allow_phrases:
        return True

    return not entry.get('is_phrase', False)


def passes_all_filters(word: str, entry: Dict, config: FilterConfig) -> bool:
    """Check if word passes all filters."""
    return (
        passes_length_filter(word, config) and
        passes_pos_filter(entry, config) and
        passes_concreteness_filter(entry, config) and
        passes_frequency_filter(entry, config) and
        passes_regional_filter(entry, config) and
        passes_register_filter(entry, config) and
        passes_temporal_filter(entry, config) and
        passes_domain_filter(entry, config) and
        passes_phrase_filter(entry, config)
    )


def calculate_score(word: str, entry: Dict, config: FilterConfig) -> float:
    """Calculate suitability score for word."""
    score = 0.0

    # Frequency score
    tier = entry.get('frequency_tier', 'rare')
    tier_scores = {
        'top10': 100,
        'top100': 95,
        'top300': 90,
        'top500': 85,
        'top1k': 80,
        'top3k': 70,
        'top10k': 60,
        'top25k': 40,
        'top50k': 20,
        'rare': 5,
    }
    score += tier_scores.get(tier, 0) * config.frequency_weight

    # Concreteness bonus (for nouns)
    if 'noun' in entry.get('pos', []) and entry.get('concreteness') == 'concrete':
        score += 20 * config.concreteness_weight

    # Length penalty (if word is very long)
    word_len = len(word)
    if word_len > 12:
        score -= (word_len - 12) * 2 * config.length_penalty_weight

    return score


def filter_words(
    metadata: Dict[str, Dict],
    config: FilterConfig,
    max_words: int = None
) -> List[tuple]:
    """
    Filter words based on configuration.

    Returns:
        List of (word, score, entry) tuples, sorted by score descending
    """
    candidates = []

    for word, entry in metadata.items():
        if passes_all_filters(word, entry, config):
            score = calculate_score(word, entry, config)
            candidates.append((word, score, entry))

    # Sort by score
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Limit if requested
    if max_words:
        candidates = candidates[:max_words]

    return candidates


def export_wordlist(
    candidates: List[tuple],
    output_path: Path,
    with_scores: bool = False
):
    """Export filtered word list."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for word, score, _ in candidates:
            if with_scores:
                f.write(f"{word}\t{score:.1f}\n")
            else:
                f.write(f"{word}\n")

    print(f"Word list written to {output_path} ({len(candidates)} words)")


def main():
    parser = argparse.ArgumentParser(
        description='Flexible word filtering for different use cases'
    )

    parser.add_argument(
        '--use-case',
        type=str,
        choices=['wordle', '20q', 'crossword', 'scrabble'],
        required=True,
        help='Use case / game type'
    )

    parser.add_argument(
        '--distribution',
        choices=['core', 'plus'],
        default='plus',
        help='Which distribution to filter (default: plus, has more metadata)'
    )

    parser.add_argument(
        '--max-words',
        type=int,
        default=None,
        help='Maximum words to output'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('data/filtered_words'),
        help='Output directory'
    )

    parser.add_argument(
        '--with-scores',
        action='store_true',
        help='Include scores in output'
    )

    args = parser.parse_args()

    # Get configuration
    config_map = {
        'wordle': WORDLE_CONFIG,
        '20q': TWENTY_Q_CONFIG,
        'crossword': CROSSWORD_CONFIG,
        'scrabble': SCRABBLE_CONFIG,
    }

    config = config_map[args.use_case]

    # Load metadata
    dist = args.distribution
    meta_path = Path(f'data/build/{dist}/{dist}.meta.json')

    if not meta_path.exists():
        print(f"Metadata not found: {meta_path}")
        print(f"  Run 'make build-{dist}' first")
        return 1

    print(f"Filtering words for: {config.description}")
    print(f"Distribution: {dist}")
    print()

    metadata = load_metadata(meta_path)
    print(f"Loaded {len(metadata):,} entries")

    # Apply filters
    candidates = filter_words(metadata, config, args.max_words)

    print(f"Found {len(candidates):,} matching words")
    print()

    # Export
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f'{args.use_case}_{dist}.txt'
    export_wordlist(candidates, output_path, args.with_scores)

    # Show sample
    print("\nSample words (top 20):")
    for word, score, _ in candidates[:20]:
        print(f"  {word:15} {score:.1f}")

    print()
    print("=" * 60)
    print(f"Output: {output_path}")
    print("=" * 60)


if __name__ == '__main__':
    exit(main())
