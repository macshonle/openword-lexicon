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
        required_pos: Set of required POS tags (e.g., {'noun', 'verb'})

    Returns:
        True if sense's POS is in required set
    """
    return sense.get('pos', '').lower() in required_pos


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
    """Check if sense is marked as proper noun."""
    return sense.get('is_proper_noun', False)


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
        # Get all nouns with frequency tier A-F (top ~3000 words)
        for lexeme, senses in filter_two_file(
            lexeme_path, senses_path,
            lexeme_predicate=lambda l: l.get('frequency_tier', 'Z') <= 'F',
            sense_predicate=lambda s: s.get('pos') == 'noun'
        ):
            print(lexeme['word'])

        # Get words where ALL senses are non-profane (strict)
        for lexeme, senses in filter_two_file(
            lexeme_path, senses_path,
            sense_predicate=lambda s: not sense_is_profane(s),
            require_all_senses=True
        ):
            print(lexeme['word'])
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
            sense_predicate=lambda s: s.get('pos') == 'noun'
        ))
    """
    for lexeme, _ in filter_two_file(
        lexeme_path, senses_path,
        lexeme_predicate, sense_predicate, require_all_senses
    ):
        yield lexeme['word']


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
        required_pos: Set of POS values (e.g., {'noun', 'verb'})

    Returns:
        Function that returns True for senses with matching POS
    """
    required_lower = {p.lower() for p in required_pos}
    def predicate(sense: dict) -> bool:
        return sense.get('pos', '').lower() in required_lower
    return predicate


def make_frequency_predicate(
    rarest_allowed: Optional[str] = None,
    most_common_allowed: Optional[str] = None
) -> Callable[[dict], bool]:
    """
    Create a lexeme predicate for frequency filtering.

    Frequency tiers: A (most common) → L (rare) → Y (very rare) → Z (unknown)

    Args:
        rarest_allowed: Include words up to this tier (e.g., 'F' includes A-F, ~top 3000)
        most_common_allowed: Exclude words more common than this (e.g., 'C' excludes A-B)

    Returns:
        Function that returns True for lexemes in frequency range

    Examples:
        # Top 3000 words only (tiers A-F)
        make_frequency_predicate(rarest_allowed='F')

        # Exclude very common words, keep C-Z
        make_frequency_predicate(most_common_allowed='C')

        # Middle frequency range (D-H)
        make_frequency_predicate(rarest_allowed='H', most_common_allowed='D')
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
        word = lexeme.get('word', '')

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
# Single-File Schema Filters
# =============================================================================
#
# These filters work with entries that have labels, pos, and sources fields
# directly on the entry object (rather than split into lexeme + senses files).
# Used by owlex.py for the word list builder.

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


def matches_frequency(entry: dict, rarest_allowed: Optional[str] = None,
                     most_common_allowed: Optional[str] = None) -> bool:
    """
    Filter by frequency tier.

    Frequency tiers: A (most common) → L (rare) → Y (very rare) → Z (unknown)

    Args:
        entry: Entry dict from schema
        rarest_allowed: Include words up to this tier (e.g., 'F' includes A-F, ~top 3000)
        most_common_allowed: Exclude words more common than this (e.g., 'C' excludes A-B)

    Returns:
        True if entry's frequency tier is within range

    Examples:
        # Top 3000 words only (tiers A-F)
        matches_frequency(entry, rarest_allowed='F')

        # Exclude very common words, keep C-Z
        matches_frequency(entry, most_common_allowed='C')
    """
    entry_tier = entry.get('frequency_tier', 'Z')

    # Alphabetical comparison: A < B < ... < L < Y < Z
    if rarest_allowed and entry_tier > rarest_allowed:
        return False

    if most_common_allowed and entry_tier < most_common_allowed:
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
    syllable_count = entry.get('syllables')

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


def is_standalone_word(entry: dict) -> bool:
    """
    Filter for standalone words (not contraction fragments).

    Excludes words that are contraction fragments:
      - Clitic suffixes: 'll, 's, 't, 'm, 're, 've, 'd
      - Clitic prefixes: 'twas, 'tis

    These appear in the lexicon from Wiktionary but are not valid standalone
    words for games or vocabulary lists.

    Args:
        entry: Entry dict from schema

    Returns:
        True if word is a standalone word (not a fragment)
    """
    word = entry.get('word', '')
    return not is_contraction_fragment(word)


def has_common_usage(entry: dict) -> bool:
    """
    Filter for words with common (non-proper-noun) usage.

    SAFE DEFAULT: Missing metadata = assume pure proper noun (exclude).

    This filter is ideal for:
      - Scrabble and word games (allow words like "bill", "candy", but exclude "Aaron")
      - Spelling practice games
      - General vocabulary lists

    Three word categories:
      1. Pure common words: "candy", "chase" (only lowercase Wiktionary page)
      2. Mixed usage: "bill" (money AND name), "sun" (celestial body AND deity)
      3. Pure proper nouns: "aaron", "january", "japan" (only capitalized page)

    This filter keeps categories 1 and 2, excludes category 3.

    Args:
        entry: Entry dict from schema

    Returns:
        True if word has common usage (categories 1 or 2)
        False if word is pure proper noun (category 3)
    """
    # Check if word has common usage flag
    # If flag is missing, assume it's a pure proper noun (safe default)
    return entry.get('has_common_usage', False)


def is_pure_common(entry: dict) -> bool:
    """
    Strict filter for pure common words only (no proper noun usage at all).

    SAFE DEFAULT: Missing metadata = assume has proper usage (exclude).

    This filter excludes words that have ANY proper noun usage, even if
    they also have common usage (e.g., "Bill", "Sun").

    Use this when you want:
      - Only dictionary words (no names, places, organizations)
      - Strict common word lists

    Args:
        entry: Entry dict from schema

    Returns:
        True if word has ONLY common usage (no proper noun usage)
        False if word has any proper noun usage
    """
    # Must have common usage
    if not entry.get('has_common_usage', False):
        return False

    # Must NOT have proper usage
    if entry.get('has_proper_usage', False):
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

    if verbose:
        with ProgressDisplay(f"Filtering {input_path.name}", update_interval=10000) as progress:
            with open(input_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
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

                        progress.update(Lines=line_num, Included=len(included), Excluded=excluded_count)

                    except json.JSONDecodeError as e:
                        logger.warning(f"Line {line_num}: JSON decode error: {e}")
                        continue
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
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
            is_standalone_word,  # Exclude contraction fragments
            lambda e: e.get('word_count', 1) == 1  # Single words only
        ],
        'wordle': [
            lambda e: matches_length(e, 5, 5),
            lambda e: e.get('word_count', 1) == 1,  # Single words only
            lambda e: matches_frequency(e, rarest_allowed='J'),  # Top ~50k words
            is_child_safe,
            is_standalone_word  # Exclude contraction fragments
        ],
        'kids-nouns': [
            lambda e: is_concrete_noun(e, require_metadata=False),
            is_child_safe,
            is_standalone_word,  # Exclude contraction fragments
            is_modern,
            lambda e: matches_frequency(e, rarest_allowed='I')  # Top ~30k words
        ],
        'scrabble': [
            lambda e: e.get('word_count', 1) == 1,  # Single words only
            is_modern,
            is_standalone_word,  # Exclude contraction fragments
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
    parser.add_argument('input', help='Input JSONL file (lexeme file for two-file mode)')
    parser.add_argument('output', help='Output JSONL file')

    # Two-file mode
    parser.add_argument('--senses', type=Path,
                       help='Senses JSONL file (enables two-file filtering mode)')
    parser.add_argument('--require-all-senses', action='store_true',
                       help='Require ALL senses to match (default: ANY sense)')

    # Presets
    parser.add_argument('--preset', choices=['child-safe', 'wordle', 'kids-nouns', 'scrabble', 'profanity'],
                       help='Use a preset filter combination')

    # Lexeme-level filters
    parser.add_argument('--rarest-allowed', type=str,
                       help='Include words up to this tier (e.g., F for top ~3000)')
    parser.add_argument('--most-common-allowed', type=str,
                       help='Exclude words more common than this tier (e.g., C excludes A-B)')
    parser.add_argument('--concreteness', choices=['concrete', 'mixed', 'abstract'],
                       help='Filter by concreteness category')
    parser.add_argument('--min-syllables', type=int, help='Minimum syllable count')
    parser.add_argument('--max-syllables', type=int, help='Maximum syllable count')
    parser.add_argument('--min-length', type=int, help='Minimum word length')
    parser.add_argument('--max-length', type=int, help='Maximum word length')
    parser.add_argument('--single-word', action='store_true',
                       help='Only single words (word_count=1)')

    # Sense-level filters
    parser.add_argument('--pos', type=str,
                       help='Required POS (comma-separated, e.g., noun,verb)')
    parser.add_argument('--no-profanity', action='store_true', help='Exclude profanity')
    parser.add_argument('--modern', action='store_true', help='Exclude archaic/obsolete')
    parser.add_argument('--no-proper-nouns', action='store_true',
                       help='Exclude proper nouns')
    parser.add_argument('--no-inflected', action='store_true',
                       help='Exclude inflected forms')
    parser.add_argument('--base-forms-only', action='store_true',
                       help='Only include base forms (exclude all inflections)')
    parser.add_argument('--no-abbreviations', action='store_true',
                       help='Exclude abbreviations')

    # Single-file schema filters (used with owlex input format)
    parser.add_argument('--child-safe', action='store_true', help='Filter for child safety')
    parser.add_argument('--concrete-nouns', action='store_true', help='Only concrete nouns')
    parser.add_argument('--max-license', help='Maximum license restrictiveness')

    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Two-file mode
    if args.senses:
        logger.info("Mode: Two-file filtering")

        # Build lexeme predicate
        lexeme_predicates = []

        if args.rarest_allowed or args.most_common_allowed:
            lexeme_predicates.append(make_frequency_predicate(args.rarest_allowed, args.most_common_allowed))

        if args.concreteness:
            lexeme_predicates.append(make_concreteness_predicate({args.concreteness}))

        if args.min_syllables is not None or args.max_syllables is not None:
            min_s, max_s = args.min_syllables, args.max_syllables
            lexeme_predicates.append(
                lambda l, min_s=min_s, max_s=max_s: matches_syllables(l, min_s, max_s)
            )

        if args.min_length is not None or args.max_length is not None:
            min_l, max_l = args.min_length, args.max_length
            lexeme_predicates.append(
                lambda l, min_l=min_l, max_l=max_l: matches_length(l, min_l, max_l)
            )

        if args.single_word:
            lexeme_predicates.append(lambda l: l.get('word_count', 1) == 1)

        # Build sense predicate
        sense_predicates = []

        if args.pos:
            pos_set = {p.strip().lower() for p in args.pos.split(',')}
            sense_predicates.append(make_pos_predicate(pos_set))

        if args.no_profanity:
            sense_predicates.append(lambda s: not sense_is_profane(s))

        if args.modern:
            sense_predicates.append(sense_is_modern)

        if args.no_proper_nouns:
            sense_predicates.append(lambda s: not sense_is_proper_noun(s))

        if args.no_inflected:
            sense_predicates.append(lambda s: not sense_is_inflected(s))

        if args.base_forms_only:
            sense_predicates.append(sense_is_base_form)

        if args.no_abbreviations:
            sense_predicates.append(lambda s: not sense_is_abbreviation(s))

        # Combine predicates
        lexeme_predicate = None
        if lexeme_predicates:
            lexeme_predicate = lambda l: all(p(l) for p in lexeme_predicates)

        sense_predicate = None
        if sense_predicates:
            sense_predicate = lambda s: all(p(s) for p in sense_predicates)

        apply_two_file_filters(
            input_path, args.senses, output_path,
            lexeme_predicate=lexeme_predicate,
            sense_predicate=sense_predicate,
            require_all_senses=args.require_all_senses,
            verbose=args.verbose
        )

    else:
        # Single-file mode (for owlex-style entries with labels/pos/sources)
        logger.info("Mode: Single-file filtering")

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

        apply_filters(input_path, output_path, filters, verbose=args.verbose)

    logger.info("Filtering complete")


if __name__ == '__main__':
    main()
