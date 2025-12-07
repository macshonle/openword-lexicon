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

TWO-FILE FILTERING (NEW):
  The new two-file pipeline splits data into:
    - lexeme file: Word-level properties (frequency, concreteness, syllables, etc.)
    - senses file: Sense-level properties (POS, tags, flags)

  Use filter_two_file() to filter based on both lexeme and sense predicates:
    - lexeme_predicate: Filters on word-level properties
    - sense_predicate: Filters on sense-level properties
    - require_all_senses: True = all senses must match, False = any sense matches
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Callable, Iterator, Tuple

import orjson

from openword.progress_display import ProgressDisplay


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

# Temporal labels marking outdated words
OUTDATED_TEMPORAL = {'archaic', 'obsolete', 'dated', 'historical'}


# =============================================================================
# Two-File Pipeline Support
# =============================================================================

class SensesIndex:
    """
    Efficient random-access index into the senses file.

    Since senses are stored as JSONL with variable-length lines, we build
    a line offset index for O(1) access to any sense by line number.

    Usage:
        index = SensesIndex.from_file(senses_path)
        senses = index.get_senses(offset=10, length=3)  # Get 3 senses starting at line 10
    """

    def __init__(self, senses_path: Path, line_offsets: List[int]):
        self.senses_path = senses_path
        self.line_offsets = line_offsets  # Byte offset of each line start
        self._file = None

    @classmethod
    def from_file(cls, senses_path: Path) -> 'SensesIndex':
        """Build line offset index from senses file."""
        offsets = []
        with open(senses_path, 'rb') as f:
            offset = 0
            for line in f:
                offsets.append(offset)
                offset += len(line)
        return cls(senses_path, offsets)

    def get_senses(self, offset: int, length: int) -> List[dict]:
        """
        Get senses by line offset and count.

        Args:
            offset: Starting line number (0-indexed)
            length: Number of senses to read

        Returns:
            List of sense dictionaries
        """
        if length <= 0 or offset < 0 or offset >= len(self.line_offsets):
            return []

        senses = []
        with open(self.senses_path, 'r', encoding='utf-8') as f:
            # Seek to first sense
            f.seek(self.line_offsets[offset])

            # Read requested senses
            for i in range(length):
                if offset + i >= len(self.line_offsets):
                    break
                line = f.readline()
                if line:
                    senses.append(json.loads(line))

        return senses


def load_senses_simple(senses_path: Path, offset: int, length: int) -> List[dict]:
    """
    Load senses by line number (simple but slower for many lookups).

    For bulk filtering, use SensesIndex instead.

    Args:
        senses_path: Path to senses JSONL file
        offset: Starting line number (0-indexed)
        length: Number of senses to read

    Returns:
        List of sense dictionaries
    """
    senses = []
    with open(senses_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if i >= offset + length:
                break
            line = line.strip()
            if line:
                senses.append(json.loads(line))
    return senses


# =============================================================================
# Sense-Level Filter Predicates (for two-file pipeline)
# =============================================================================

def sense_is_profane(sense: dict) -> bool:
    """
    Check if a sense is marked as profane/offensive.

    Args:
        sense: Sense dict from senses file (flat tag arrays)

    Returns:
        True if sense has vulgar/offensive/derogatory register tags
    """
    register_tags = set(sense.get('register_tags', []))
    return bool(register_tags & PROFANITY_REGISTERS)


def sense_is_modern(sense: dict) -> bool:
    """
    Check if a sense is modern (not archaic/obsolete).

    Args:
        sense: Sense dict from senses file

    Returns:
        True if sense is not marked as archaic/obsolete/dated/historical
    """
    temporal_tags = set(sense.get('temporal_tags', []))
    return not bool(temporal_tags & OUTDATED_TEMPORAL)


def sense_matches_pos(sense: dict, required_pos: Set[str]) -> bool:
    """
    Check if sense matches required POS.

    Args:
        sense: Sense dict from senses file
        required_pos: Set of required POS tags (e.g., {'NOU', 'VRB'})

    Returns:
        True if sense's POS is in required set
    """
    return sense.get('pos', '') in required_pos


def sense_matches_region(sense: dict, preferred_regions: Optional[Set[str]] = None) -> bool:
    """
    Check if sense matches preferred regions.

    SAFE DEFAULT: Missing region tags = universal (include).

    Args:
        sense: Sense dict from senses file
        preferred_regions: Set of region codes (e.g., {'US', 'UK'})

    Returns:
        True if sense matches region or has no region tags
    """
    if not preferred_regions:
        return True

    region_tags = set(sense.get('region_tags', []))

    # No region tags = universal → include
    if not region_tags:
        return True

    return bool(region_tags & preferred_regions)


def sense_is_inflected(sense: dict) -> bool:
    """Check if sense is marked as inflected form."""
    return sense.get('is_inflected', False)


def sense_is_base_form(sense: dict) -> bool:
    """
    Check if sense is a base form (not an inflection).

    Base forms are:
    - Not marked as inflected
    - Or don't have a lemma pointing to a different word

    Args:
        sense: Sense dict from senses file

    Returns:
        True if this sense represents a base/root form
    """
    # If explicitly marked as inflected, it's not a base form
    if sense.get('is_inflected', False):
        return False

    # If it has a lemma pointing to another word, it's an inflection
    lemma = sense.get('lemma')
    if lemma:
        # Has lemma = inflected form (lemma points to base word)
        return False

    return True


def sense_has_lemma(sense: dict, target_lemma: str) -> bool:
    """
    Check if sense's lemma matches target.

    Args:
        sense: Sense dict from senses file
        target_lemma: The lemma value to match

    Returns:
        True if this sense's lemma matches the target
    """
    return sense.get('lemma') == target_lemma


def sense_get_lemma(sense: dict) -> str | None:
    """
    Get the lemma (base form) for a sense.

    Args:
        sense: Sense dict from senses file

    Returns:
        The lemma string if inflected, None if base form
    """
    return sense.get('lemma')


def sense_is_abbreviation(sense: dict) -> bool:
    """Check if sense is marked as abbreviation."""
    return sense.get('is_abbreviation', False)


def sense_is_proper_noun(sense: dict) -> bool:
    """Check if sense is a proper noun (names, places, etc.)."""
    return sense.get('pos') == 'proper'


# =============================================================================
# Word-Form Predicates
# =============================================================================

def is_contraction_fragment(word: str) -> bool:
    """
    Check if word is a contraction fragment (not a standalone word).

    Contraction fragments are partial word forms that can't stand alone:
      - Clitic suffixes: 'll, 's, 't, 'm, 're, 've, 'd
      - Clitic prefixes: 'twas, 'tis (less common)

    These appear in the lexicon from Wiktionary but are not valid standalone
    words for games or vocabulary lists.

    Args:
        word: The word to check

    Returns:
        True if the word is a contraction fragment (starts or ends with apostrophe)
    """
    return word.startswith("'") or word.endswith("'")


def is_valid_contraction(word: str) -> bool:
    """
    Check if word is a valid full contraction (not a fragment).

    Valid contractions have apostrophes in the middle:
      - "he'll", "don't", "won't", "it's", "I'm"

    Invalid fragments have apostrophes at the start or end:
      - "'ll", "'s", "'t", "'" (not standalone words)

    Args:
        word: The word to check

    Returns:
        True if the word contains an apostrophe but is not a fragment
    """
    if "'" not in word:
        return False  # Not a contraction at all
    return not is_contraction_fragment(word)


# =============================================================================
# Two-File Filtering Functions
# =============================================================================

def filter_two_file(
    lexeme_path: Path,
    senses_path: Path,
    lexeme_predicate: Optional[Callable[[dict], bool]] = None,
    sense_predicate: Optional[Callable[[dict], bool]] = None,
    require_all_senses: bool = False
) -> Iterator[Tuple[dict, List[dict]]]:
    """
    Filter lexemes based on both word-level and sense-level predicates.

    This is the main entry point for filtering in the two-file pipeline.

    Args:
        lexeme_path: Path to lexeme JSONL file
        senses_path: Path to senses JSONL file
        lexeme_predicate: Filter function for lexeme (word-level) properties.
                         If None, all lexemes pass this check.
        sense_predicate: Filter function for sense properties.
                        If None, all senses pass this check.
        require_all_senses: If True, ALL senses must match sense_predicate (AND logic).
                           If False, ANY sense matching is sufficient (OR logic).
                           Default is False (more permissive).

    Yields:
        Tuples of (lexeme, matching_senses) for each lexeme that passes filters

    Examples:
        # Get all nouns with frequency tier A-I (top ~3000 words)
        for lexeme, senses in filter_two_file(
            lexeme_path, senses_path,
            lexeme_predicate=lambda l: l.get('frequency_tier', 'Z') <= 'I',
            sense_predicate=lambda s: s.get('pos') == 'NOU'
        ):
            print(lexeme['id'])

        # Get words where ALL senses are non-profane (strict)
        for lexeme, senses in filter_two_file(
            lexeme_path, senses_path,
            sense_predicate=lambda s: not sense_is_profane(s),
            require_all_senses=True
        ):
            print(lexeme['id'])
    """
    # Build senses index for efficient random access
    senses_index = SensesIndex.from_file(senses_path)

    with open(lexeme_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            lexeme = json.loads(line)

            # Check lexeme predicate
            if lexeme_predicate and not lexeme_predicate(lexeme):
                continue

            # Load senses for this lexeme
            offset = lexeme.get('sense_offset', 0)
            length = lexeme.get('sense_length', 0)
            senses = senses_index.get_senses(offset, length)

            # If no senses, handle based on require_all_senses
            if not senses:
                if require_all_senses or sense_predicate is None:
                    yield (lexeme, [])
                continue

            # Check sense predicate
            if sense_predicate:
                if require_all_senses:
                    # ALL senses must match
                    matching_senses = [s for s in senses if sense_predicate(s)]
                    if len(matching_senses) == len(senses):
                        yield (lexeme, matching_senses)
                else:
                    # ANY sense matching is sufficient
                    matching_senses = [s for s in senses if sense_predicate(s)]
                    if matching_senses:
                        yield (lexeme, matching_senses)
            else:
                # No sense predicate - include all senses
                yield (lexeme, senses)


def filter_two_file_words_only(
    lexeme_path: Path,
    senses_path: Path,
    lexeme_predicate: Optional[Callable[[dict], bool]] = None,
    sense_predicate: Optional[Callable[[dict], bool]] = None,
    require_all_senses: bool = False
) -> Iterator[str]:
    """
    Convenience function that yields only word strings (not full lexeme dicts).

    Same filtering logic as filter_two_file, but yields just the word strings.
    Useful for generating wordlists.

    Args:
        Same as filter_two_file

    Yields:
        Word strings that pass the filters

    Example:
        # Generate wordlist of concrete nouns
        words = list(filter_two_file_words_only(
            lexeme_path, senses_path,
            lexeme_predicate=lambda l: l.get('concreteness') == 'concrete',
            sense_predicate=lambda s: s.get('pos') == 'NOU'
        ))
    """
    for lexeme, _ in filter_two_file(
        lexeme_path, senses_path,
        lexeme_predicate, sense_predicate, require_all_senses
    ):
        yield lexeme['id']


def apply_two_file_filters(
    lexeme_path: Path,
    senses_path: Path,
    output_path: Path,
    lexeme_predicate: Optional[Callable[[dict], bool]] = None,
    sense_predicate: Optional[Callable[[dict], bool]] = None,
    require_all_senses: bool = False,
    verbose: bool = False
) -> Tuple[int, int]:
    """
    Apply filters and write matching lexemes to output file.

    Args:
        lexeme_path: Input lexeme JSONL file
        senses_path: Input senses JSONL file
        output_path: Output JSONL file (lexemes only)
        lexeme_predicate: Filter for lexeme properties
        sense_predicate: Filter for sense properties
        require_all_senses: True = AND logic, False = OR logic
        verbose: Show progress

    Returns:
        Tuple of (included_count, excluded_count)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    included = 0
    excluded = 0

    with open(output_path, 'wb') as f_out:
        if verbose:
            with ProgressDisplay("Filtering", update_interval=10000) as progress:
                for lexeme, senses in filter_two_file(
                    lexeme_path, senses_path,
                    lexeme_predicate, sense_predicate, require_all_senses
                ):
                    f_out.write(orjson.dumps(lexeme, option=orjson.OPT_SORT_KEYS) + b'\n')
                    included += 1
                    progress.update(Included=included)
        else:
            for lexeme, senses in filter_two_file(
                lexeme_path, senses_path,
                lexeme_predicate, sense_predicate, require_all_senses
            ):
                f_out.write(orjson.dumps(lexeme, option=orjson.OPT_SORT_KEYS) + b'\n')
                included += 1

    # Count total to get excluded
    total = 0
    with open(lexeme_path, 'r') as f:
        for line in f:
            if line.strip():
                total += 1
    excluded = total - included

    logger.info(f"  Included: {included:,} lexemes")
    logger.info(f"  Excluded: {excluded:,} lexemes")
    logger.info(f"  -> {output_path}")

    return included, excluded


# =============================================================================
# Combined Predicates for Two-File Pipeline
# =============================================================================

def make_child_safe_sense_predicate() -> Callable[[dict], bool]:
    """
    Create a sense predicate for child-safe filtering.

    Returns a function that returns True for senses that are:
    - Not profane (no vulgar/offensive/derogatory tags)
    - Modern (no archaic/obsolete tags)
    """
    def predicate(sense: dict) -> bool:
        return not sense_is_profane(sense) and sense_is_modern(sense)
    return predicate


def make_pos_predicate(required_pos: Set[str]) -> Callable[[dict], bool]:
    """
    Create a sense predicate for POS filtering.

    Args:
        required_pos: Set of POS values (e.g., {'NOU', 'VRB'})

    Returns:
        Function that returns True for senses with matching POS
    """
    def predicate(sense: dict) -> bool:
        return sense.get('pos', '') in required_pos
    return predicate


def make_frequency_predicate(
    rarest_allowed: Optional[str] = None,
    most_common_allowed: Optional[str] = None
) -> Callable[[dict], bool]:
    """
    Create a lexeme predicate for frequency filtering.

    Frequency tiers (26 levels):
      A-F: top 500 (A=20, B=100, C=200, D=300, E=400, F=500)
      G-K: top 5,000 (G=1k, H=2k, I=3k, J=4k, K=5k)
      L-P: top 50,000 (L=10k, M=20k, N=30k, O=40k, P=50k)
      Q-X: top 400,000 (extended range)
      Y: 400,001+ (known but very rare)
      Z: unknown/unranked

    Args:
        rarest_allowed: Include words up to this tier (e.g., 'I' includes A-I, ~top 3000)
        most_common_allowed: Exclude words more common than this (e.g., 'C' excludes A-B)

    Returns:
        Function that returns True for lexemes in frequency range

    Examples:
        # Top 3000 words only (tiers A-I)
        make_frequency_predicate(rarest_allowed='I')

        # Exclude very common words, keep C-Z
        make_frequency_predicate(most_common_allowed='C')

        # Middle frequency range (D-L)
        make_frequency_predicate(rarest_allowed='L', most_common_allowed='D')
    """
    def predicate(lexeme: dict) -> bool:
        tier = lexeme.get('frequency_tier', 'Z')
        if rarest_allowed and tier > rarest_allowed:
            return False
        if most_common_allowed and tier < most_common_allowed:
            return False
        return True
    return predicate


def make_word_form_predicate(
    exclude_fragments: bool = True,
    pure_alpha: bool = False
) -> Callable[[dict], bool]:
    """
    Create a lexeme predicate for word form filtering.

    Args:
        exclude_fragments: If True, exclude contraction fragments ('ll, 's, 't)
        pure_alpha: If True, only allow pure alphabetic words (a-z, A-Z)

    Returns:
        Function that returns True for lexemes with valid word forms
    """
    def predicate(lexeme: dict) -> bool:
        word = lexeme.get('id', '')

        if exclude_fragments and is_contraction_fragment(word):
            return False

        if pure_alpha and not word.isalpha():
            return False

        return True
    return predicate


def make_concreteness_predicate(
    categories: Optional[Set[str]] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None
) -> Callable[[dict], bool]:
    """
    Create a lexeme predicate for concreteness filtering.

    Args:
        categories: Set of allowed categories (e.g., {'concrete', 'mixed'})
        min_rating: Minimum concreteness rating (1.0-5.0 scale)
        max_rating: Maximum concreteness rating

    Returns:
        Function that returns True for lexemes matching concreteness criteria
    """
    def predicate(lexeme: dict) -> bool:
        if categories:
            cat = lexeme.get('concreteness')
            if cat not in categories:
                return False

        rating = lexeme.get('concreteness_rating')
        if rating is not None:
            if min_rating is not None and rating < min_rating:
                return False
            if max_rating is not None and rating > max_rating:
                return False

        return True
    return predicate


# =============================================================================
# Syllable Filter (used by owlex.py)
# =============================================================================

def matches_syllables(entry: dict, min_syllables: Optional[int] = None,
                      max_syllables: Optional[int] = None,
                      exact_syllables: Optional[int] = None,
                      require_syllables: bool = False) -> bool:
    """
    Filter by syllable count.

    SAFE DEFAULT: Missing syllable data = exclude if any filter specified.

    Syllable data comes from Wiktionary (hyphenation > rhymes > categories).
    Coverage is ~2-3% of entries (~30k words), but these are high-quality,
    human-curated counts.

    Use cases:
      - Children's word games: Find 2-syllable concrete nouns
      - Poetry tools: Filter by syllable count for meter
      - Pronunciation practice: Group words by syllable complexity
      - Reading level: Shorter syllable counts = easier words

    Args:
        entry: Entry dict from schema
        min_syllables: Minimum syllable count (inclusive)
        max_syllables: Maximum syllable count (inclusive)
        exact_syllables: Exact syllable count required
        require_syllables: If True, exclude words without syllable data

    Returns:
        True if syllable count is within range (or no syllable filter active)

    Examples:
        # Two-syllable words only (with data)
        matches_syllables(entry, exact_syllables=2, require_syllables=True)

        # 1-3 syllables for simple words
        matches_syllables(entry, min_syllables=1, max_syllables=3)

        # At least 4 syllables for complex words
        matches_syllables(entry, min_syllables=4)

        # Words with syllable data (any count)
        matches_syllables(entry, require_syllables=True)
    """
    syllable_count = entry.get('nsyll')

    # If requiring syllable data and it's missing, exclude
    if require_syllables and syllable_count is None:
        return False

    # If any filter specified and no data, exclude (safe default)
    if syllable_count is None and (min_syllables is not None or
                                   max_syllables is not None or
                                   exact_syllables is not None):
        return False

    # If no data and no filters specified, include (neutral)
    if syllable_count is None:
        return True

    # Apply exact match filter (takes precedence)
    if exact_syllables is not None:
        return syllable_count == exact_syllables

    # Apply range filters
    if min_syllables is not None and syllable_count < min_syllables:
        return False

    if max_syllables is not None and syllable_count > max_syllables:
        return False

    return True


# NOTE: Single-file filters, presets, and CLI removed - use owlex.py with YAML/JSON specs instead.
# The two-file filtering functions above are kept for programmatic use.
