#!/usr/bin/env python3
"""
filters.py — Runtime filtering functions with safe defaults.

Provides filter functions for common use cases:
  1. Child-safe filtering (games for kids)
  2. Region-specific filtering (US vs UK spellings)
  3. Profanity filtering (offensive content)
  4. Concreteness filtering (concrete nouns for visualization games)
  5. License filtering (restrictiveness tolerance)

SAFE DEFAULTS PHILOSOPHY:
  - Missing metadata implies conservative assumptions
  - If we can't confirm something is safe → exclude it
  - If we can't confirm it's concrete → assume abstract
  - If we can't confirm region → assume universal

This enables reliable filtering for critical use cases like children's content.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Callable

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Register labels that mark profanity/offensive content
PROFANITY_REGISTERS = {'vulgar', 'offensive', 'derogatory'}

# Core sources that are curated for word games (pre-vetted)
GAME_CURATED_SOURCES = {'enable', 'eowl'}


def is_child_safe(entry: dict) -> bool:
    """
    Filter for children-appropriate words.

    SAFE DEFAULT: If we can't confirm it's safe, exclude it.

    Logic:
      1. Exclude explicit profanity (vulgar, offensive, derogatory)
      2. Exclude archaic/obsolete (kids won't know them)
      3. For Wiktionary-only words without labels: exclude (risky)
      4. Core sources (ENABLE/EOWL) are trusted even without labels

    Args:
        entry: Entry dict from schema

    Returns:
        True if safe for children, False otherwise
    """
    # Check explicit profanity markers
    register = entry.get('labels', {}).get('register', [])
    if any(label in register for label in PROFANITY_REGISTERS):
        return False

    # Check temporal labels (archaic/obsolete)
    temporal = entry.get('labels', {}).get('temporal', [])
    if any(label in temporal for label in ['archaic', 'obsolete']):
        return False

    # Check sources
    sources = set(entry.get('sources', []))

    # If from game-curated sources (ENABLE/EOWL), trust it
    if sources & GAME_CURATED_SOURCES:
        return True

    # If Wiktionary-only AND no register labels, be cautious
    # (These might be technical, regional slang, or otherwise inappropriate)
    if 'wikt' in sources and not register:
        # No labels = can't confirm safety → exclude
        return False

    # Has labels and passed checks above → include
    return True


def is_profanity(entry: dict) -> bool:
    """
    Check if entry is marked as profanity/offensive.

    Args:
        entry: Entry dict from schema

    Returns:
        True if marked as vulgar/offensive/derogatory
    """
    register = entry.get('labels', {}).get('register', [])
    return bool(set(register) & PROFANITY_REGISTERS)


def matches_region(entry: dict, preferred_regions: Optional[Set[str]] = None) -> bool:
    """
    Filter by regional usage.

    SAFE DEFAULT: Missing region labels = universal (include).

    Args:
        entry: Entry dict from schema
        preferred_regions: Set of BCP 47 region codes (e.g., {'en-US', 'en-GB'})
                          None means accept all regions

    Returns:
        True if entry matches preferred region(s) or has no region labels
    """
    if not preferred_regions:
        return True

    region_labels = entry.get('labels', {}).get('region', [])

    # No region labels = universal/unknown → include
    if not region_labels:
        return True

    # Has region labels - check if any match
    return bool(set(region_labels) & preferred_regions)


def is_concrete_noun(entry: dict, require_metadata: bool = True) -> bool:
    """
    Filter for concrete nouns (visualizable objects for games).

    SAFE DEFAULT: Missing concreteness = assume abstract/technical.

    Args:
        entry: Entry dict from schema
        require_metadata: If True, require explicit concreteness metadata.
                         If False, accept game-curated sources without metadata.

    Returns:
        True if confirmed concrete noun
    """
    # Must be a noun
    if 'noun' not in entry.get('pos', []):
        return False

    concreteness = entry.get('concreteness')

    # Has explicit metadata
    if concreteness:
        return concreteness == 'concrete'

    # Missing metadata - apply safe default
    if require_metadata:
        # Strict mode: must have metadata
        return False
    else:
        # Lenient mode: trust game-curated sources
        sources = set(entry.get('sources', []))
        return bool(sources & GAME_CURATED_SOURCES)


def is_modern(entry: dict) -> bool:
    """
    Filter for modern (non-archaic) words.

    Args:
        entry: Entry dict from schema

    Returns:
        True if not marked as archaic/obsolete/dated/historical
    """
    temporal = entry.get('labels', {}).get('temporal', [])
    outdated_labels = {'archaic', 'obsolete', 'dated', 'historical'}
    return not bool(set(temporal) & outdated_labels)


def matches_license(entry: dict, max_restrictiveness: str = 'CC-BY-SA-4.0') -> bool:
    """
    Filter by license restrictiveness.

    License hierarchy (least to most restrictive):
      CC0 < UKACD < WordNet < CC-BY-4.0 < CC-BY-SA-4.0

    Args:
        entry: Entry dict from schema
        max_restrictiveness: Maximum license allowed (more restrictive excluded)

    Returns:
        True if entry's licenses are at or below max restrictiveness
    """
    license_order = {
        'CC0': 0,
        'UKACD': 1,
        'WordNet': 2,
        'CC-BY-4.0': 3,
        'CC-BY-SA-4.0': 4
    }

    max_level = license_order.get(max_restrictiveness, 4)

    # Get entry's licenses
    license_sources = entry.get('license_sources', {})
    entry_licenses = license_sources.keys()

    # Check if any license exceeds max
    for lic in entry_licenses:
        lic_level = license_order.get(lic, 5)  # Unknown = most restrictive
        if lic_level > max_level:
            return False

    return True


def matches_pos(entry: dict, required_pos: Set[str]) -> bool:
    """
    Filter by part-of-speech tags.

    Args:
        entry: Entry dict from schema
        required_pos: Set of required POS tags (entry must have at least one)

    Returns:
        True if entry has any of the required POS tags
    """
    entry_pos = set(entry.get('pos', []))
    return bool(entry_pos & required_pos)


def matches_frequency(entry: dict, min_tier: Optional[str] = None,
                     max_tier: Optional[str] = None) -> bool:
    """
    Filter by frequency rank code.

    Rank codes: A (most frequent) < B < C < ... < Z (extremely rare)

    Args:
        entry: Entry dict from schema
        min_tier: Minimum frequency tier (e.g., 'M' excludes words rarer than ~rank 1000)
        max_tier: Maximum frequency tier (e.g., 'E' excludes words more frequent than ~rank 10)

    Returns:
        True if entry's frequency is within range
    """
    entry_tier = entry.get('frequency_tier', 'Z')

    # Simple alphabetical comparison (A < B < ... < Z)
    if min_tier and entry_tier > min_tier:
        return False

    if max_tier and entry_tier < max_tier:
        return False

    return True


def matches_length(entry: dict, min_length: Optional[int] = None,
                  max_length: Optional[int] = None) -> bool:
    """
    Filter by word length.

    Args:
        entry: Entry dict from schema
        min_length: Minimum character count (inclusive)
        max_length: Maximum character count (inclusive)

    Returns:
        True if word length is within range
    """
    word_len = len(entry['word'])

    if min_length is not None and word_len < min_length:
        return False

    if max_length is not None and word_len > max_length:
        return False

    return True


def apply_filters(input_path: Path, output_path: Path,
                 filters: List[Callable[[dict], bool]],
                 verbose: bool = False):
    """
    Apply a list of filter functions to entries.

    Args:
        input_path: Input JSONL file
        output_path: Output JSONL file
        filters: List of filter functions (all must return True to include)
        verbose: Log detailed stats
    """
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    logger.info(f"Applying filters to {input_path.name}")

    included = []
    excluded_count = 0

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if verbose and line_num % 100000 == 0:
                logger.info(f"  Processed {line_num:,} entries...")

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)

                # Apply all filters
                if all(f(entry) for f in filters):
                    included.append(entry)
                else:
                    excluded_count += 1

            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in included:
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"  Included: {len(included):,} entries")
    logger.info(f"  Excluded: {excluded_count:,} entries")
    logger.info(f"  -> {output_path}")


# Preset filter combinations for common use cases
def get_preset_filters(preset: str) -> List[Callable[[dict], bool]]:
    """
    Get a preset combination of filters.

    Presets:
      - 'child-safe': Safe for children's games
      - 'wordle': 5-letter common words
      - 'kids-nouns': Concrete nouns for children
      - 'scrabble': Single words, modern, no profanity
      - 'profanity': Only profane words (for blocklist)

    Args:
        preset: Preset name

    Returns:
        List of filter functions
    """
    presets = {
        'child-safe': [
            is_child_safe,
            is_modern,
            lambda e: not e.get('is_phrase', False)
        ],
        'wordle': [
            lambda e: matches_length(e, 5, 5),
            lambda e: not e.get('is_phrase', False),
            lambda e: matches_frequency(e, max_tier='top50k'),
            is_child_safe
        ],
        'kids-nouns': [
            lambda e: is_concrete_noun(e, require_metadata=False),
            is_child_safe,
            is_modern,
            lambda e: matches_frequency(e, max_tier='top25k')
        ],
        'scrabble': [
            lambda e: not e.get('is_phrase', False),
            is_modern,
            lambda e: not is_profanity(e)
        ],
        'profanity': [
            is_profanity
        ]
    }

    return presets.get(preset, [])


def main():
    """Example usage of filtering system."""
    import argparse

    parser = argparse.ArgumentParser(description='Filter entries with safe defaults')
    parser.add_argument('input', help='Input JSONL file')
    parser.add_argument('output', help='Output JSONL file')
    parser.add_argument('--preset', choices=['child-safe', 'wordle', 'kids-nouns', 'scrabble', 'profanity'],
                       help='Use a preset filter combination')
    parser.add_argument('--child-safe', action='store_true', help='Filter for child safety')
    parser.add_argument('--no-profanity', action='store_true', help='Exclude profanity')
    parser.add_argument('--concrete-nouns', action='store_true', help='Only concrete nouns')
    parser.add_argument('--modern', action='store_true', help='Exclude archaic/obsolete')
    parser.add_argument('--max-license', help='Maximum license restrictiveness')
    parser.add_argument('--min-length', type=int, help='Minimum word length')
    parser.add_argument('--max-length', type=int, help='Maximum word length')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Build filter list
    filters = []

    if args.preset:
        filters = get_preset_filters(args.preset)
        logger.info(f"Using preset: {args.preset}")
    else:
        if args.child_safe:
            filters.append(is_child_safe)
        if args.no_profanity:
            filters.append(lambda e: not is_profanity(e))
        if args.concrete_nouns:
            filters.append(lambda e: is_concrete_noun(e, require_metadata=True))
        if args.modern:
            filters.append(is_modern)
        if args.max_license:
            filters.append(lambda e: matches_license(e, args.max_license))
        if args.min_length or args.max_length:
            filters.append(lambda e: matches_length(e, args.min_length, args.max_length))

    if not filters:
        logger.error("No filters specified. Use --preset or individual filter flags.")
        return

    # Apply filters
    input_path = Path(args.input)
    output_path = Path(args.output)

    apply_filters(input_path, output_path, filters, verbose=args.verbose)

    logger.info("Filtering complete")


if __name__ == '__main__':
    main()
