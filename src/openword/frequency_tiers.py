#!/usr/bin/env python3
"""
frequency_tiers.py — Assign frequency rank codes (A–L, Y, Z) to lexeme entries.

Usage:
  uv run python src/openword/frequency_tiers.py \\
      --input INPUT.jsonl \\
      --output OUTPUT.jsonl

Reads frequency data from data/raw/{lang}/{lang}_50k.txt

Rank Code System (12-level explicit boundaries):
  - A: ranks 1-20         Universal Anchor
  - B: ranks 21-100       Grammatical Skeleton
  - C: ranks 101-300      Semantic Core
  - D: ranks 301-500      Basic Literacy
  - E: ranks 501-1000     Elementary Vocabulary
  - F: ranks 1001-3000    Everyday Lexicon
  - G: ranks 3001-5000    Conversational Mastery
  - H: ranks 5001-10000   Educated Standard
  - I: ranks 10001-30000  Full Adult Repertoire
  - J: ranks 30001-50000  Sophisticated/Erudite
  - K: ranks 50001-75000  Technical/Domain-specific
  - L: ranks 75001-100000 Archaic/Hyperspecialized
  - Y: ranks 100001+      Known but very rare (beyond typical frequency data)
  - Z: unknown/unranked
"""

import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

import orjson

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_frequency_ranks(freq_file: Path) -> Dict[str, int]:
    """
    Load frequency list and return word->rank mapping.

    Input format: word<space>count (one per line)
    Returns: {normalized_word: rank} (1-indexed)
    """
    ranks = {}

    if not freq_file.exists():
        logger.warning(f"Frequency file not found: {freq_file}")
        return ranks

    logger.info(f"Loading frequency data from {freq_file}")

    with open(freq_file, 'r', encoding='utf-8') as f:
        for rank, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            # Parse: word frequency
            parts = line.split()
            if not parts:
                continue

            word = parts[0]

            # Normalize to match our entries
            normalized = unicodedata.normalize('NFKC', word.lower())

            # Skip contraction fragments (e.g., 'll, 's, 't, 'm, 're, 've)
            # These are not standalone words and should not affect frequency tiers
            if _is_contraction_fragment(normalized):
                continue

            ranks[normalized] = rank

    logger.info(f"  -> Loaded {len(ranks):,} frequency ranks")
    return ranks


def _is_contraction_fragment(word: str) -> bool:
    """
    Check if word is a contraction fragment (not a standalone word).

    Contraction fragments are partial word forms that can't stand alone:
      - Clitic suffixes: 'll, 's, 't, 'm, 're, 've, 'd
      - Clitic prefixes: 'twas, 'tis (less common)

    These appear in some frequency lists but are not valid standalone words.
    """
    return word.startswith("'") or word.endswith("'")


def _should_assign_frequency(word: str, lowercase_words: Set[str]) -> bool:
    """
    Determine if this entry should receive a frequency tier.

    Case normalization logic:
      - Lowercase words always get frequency tier
      - Non-lowercase words only get tier if no lowercase variant exists

    This ensures frequency "credit" goes to the canonical form:
      - "boat" gets tier E, "BOAT"/"BoAT" get tier Z (lowercase exists)
      - "NASA"/"Nasa" both get tier (no lowercase "nasa" exists)
      - "Monday" gets tier (no lowercase "monday" exists)

    Args:
        word: The word to check
        lowercase_words: Set of all lowercase words in the lexicon

    Returns:
        True if this entry should receive a frequency tier
    """
    if word.islower():
        return True
    return word.lower() not in lowercase_words


# Tier thresholds: (min_rank, code, description)
# Each tier starts at min_rank and extends to the next tier's min_rank - 1
TIER_DEFINITIONS = [
    (1, 'A', 'Universal Anchor'),
    (21, 'B', 'Grammatical Skeleton'),
    (101, 'C', 'Semantic Core'),
    (301, 'D', 'Basic Literacy'),
    (501, 'E', 'Elementary Vocabulary'),
    (1001, 'F', 'Everyday Lexicon'),
    (3001, 'G', 'Conversational Mastery'),
    (5001, 'H', 'Educated Standard'),
    (10001, 'I', 'Full Adult Repertoire'),
    (30001, 'J', 'Sophisticated/Erudite'),
    (50001, 'K', 'Technical/Domain-specific'),
    (75001, 'L', 'Archaic/Hyperspecialized'),
    (100001, 'Y', 'Known but very rare'),
]

# Reversed for efficient lookup (check highest thresholds first)
_TIER_THRESHOLDS = [(t[0], t[1]) for t in reversed(TIER_DEFINITIONS)]

# Valid tier codes (Y is now in TIER_DEFINITIONS, Z is for unknown/unranked)
TIER_CODES = [t[1] for t in TIER_DEFINITIONS] + ['Z']


def rank_to_code(rank: Optional[int]) -> str:
    """
    Convert frequency rank to single-letter code (A–L, Y, Z).

    12-level explicit boundary system:
    - A: ranks 1-20         Universal Anchor
    - B: ranks 21-100       Grammatical Skeleton
    - C: ranks 101-300      Semantic Core
    - D: ranks 301-500      Basic Literacy
    - E: ranks 501-1000     Elementary Vocabulary
    - F: ranks 1001-3000    Everyday Lexicon
    - G: ranks 3001-5000    Conversational Mastery
    - H: ranks 5001-10000   Educated Standard
    - I: ranks 10001-30000  Full Adult Repertoire
    - J: ranks 30001-50000  Sophisticated/Erudite
    - K: ranks 50001-75000  Technical/Domain-specific
    - L: ranks 75001-100000 Archaic/Hyperspecialized
    - Y: ranks 100001+      Known but very rare
    - Z: unknown/unranked

    Args:
        rank: Integer rank (1-indexed), or None for unranked words

    Returns:
        Single letter code A–L, Y, or Z
    """
    if rank is None or rank < 1:
        return 'Z'  # Unknown/unranked

    # Find the appropriate tier by checking thresholds from highest to lowest
    for threshold, code in _TIER_THRESHOLDS:
        if rank >= threshold:
            return code

    return 'A'  # Fallback (should not reach here for valid ranks)


def code_to_rank(code: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Convert letter code to rank range (min_rank, max_rank).

    Args:
        code: Single letter A–L, Y, or Z

    Returns:
        Tuple of (min_rank, max_rank) where:
        - For A-L, Y: inclusive range of ranks for that tier
        - For Z: (None, None) - unknown/unranked

    Raises:
        ValueError: If code is not a valid tier code
    """
    c = code.upper()

    if c == 'Z':
        return (None, None)

    # Find the tier in definitions (includes A-L and Y)
    tier_idx = None
    for i, (_, tier_code, _) in enumerate(TIER_DEFINITIONS):
        if tier_code == c:
            tier_idx = i
            break

    if tier_idx is None:
        raise ValueError(f"Code must be A-L, Y, or Z, got: {code}")

    min_rank = TIER_DEFINITIONS[tier_idx][0]

    # Max rank is one less than the next tier's min, or None for the last tier (Y)
    if tier_idx < len(TIER_DEFINITIONS) - 1:
        max_rank = TIER_DEFINITIONS[tier_idx + 1][0] - 1
    else:
        # Last tier (Y) - no upper bound
        max_rank = None

    return (min_rank, max_rank)


def assign_tier(entry: dict, ranks: Dict[str, int], lowercase_words: Set[str]) -> dict:
    """Assign frequency rank code to an entry with case normalization.

    Case normalization logic:
      - Lowercase words always get frequency tier based on lookup
      - Non-lowercase words get tier Z if a lowercase variant exists
      - Non-lowercase words get frequency tier if no lowercase variant exists

    This ensures frequency "credit" goes to the canonical (lowercase) form
    when it exists, while still assigning tiers to proper nouns and acronyms
    that only exist in capitalized forms.

    Args:
        entry: Lexeme entry dict with 'word' key
        ranks: Word to frequency rank mapping (1-indexed)
        lowercase_words: Set of all lowercase words in the lexicon

    Returns:
        Entry dict with 'frequency_tier' assigned
    """
    word = entry['word']

    # Check if this entry should receive a frequency tier
    if not _should_assign_frequency(word, lowercase_words):
        entry['frequency_tier'] = 'Z'
        return entry

    # Normalize for lookup (frequency tables are lowercase)
    normalized = unicodedata.normalize('NFKC', word.lower())
    rank = ranks.get(normalized)
    code = rank_to_code(rank)

    entry['frequency_tier'] = code
    return entry


def process_file(input_path: Path, output_path: Path, ranks: Dict[str, int]):
    """Process a JSONL file and assign rank codes with case normalization.

    Uses a two-pass approach:
      1. Load all entries and build set of lowercase words
      2. Assign tiers with case-aware logic (only canonical forms get tiers)

    This ensures frequency "credit" goes to lowercase forms when they exist,
    while proper nouns and acronyms without lowercase variants still get tiers.
    """
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return

    logger.info(f"Processing {input_path.name}")

    # Pass 1: Load all entries and build lowercase word set
    entries = []
    lowercase_words: Set[str] = set()

    with ProgressDisplay(f"Loading {input_path.name}", update_interval=10000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    word = entry['word']
                    if word.islower():
                        lowercase_words.add(word)
                    progress.update(Lines=line_num, Entries=len(entries))
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue

    logger.info(f"  Found {len(lowercase_words):,} lowercase words in lexicon")

    # Pass 2: Assign tiers with case-aware logic
    tier_counts = {code: 0 for code in TIER_CODES}

    with ProgressDisplay("Assigning frequency tiers", update_interval=10000) as progress:
        for i, entry in enumerate(entries, 1):
            tiered = assign_tier(entry, ranks, lowercase_words)
            tier_counts[tiered['frequency_tier']] += 1
            progress.update(Entries=i)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in entries:
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"  Assigned rank codes to {len(entries):,} entries")
    # Log counts for codes that have entries
    for code in sorted(tier_counts.keys()):
        count = tier_counts[code]
        if count > 0:
            # Get rank range for this code
            min_rank, max_rank = code_to_rank(code)
            if min_rank is None:
                logger.info(f"    {code}: {count:6,}  (unknown/unranked)")
            elif max_rank is None:
                logger.info(f"    {code}: {count:6,}  (ranks {min_rank:,}+)")
            else:
                logger.info(f"    {code}: {count:6,}  (ranks {min_rank:,}-{max_rank:,})")
    logger.info(f"  -> {output_path}")


def main():
    """Main frequency tier assignment pipeline."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Assign frequency tiers to entries')
    parser.add_argument('--input', type=Path, required=True,
                        help='Input JSONL file (lexeme entries)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output JSONL file')
    parser.add_argument('--language', default='en',
                        help='Language code for frequency file (default: en)')
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / args.language

    freq_file = raw_dir / f"{args.language}_50k.txt"

    logger.info("Frequency tier assignment")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Output: {args.output}")

    # Load frequency ranks
    ranks = load_frequency_ranks(freq_file)

    if not ranks:
        logger.warning("No frequency data loaded. All words will be marked 'rare'.")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    process_file(args.input, args.output, ranks)

    logger.info("")
    logger.info("Frequency tier assignment complete")


if __name__ == '__main__':
    main()
