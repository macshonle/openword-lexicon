#!/usr/bin/env python3
"""
frequency_tiers.py — Assign frequency rank codes (A–Z) to lexeme entries.

Usage:
  uv run python src/openword/frequency_tiers.py \\
      --input INPUT.jsonl \\
      --output OUTPUT.jsonl

Reads frequency data from data/raw/{lang}/{lang}_50k.txt

Rank Code System (A–Z, logarithmic scale with base B = 10^(1/4)):
  Each letter represents a geometric band on the frequency rank scale.
  - A: rank 1 (most frequent word)
  - B: rank 2
  - C: ranks 3-4
  - D: ranks 5-7 (ultra-top function words)
  - E: ranks 8-13 (core function words)
  - F: ranks 14-23 (very frequent function/structure words)
  - G: ranks 24-42 (high-frequency function + extremely common content)
  - H: ranks 43-74 (very common grammatical items, basic content)
  - I: ranks 75-133 (high-frequency core vocabulary)
  - J: ranks 134-237 (core high-frequency; early "sight" vocabulary)
  - K: ranks 238-421 (basic everyday content vocabulary)
  - L: ranks 422-749 (common conversational words; early reader level)
  - M: ranks 750-1333 (simple vocabulary; frequent in everyday texts)
  - N: ranks 1334-2371 (high-frequency everyday vocabulary)
  - O: ranks 2372-4216 (conversational fluency band)
  - P: ranks 4217-7498 (broad conversational fluency; frequent in general prose)
  - Q: ranks 7499-13335 (general educated vocabulary)
  - R: ranks 13336-23713 (educated usage; lower-mid frequency)
  - S: ranks 23714-42169 (standard educated vocabulary; mid-frequency)
  - T: ranks 42170-74989 (extended vocabulary; literary and academic)
  - U: ranks 74990-133352 (extended/technical vocabulary)
  - V: ranks 133353-237137 (specialized but relatively well-attested)
  - W: ranks 237138-421696 (rare/specialized; tail of large general lexicons)
  - X: ranks 421697-749894 (very rare; technical terms, obscure lexemes)
  - Y: ranks 749895-1333521 (very rare; domain-specific vocabulary, proper names)
  - Z: ranks 1333522+ (extremely rare; highly specialized jargon, neologisms)
"""

import json
import logging
import math
import unicodedata
from pathlib import Path
from typing import Dict, Optional, Tuple

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
            ranks[normalized] = rank

    logger.info(f"  -> Loaded {len(ranks):,} frequency ranks")
    return ranks


def rank_to_code(rank: Optional[int]) -> str:
    """
    Convert frequency rank to single-letter code (A–Z).

    Uses logarithmic scale with base B = 10^(1/4):
    - A = rank 1 (most frequent)
    - B = rank 2
    - ...
    - M ≈ rank 1000
    - Q ≈ rank 10000
    - U ≈ rank 100000
    - Z = ranks 1333522+ (extremely rare)

    Args:
        rank: Integer rank (1-indexed), or None for unranked words

    Returns:
        Single letter code A–Z
    """
    if rank is None or rank < 1:
        # Unranked words get 'Z' (extremely rare)
        return 'Z'

    # Base B = 10^(1/4) = 10^0.25
    B = 10 ** 0.25

    # Continuous band index on log_B scale
    i_real = math.log(rank) / math.log(B)

    # Nearest integer index
    i = round(i_real)

    # Clamp to 0..25 (A..Z)
    i = max(0, min(25, i))

    # Convert to letter
    code = chr(ord('A') + i)

    return code


def code_to_rank(code: str) -> Tuple[int, int, int, int]:
    """
    Convert letter code to band index, center rank, and rank range.

    Args:
        code: Single letter A–Z

    Returns:
        Tuple of (band_index, center_rank, low_rank, high_rank)
        All ranks are inclusive.

    Raises:
        ValueError: If code is not A–Z
    """
    c = code.upper()
    i = ord(c) - ord('A')

    if i < 0 or i > 25:
        raise ValueError(f"Code must be A-Z, got: {code}")

    # Base B = 10^(1/4)
    B = 10 ** 0.25

    # Center of the band
    center = round(B ** i)

    # Half-step boundaries
    if i == 0:
        low = 1
    else:
        low = math.ceil(B ** (i - 0.5))
        low = max(1, low)

    high = math.ceil(B ** (i + 0.5)) - 1

    return (i, center, low, high)


def assign_tier(entry: dict, ranks: Dict[str, int]) -> dict:
    """Assign frequency rank code to an entry."""
    word = entry['word']
    rank = ranks.get(word)
    code = rank_to_code(rank)

    entry['frequency_tier'] = code
    return entry


def process_file(input_path: Path, output_path: Path, ranks: Dict[str, int]):
    """Process a JSONL file and assign rank codes."""
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return

    logger.info(f"Processing {input_path.name}")

    entries = []
    # Initialize counts for all letter codes A-Z
    tier_counts = {chr(ord('A') + i): 0 for i in range(26)}

    with ProgressDisplay(f"Assigning tiers to {input_path.name}", update_interval=1000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    tiered = assign_tier(entry, ranks)
                    tier_counts[tiered['frequency_tier']] += 1
                    entries.append(tiered)
                    progress.update(Lines=line_num, Entries=len(entries))
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue

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
            _, center, low, high = code_to_rank(code)
            logger.info(f"    {code}: {count:6,}  (ranks {low:,}-{high:,}, center ~{center:,})")
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
