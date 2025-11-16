#!/usr/bin/env python3
"""
frequency_tiers.py — Assign frequency tier buckets to entries.

Reads:
  - data/raw/plus/en_50k.txt (frequency list: word<space>count)
  - data/intermediate/{core,plus}/*_enriched.jsonl

Outputs:
  - data/intermediate/{core,plus}/*_tiered.jsonl

Tiers (based on 50k frequency dataset):
  - top10:    ranks 1-10         (ultra-common function words)
  - top100:   ranks 11-100       (core vocabulary)
  - top300:   ranks 101-300      (early reader / sight words)
  - top500:   ranks 301-500      (simple vocabulary)
  - top1k:    ranks 501-1,000    (high-frequency everyday)
  - top3k:    ranks 1,001-3,000  (conversational fluency, ~95% coverage)
  - top10k:   ranks 3,001-10,000 (standard educated vocabulary)
  - top25k:   ranks 10,001-25,000 (extended vocabulary)
  - top50k:   ranks 25,001-50,000 (rare/technical/variants)
  - rare:     ranks >50,000 or not in frequency list
"""

import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Optional

import orjson


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


def get_tier(rank: Optional[int]) -> str:
    """
    Convert rank to tier bucket.

    10-tier system aligned with 50k frequency dataset:
    - Respects linguistic breakpoints (esp. 3k = 95% comprehension)
    - Better granularity in critical 1k-10k range
    - Supports educational use cases (grade-level targeting)
    """
    if rank is None:
        return 'rare'
    elif rank <= 10:
        return 'top10'
    elif rank <= 100:
        return 'top100'
    elif rank <= 300:
        return 'top300'
    elif rank <= 500:
        return 'top500'
    elif rank <= 1000:
        return 'top1k'
    elif rank <= 3000:
        return 'top3k'
    elif rank <= 10000:
        return 'top10k'
    elif rank <= 25000:
        return 'top25k'
    elif rank <= 50000:
        return 'top50k'
    else:
        return 'rare'


def assign_tier(entry: dict, ranks: Dict[str, int]) -> dict:
    """Assign frequency tier to an entry."""
    word = entry['word']
    rank = ranks.get(word)
    tier = get_tier(rank)

    entry['frequency_tier'] = tier
    return entry


def process_file(input_path: Path, output_path: Path, ranks: Dict[str, int]):
    """Process a JSONL file and assign tiers."""
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return

    logger.info(f"Processing {input_path.name}")

    entries = []
    tier_counts = {
        'top10': 0,
        'top100': 0,
        'top300': 0,
        'top500': 0,
        'top1k': 0,
        'top3k': 0,
        'top10k': 0,
        'top25k': 0,
        'top50k': 0,
        'rare': 0
    }

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                logger.info(f"  Processed {line_num:,} entries...")

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                tiered = assign_tier(entry, ranks)
                tier_counts[tiered['frequency_tier']] += 1
                entries.append(tiered)
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in entries:
            line = orjson.dumps(entry) + b'\n'
            f.write(line)

    logger.info(f"  Tiered {len(entries):,} entries")
    logger.info(f"    top10:    {tier_counts['top10']:,}")
    logger.info(f"    top100:   {tier_counts['top100']:,}")
    logger.info(f"    top300:   {tier_counts['top300']:,}")
    logger.info(f"    top500:   {tier_counts['top500']:,}")
    logger.info(f"    top1k:    {tier_counts['top1k']:,}")
    logger.info(f"    top3k:    {tier_counts['top3k']:,}")
    logger.info(f"    top10k:   {tier_counts['top10k']:,}")
    logger.info(f"    top25k:   {tier_counts['top25k']:,}")
    logger.info(f"    top50k:   {tier_counts['top50k']:,}")
    logger.info(f"    rare:     {tier_counts['rare']:,}")
    logger.info(f"  -> {output_path}")


def main():
    """Main frequency tier assignment pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / "plus"
    intermediate_dir = data_root / "intermediate"

    freq_file = raw_dir / "en_50k.txt"

    logger.info("Frequency tier assignment")

    # Load frequency ranks
    ranks = load_frequency_ranks(freq_file)

    if not ranks:
        logger.warning("No frequency data loaded. All words will be marked 'rare'.")

    # Process core entries
    core_input = intermediate_dir / "core" / "core_entries_enriched.jsonl"
    core_output = intermediate_dir / "core" / "core_entries_tiered.jsonl"

    if core_input.exists():
        process_file(core_input, core_output, ranks)

    # Process wikt entries
    plus_input = intermediate_dir / "plus" / "wikt_entries_enriched.jsonl"
    plus_output = intermediate_dir / "plus" / "wikt_entries_tiered.jsonl"

    if plus_input.exists():
        process_file(plus_input, plus_output, ranks)

    logger.info("")
    logger.info("Frequency tier assignment complete")


if __name__ == '__main__':
    main()
