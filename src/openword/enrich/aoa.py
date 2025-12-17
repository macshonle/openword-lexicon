#!/usr/bin/env python3
"""
aoa_enrich.py - Enrich entries with Age of Acquisition (AoA) ratings

Adds AoA ratings from the Kuperman et al. (2012) dataset:
"Age-of-acquisition ratings for 30,000 English words"
Behavior Research Methods, 44, 978-990.

AoA indicates the estimated age (in years) when a word is typically acquired.
Lower values = earlier acquisition (e.g., "cat" ~4 years, "philosophy" ~13 years).

Use cases:
- Filter vocabulary for children's games/apps by acquisition age
- Grade-level appropriate word selection
- Vocabulary difficulty estimation
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

from openword.progress_display import ProgressDisplay

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# License mapping
KUPERMAN_LICENSE = "CC-BY-4.0"


def load_aoa_ratings(filepath: Path) -> Dict[str, Tuple[float, float, float]]:
    """
    Load Kuperman AoA ratings from TSV file.

    Returns:
        Dict mapping word -> (mean_aoa, std_dev, known_proportion)
        where mean_aoa is the estimated acquisition age in years (roughly 2-25)
        and known_proportion is the proportion of raters who knew the word
        (Note: Despite the column name "Dunno", this column actually represents
        the proportion who DID know the word in this dataset)
    """
    ratings = {}

    if not filepath.exists():
        logger.error(f"AoA ratings file not found: {filepath}")
        return ratings

    logger.info(f"Loading AoA ratings from {filepath}")

    with ProgressDisplay(f"Loading {filepath.name}", update_interval=1000) as progress:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip header line
            header = f.readline().strip().split('\t')

            # Verify expected columns
            expected = ['Word', 'Rating.Mean', 'Rating.SD', 'Dunno']
            if header[:4] != expected:
                logger.warning(f"Unexpected header format in AoA file: {header}")

            for line_num, line in enumerate(f, 2):  # Start at 2 since we skipped header
                parts = line.strip().split('\t')
                if len(parts) < 4:
                    continue

                word = parts[0].lower()  # Normalize to lowercase

                # Skip entries with NA values (words too obscure to rate reliably)
                if parts[1] == 'NA' or parts[1] == '#N/A':
                    continue

                try:
                    mean_aoa = float(parts[1])  # Rating.Mean
                    std_dev = float(parts[2]) if parts[2] and parts[2] != 'NA' else 0.0  # Rating.SD
                    # Note: Despite the column name "Dunno", this value actually represents
                    # the proportion of raters who KNEW the word (not who didn't know)
                    known_proportion = float(parts[3]) if parts[3] and parts[3] != 'NA' else 0.0

                    ratings[word] = (mean_aoa, std_dev, known_proportion)
                    progress.update(Lines=line_num-1, Ratings=len(ratings))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Line {line_num}: Could not parse rating for '{word}': {e}")
                    continue

    logger.info(f"  -> Loaded {len(ratings):,} AoA ratings")
    return ratings


def aoa_to_grade_level(aoa: float) -> str:
    """
    Convert AoA rating to approximate US grade level category.

    Mapping based on typical school ages:
    - Pre-K: acquired before age 5 (very common words)
    - K-2: acquired ages 5-8 (early elementary)
    - 3-5: acquired ages 8-11 (upper elementary)
    - 6-8: acquired ages 11-14 (middle school)
    - 9-12: acquired ages 14-18 (high school)
    - Adult: acquired 18+ (advanced vocabulary)

    Args:
        aoa: Age of acquisition in years

    Returns:
        Grade level category string
    """
    if aoa < 5:
        return 'pre-k'
    elif aoa < 8:
        return 'k-2'
    elif aoa < 11:
        return '3-5'
    elif aoa < 14:
        return '6-8'
    elif aoa < 18:
        return '9-12'
    else:
        return 'adult'


def add_kuperman_source(entry: dict) -> dict:
    """Add 'kuperman_aoa' to sources and update license_sources."""
    sources = entry.get('sources', [])
    if 'kuperman_aoa' not in sources:
        entry['sources'] = sorted(sources + ['kuperman_aoa'])

        # Update license_sources
        license_sources = entry.get('license_sources', {})
        if KUPERMAN_LICENSE not in license_sources:
            license_sources[KUPERMAN_LICENSE] = ['kuperman_aoa']
        elif 'kuperman_aoa' not in license_sources[KUPERMAN_LICENSE]:
            license_sources[KUPERMAN_LICENSE] = sorted(
                license_sources[KUPERMAN_LICENSE] + ['kuperman_aoa']
            )
        entry['license_sources'] = license_sources

    return entry


def enrich_entry(
    entry: dict,
    ratings: Dict[str, Tuple[float, float, float]],
    min_known_proportion: float = 0.5
) -> dict:
    """
    Enrich a single entry with Kuperman AoA data.

    Args:
        entry: Dictionary containing word entry
        ratings: AoA ratings dictionary
        min_known_proportion: Minimum proportion of raters who knew the word
                             (filters out very obscure words with unreliable ratings)

    Returns:
        Enriched entry dictionary
    """
    word = entry.get('id', '').lower()

    if word not in ratings:
        return entry

    mean_aoa, std_dev, known_proportion = ratings[word]

    # Skip words that most raters didn't know (unreliable ratings)
    if known_proportion < min_known_proportion:
        return entry

    # Add AoA rating (in years)
    entry['aoa_rating'] = round(mean_aoa, 2)

    # Add standard deviation for filtering precision
    entry['aoa_sd'] = round(std_dev, 2)

    # Add grade level category for easy filtering
    entry['aoa_grade'] = aoa_to_grade_level(mean_aoa)

    # Add kuperman_aoa to sources
    entry = add_kuperman_source(entry)

    return entry


def process_file(
    input_path: Path,
    output_path: Path,
    ratings: Dict[str, Tuple[float, float, float]],
    min_known_proportion: float = 0.5
):
    """Process a JSONL file and enrich entries with AoA data."""
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info(f"Processing {input_path.name}")

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries_processed = 0
    entries_enriched = 0

    with ProgressDisplay(f"Enriching {input_path.name}", update_interval=1000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f_in, \
             open(output_path, 'w', encoding='utf-8') as f_out:

            for line_num, line in enumerate(f_in, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)

                    # Check if entry will be enriched
                    had_aoa = entry.get('aoa_rating') is not None

                    # Enrich entry
                    enriched_entry = enrich_entry(entry, ratings, min_known_proportion)

                    # Count if we added new data
                    has_aoa = enriched_entry.get('aoa_rating') is not None
                    if has_aoa and not had_aoa:
                        entries_enriched += 1

                    # Write enriched entry
                    f_out.write(json.dumps(enriched_entry, ensure_ascii=False, sort_keys=True) + '\n')
                    entries_processed += 1

                    progress.update(Lines=line_num, Processed=entries_processed, Enriched=entries_enriched)

                except json.JSONDecodeError:
                    logger.warning(f"Line {line_num}: Invalid JSON")
                    continue

    logger.info(f"  Processed {entries_processed:,} entries")
    logger.info(f"    Added AoA ratings: {entries_enriched:,}")
    logger.info(f"  -> {output_path}")


def main():
    """Main enrichment pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Enrich entries with Kuperman AoA data')
    parser.add_argument('--input', type=Path, required=True,
                        help='Input JSONL file (lexeme entries)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output JSONL file')
    parser.add_argument('--language', default='en',
                        help='Language code for ratings file (default: en)')
    parser.add_argument('--min-known', type=float, default=0.5,
                        help='Minimum proportion of raters who knew the word (default: 0.5)')
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / args.language

    ratings_file = raw_dir / "kuperman_aoa.txt"

    logger.info("Kuperman AoA enrichment")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Output: {args.output}")
    logger.info(f"  Min known proportion: {args.min_known}")

    # Load AoA ratings
    ratings = load_aoa_ratings(ratings_file)

    if not ratings:
        logger.error("No ratings loaded. Cannot proceed.")
        logger.error(f"Ensure {ratings_file} exists (download via fetch_sources.py)")
        sys.exit(1)

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    process_file(args.input, args.output, ratings, args.min_known)

    logger.info("")
    logger.info("AoA enrichment complete")


if __name__ == '__main__':
    main()
