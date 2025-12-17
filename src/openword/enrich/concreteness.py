#!/usr/bin/env python3
"""
brysbaert_enrich.py - Enrich entries with Brysbaert concreteness ratings

Adds concreteness ratings from the Brysbaert et al. (2014) dataset:
"Concreteness ratings for 40 thousand generally known English word lemmas"
Behavior Research Methods, 46, 904-911.

This significantly improves concreteness coverage compared to WordNet alone.
Coverage expected: ~40k words vs ~20-30k from WordNet.
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
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# License mapping
BRYSBAERT_LICENSE = "Brysbaert-Research"  # Custom identifier for this dataset

def load_brysbaert_ratings(filepath: Path) -> Dict[str, Tuple[float, float]]:
    """
    Load Brysbaert concreteness ratings from TSV file.

    Returns:
        Dict mapping word -> (mean_rating, std_dev)
        where mean_rating is on a 1-5 scale (5 = most concrete)
    """
    ratings = {}

    if not filepath.exists():
        logger.error(f"Brysbaert ratings file not found: {filepath}")
        return ratings

    logger.info(f"Loading Brysbaert ratings from {filepath}")

    with ProgressDisplay(f"Loading {filepath.name}", update_interval=1000) as progress:
        with open(filepath, "r", encoding="utf-8") as f:
            # Skip header line
            header = f.readline().strip().split("\t")

            # Verify expected columns
            if header[0] != "Word" or header[2] != "Conc.M":
                logger.warning(f"Unexpected header format in Brysbaert file: {header}")

            for line_num, line in enumerate(f, 2):  # Start at 2 since we skipped header
                parts = line.strip().split("\t")
                if len(parts) < 3:
                    continue

                word = parts[0].lower()  # Normalize to lowercase
                try:
                    mean_rating = float(parts[2])  # Conc.M
                    std_dev = float(parts[3]) if len(parts) > 3 else 0.0  # Conc.SD
                    ratings[word] = (mean_rating, std_dev)
                    progress.update(Lines=line_num-1, Ratings=len(ratings))
                except (ValueError, IndexError):
                    logger.warning(f"Line {line_num}: Could not parse rating for '{word}'")
                    continue

    logger.info(f"  -> Loaded {len(ratings):,} concreteness ratings")
    return ratings


def rating_to_category(rating: float) -> str:
    """
    Convert Brysbaert 1-5 scale to concrete/mixed/abstract category.

    Scale interpretation:
    - 1.0-2.5: abstract (low concreteness)
    - 2.5-3.5: mixed (medium concreteness)
    - 3.5-5.0: concrete (high concreteness)

    These thresholds are based on the distribution analysis in the original paper.
    """
    if rating >= 3.5:
        return "concrete"
    elif rating >= 2.5:
        return "mixed"
    else:
        return "abstract"


def add_brysbaert_source(entry: dict) -> dict:
    """Add 'brysbaert' to sources and update license_sources."""
    sources = entry.get("sources", [])
    if "brysbaert" not in sources:
        entry["sources"] = sorted(sources + ["brysbaert"])

        # Update license_sources
        license_sources = entry.get("license_sources", {})
        if BRYSBAERT_LICENSE not in license_sources:
            license_sources[BRYSBAERT_LICENSE] = ["brysbaert"]
        elif "brysbaert" not in license_sources[BRYSBAERT_LICENSE]:
            license_sources[BRYSBAERT_LICENSE] = sorted(
                license_sources[BRYSBAERT_LICENSE] + ["brysbaert"]
            )
        entry["license_sources"] = license_sources

    return entry


def enrich_entry(
    entry: dict,
    ratings: Dict[str, Tuple[float, float]],
    prefer_brysbaert: bool = True
) -> dict:
    """
    Enrich a single entry with Brysbaert concreteness data.

    Args:
        entry: Dictionary containing word entry
        ratings: Brysbaert ratings dictionary
        prefer_brysbaert: If True, Brysbaert ratings override existing concreteness.
                         If False, only fill missing concreteness data.

    Returns:
        Enriched entry dictionary
    """
    word = entry.get("id", "").lower()

    if word not in ratings:
        return entry

    mean_rating, std_dev = ratings[word]

    # Check if we should update concreteness
    existing_concreteness = entry.get("concreteness")

    should_update = (
        existing_concreteness is None or  # No existing data
        (prefer_brysbaert and existing_concreteness)  # Prefer Brysbaert even if data exists
    )

    if should_update:
        # Add concreteness category
        entry["concreteness"] = rating_to_category(mean_rating)

        # Add raw rating and std dev for advanced filtering
        entry["concreteness_rating"] = round(mean_rating, 2)
        entry["concreteness_sd"] = round(std_dev, 2)

        # Add brysbaert to sources
        entry = add_brysbaert_source(entry)

    return entry


def process_file(
    input_path: Path,
    output_path: Path,
    ratings: Dict[str, Tuple[float, float]],
    prefer_brysbaert: bool = True
):
    """Process a JSONL file and enrich entries with Brysbaert data."""
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info(f"Processing {input_path.name}")

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries_processed = 0
    entries_enriched = 0

    with ProgressDisplay(f"Enriching {input_path.name}", update_interval=1000) as progress:
        with open(input_path, "r", encoding="utf-8") as f_in, \
             open(output_path, "w", encoding="utf-8") as f_out:

            for line_num, line in enumerate(f_in, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)

                    # Check if entry will be enriched
                    had_concreteness = entry.get("concreteness") is not None

                    # Enrich entry
                    enriched_entry = enrich_entry(entry, ratings, prefer_brysbaert)

                    # Count if we added new data
                    has_concreteness = enriched_entry.get("concreteness") is not None
                    if has_concreteness and (not had_concreteness or prefer_brysbaert):
                        entries_enriched += 1

                    # Write enriched entry
                    f_out.write(json.dumps(enriched_entry, ensure_ascii=False, sort_keys=True) + "\n")
                    entries_processed += 1

                    progress.update(Lines=line_num, Processed=entries_processed, Enriched=entries_enriched)

                except json.JSONDecodeError:
                    logger.warning(f"Line {line_num}: Invalid JSON")
                    continue

    logger.info(f"  Enriched {entries_processed:,} entries")
    logger.info(f"    Added/updated concreteness: {entries_enriched:,}")
    logger.info(f"  -> {output_path}")


def main():
    """Main enrichment pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Enrich entries with Brysbaert concreteness data")
    parser.add_argument("--input", type=Path, required=True,
                        help="Input JSONL file (lexeme entries)")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output JSONL file")
    parser.add_argument("--language", default="en",
                        help="Language code for ratings file (default: en)")
    parser.add_argument("--no-prefer", action="store_true",
                        help="Do not override existing concreteness data")
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    raw_dir = data_root / "raw" / args.language

    ratings_file = raw_dir / "brysbaert_concreteness.txt"

    logger.info("Brysbaert concreteness enrichment")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Output: {args.output}")

    # Load Brysbaert ratings
    ratings = load_brysbaert_ratings(ratings_file)

    if not ratings:
        logger.error("No ratings loaded. Cannot proceed.")
        logger.error(f"Run: LEXICON_LANG={args.language} bash scripts/fetch/fetch_brysbaert.sh")
        sys.exit(1)

    prefer_brysbaert = not args.no_prefer
    if prefer_brysbaert:
        logger.info("Mode: Prefer Brysbaert (will override existing concreteness)")
    else:
        logger.info("Mode: Fill missing only (will not override existing concreteness)")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    process_file(args.input, args.output, ratings, prefer_brysbaert)

    logger.info("")
    logger.info("Brysbaert enrichment complete")


if __name__ == "__main__":
    main()
