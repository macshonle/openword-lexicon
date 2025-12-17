#!/usr/bin/env python3
"""
Enrichment pipeline for v2 scanner output.

Schema-driven enrichment pipeline that chains multiple enrichment passes:
1. Frequency tier assignment (OpenSubtitles-based)
2. Concreteness ratings (Brysbaert et al.)
3. Age of Acquisition (Kuperman et al.)

Configuration is loaded from schema/enrichment/pipeline.yaml which defines:
- Enrichment stages and their order
- Field definitions and defaults
- Output field ordering

Usage:
    uv run python -m openword.enrich.pipeline \\
        --input en-wikt-v2.jsonl \\
        --output en-wikt-v2-enriched.jsonl

Pipeline:
    scanner output → frequency → concreteness → AoA → enriched output
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import orjson
import yaml

from openword.progress_display import ProgressDisplay

# Import enrichment modules
from openword.enrich.frequency import (
    load_frequency_ranks,
    assign_tier,
)
from openword.enrich.concreteness import (
    load_brysbaert_ratings,
    rating_to_category,
    add_brysbaert_source,
)
from openword.enrich.aoa import (
    load_aoa_ratings,
    aoa_to_grade_level,
    add_kuperman_source,
)


# =============================================================================
# Schema Loading and Configuration
# =============================================================================

def get_schema_dir() -> Path:
    """Get the schema/enrichment directory path."""
    # From src/openword/enrich/ go up to project root
    return Path(__file__).parent.parent.parent.parent / "schema" / "enrichment"


def load_pipeline_config() -> Dict[str, Any]:
    """
    Load the enrichment pipeline configuration from pipeline.yaml.

    Returns:
        Pipeline configuration dictionary
    """
    config_path = get_schema_dir() / "pipeline.yaml"
    if not config_path.exists():
        # Fall back to hardcoded defaults if no config
        return {
            'settings': {
                'priority_fields': ['id', 'pos', 'wc', 'nsyll'],
                'defaults_policy': {'omit_defaults': True},
            },
            'output_fields': [],
        }

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_field_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Load field definitions from all enrichment schemas.

    Returns:
        Dict mapping field_name -> field schema (including 'default', 'omit_default')
    """
    schema_dir = get_schema_dir()
    field_schemas: Dict[str, Dict[str, Any]] = {}

    # Load each enrichment schema
    for schema_file in ['frequency.yaml', 'concreteness.yaml', 'aoa.yaml']:
        schema_path = schema_dir / schema_file
        if not schema_path.exists():
            continue

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)

        # Extract field definitions
        for field_name, field_def in schema.get('fields', {}).items():
            field_schemas[field_name] = {
                'default': field_def.get('default'),
                'omit_default': field_def.get('omit_default', False),
                'type': field_def.get('type'),
                'source': schema.get('name'),
            }

    return field_schemas


# Global config loaded at module level
_pipeline_config: Optional[Dict[str, Any]] = None
_field_schemas: Optional[Dict[str, Dict[str, Any]]] = None


def get_pipeline_config() -> Dict[str, Any]:
    """Get cached pipeline configuration."""
    global _pipeline_config
    if _pipeline_config is None:
        _pipeline_config = load_pipeline_config()
    return _pipeline_config


def get_field_schemas() -> Dict[str, Dict[str, Any]]:
    """Get cached field schemas."""
    global _field_schemas
    if _field_schemas is None:
        _field_schemas = load_field_schemas()
    return _field_schemas


def get_priority_fields() -> List[str]:
    """Get priority fields from config or use defaults."""
    config = get_pipeline_config()
    return config.get('settings', {}).get('priority_fields', ['id', 'pos', 'wc', 'nsyll'])


def should_omit_defaults() -> bool:
    """Check if defaults should be omitted from output."""
    config = get_pipeline_config()
    return config.get('settings', {}).get('defaults_policy', {}).get('omit_defaults', True)


def apply_default_omission(entry: dict) -> dict:
    """
    Remove fields that match their default values (if omit_defaults is enabled).

    This reduces output size by not writing fields that would have their
    default interpretation anyway.

    Args:
        entry: Entry dictionary with enrichment fields

    Returns:
        Entry with default-valued fields removed (if configured)
    """
    if not should_omit_defaults():
        return entry

    field_schemas = get_field_schemas()
    result = entry.copy()

    for field_name, schema in field_schemas.items():
        if not schema.get('omit_default', False):
            continue

        default_value = schema.get('default')

        # Check if field exists and matches default
        if field_name in result:
            field_value = result[field_name]
            # Match if both are None/null, or if values are equal
            if field_value == default_value or (field_value is None and default_value is None):
                del result[field_name]

    return result


def order_entry_fields(entry: dict) -> dict:
    """
    Reorder entry fields: priority fields first, then remaining fields sorted.

    Uses priority_fields from pipeline.yaml configuration.

    Args:
        entry: Entry dictionary

    Returns:
        New dict with fields in canonical order
    """
    priority_fields = get_priority_fields()
    ordered = {}

    # Add priority fields first (in order)
    for field in priority_fields:
        if field in entry:
            ordered[field] = entry[field]

    # Add remaining fields in sorted order
    remaining = sorted(k for k in entry.keys() if k not in priority_fields)
    for key in remaining:
        ordered[key] = entry[key]

    return ordered


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_all_data_sources(language: str = 'en') -> Tuple[
    Dict[str, int],  # frequency ranks
    Dict[str, Tuple[float, float]],  # brysbaert ratings
    Dict[str, Tuple[float, float, float]],  # aoa ratings
]:
    """Load all enrichment data sources."""
    # From src/openword/enrich/ go up 4 levels to project root
    data_root = Path(__file__).parent.parent.parent.parent / "data"
    raw_dir = data_root / "raw" / language

    # Frequency data
    freq_file = raw_dir / f"{language}_50k.txt"
    freq_ranks = load_frequency_ranks(freq_file) if freq_file.exists() else {}

    # Brysbaert concreteness
    brysbaert_file = raw_dir / "brysbaert_concreteness.txt"
    brysbaert_ratings = load_brysbaert_ratings(brysbaert_file) if brysbaert_file.exists() else {}

    # Kuperman AoA
    aoa_file = raw_dir / "kuperman_aoa.txt"
    aoa_ratings = load_aoa_ratings(aoa_file) if aoa_file.exists() else {}

    return freq_ranks, brysbaert_ratings, aoa_ratings


def enrich_entry(
    entry: dict,
    freq_ranks: Dict[str, int],
    lowercase_words: Set[str],
    brysbaert_ratings: Dict[str, Tuple[float, float]],
    aoa_ratings: Dict[str, Tuple[float, float, float]],
    prefer_brysbaert: bool = True,
    min_aoa_known: float = 0.5,
) -> dict:
    """
    Apply all enrichments to a single entry.

    Args:
        entry: Entry dictionary with 'id' field
        freq_ranks: Frequency rank lookup
        lowercase_words: Set of lowercase words in lexicon
        brysbaert_ratings: Brysbaert concreteness ratings
        aoa_ratings: Kuperman AoA ratings
        prefer_brysbaert: Override existing concreteness with Brysbaert
        min_aoa_known: Minimum known proportion for AoA

    Returns:
        Enriched entry dictionary
    """
    word = entry['id']
    word_lower = word.lower()

    # 1. Frequency tier
    entry = assign_tier(entry, freq_ranks, lowercase_words)

    # 2. Brysbaert concreteness
    if word_lower in brysbaert_ratings:
        mean_rating, std_dev = brysbaert_ratings[word_lower]
        existing_concreteness = entry.get('concreteness')

        should_update = (
            existing_concreteness is None or
            (prefer_brysbaert and existing_concreteness)
        )

        if should_update:
            entry['concreteness'] = rating_to_category(mean_rating)
            entry['concreteness_rating'] = round(mean_rating, 2)
            entry['concreteness_sd'] = round(std_dev, 2)
            entry = add_brysbaert_source(entry)

    # 3. Kuperman AoA
    if word_lower in aoa_ratings:
        mean_aoa, std_dev, known_proportion = aoa_ratings[word_lower]

        if known_proportion >= min_aoa_known:
            entry['aoa_rating'] = round(mean_aoa, 2)
            entry['aoa_sd'] = round(std_dev, 2)
            entry['aoa_grade'] = aoa_to_grade_level(mean_aoa)
            entry = add_kuperman_source(entry)

    return entry


def process_file(
    input_path: Path,
    output_path: Path,
    language: str = 'en',
    prefer_brysbaert: bool = True,
    min_aoa_known: float = 0.5,
    sort_output: bool = True,
):
    """
    Process v2 scanner output through full enrichment pipeline.

    Args:
        input_path: Path to v2 scanner JSONL output
        output_path: Path for enriched output
        language: Language code for data sources
        prefer_brysbaert: Override existing concreteness
        min_aoa_known: Minimum known proportion for AoA
        sort_output: Sort entries lexicographically
    """
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info("V2 Enrichment Pipeline")
    logger.info(f"  Input: {input_path}")
    logger.info(f"  Output: {output_path}")

    # Log schema configuration
    field_schemas = get_field_schemas()
    omit_defaults = should_omit_defaults()
    priority_fields = get_priority_fields()

    logger.info("")
    logger.info("Schema configuration:")
    logger.info(f"  Priority fields: {', '.join(priority_fields)}")
    logger.info(f"  Omit defaults: {omit_defaults}")
    logger.info(f"  Enrichment fields defined: {len(field_schemas)}")

    # Load all data sources
    logger.info("")
    logger.info("Loading enrichment data sources...")
    freq_ranks, brysbaert_ratings, aoa_ratings = load_all_data_sources(language)

    logger.info(f"  Frequency ranks: {len(freq_ranks):,}")
    logger.info(f"  Brysbaert concreteness: {len(brysbaert_ratings):,}")
    logger.info(f"  Kuperman AoA: {len(aoa_ratings):,}")

    # Pass 1: Load all entries and build lowercase word set
    logger.info("")
    logger.info("Pass 1: Loading entries...")

    entries = []
    lowercase_words: Set[str] = set()

    with ProgressDisplay("Loading entries", update_interval=10000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    word = entry['id']
                    if word.islower():
                        lowercase_words.add(word)
                    progress.update(Lines=line_num, Entries=len(entries))
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue

    logger.info(f"  Loaded {len(entries):,} entries")
    logger.info(f"  Found {len(lowercase_words):,} lowercase words")

    # Pass 2: Enrich all entries
    logger.info("")
    logger.info("Pass 2: Enriching entries...")

    stats = {
        'frequency_assigned': 0,
        'concreteness_added': 0,
        'aoa_added': 0,
    }

    with ProgressDisplay("Enriching", update_interval=10000) as progress:
        for i, entry in enumerate(entries, 1):
            # Track what we're adding
            had_freq = entry.get('frequency_tier') is not None
            had_conc = entry.get('concreteness') is not None
            had_aoa = entry.get('aoa_rating') is not None

            # Enrich
            entry = enrich_entry(
                entry,
                freq_ranks,
                lowercase_words,
                brysbaert_ratings,
                aoa_ratings,
                prefer_brysbaert,
                min_aoa_known,
            )

            # Update stats
            if not had_freq and entry.get('frequency_tier') is not None:
                stats['frequency_assigned'] += 1
            if not had_conc and entry.get('concreteness') is not None:
                stats['concreteness_added'] += 1
            if not had_aoa and entry.get('aoa_rating') is not None:
                stats['aoa_added'] += 1

            progress.update(Entries=i)

    logger.info(f"  Frequency tiers assigned: {stats['frequency_assigned']:,}")
    logger.info(f"  Concreteness added: {stats['concreteness_added']:,}")
    logger.info(f"  AoA added: {stats['aoa_added']:,}")

    # Optional: Sort entries lexicographically
    if sort_output:
        logger.info("")
        logger.info("Sorting entries lexicographically...")
        entries.sort(key=lambda e: e['id'].lower())

    # Write output
    logger.info("")
    logger.info("Writing enriched output...")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in entries:
            # Apply default omission (removes fields matching schema defaults)
            cleaned_entry = apply_default_omission(entry)
            # Reorder fields (priority fields first, then alphabetical)
            ordered_entry = order_entry_fields(cleaned_entry)
            line = orjson.dumps(ordered_entry) + b'\n'
            f.write(line)

    logger.info(f"  -> {output_path}")

    # Summary statistics
    logger.info("")
    logger.info("Enrichment summary:")
    tier_counts = {}
    for entry in entries:
        tier = entry.get('frequency_tier', 'Z')
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    for tier in sorted(tier_counts.keys()):
        logger.info(f"  Tier {tier}: {tier_counts[tier]:,}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='V2 enrichment pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    uv run python -m openword.v2_enrich \\
        --input data/wikt/en-wikt-v2.jsonl \\
        --output data/wikt/en-wikt-v2-enriched.jsonl
        """
    )
    parser.add_argument('--input', type=Path, required=True,
                        help='Input JSONL file (v2 scanner output)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output JSONL file (enriched)')
    parser.add_argument('--language', default='en',
                        help='Language code for data sources (default: en)')
    parser.add_argument('--no-prefer-brysbaert', action='store_true',
                        help='Do not override existing concreteness data')
    parser.add_argument('--min-aoa-known', type=float, default=0.5,
                        help='Minimum known proportion for AoA (default: 0.5)')
    parser.add_argument('--no-sort', action='store_true',
                        help='Do not sort output lexicographically')

    args = parser.parse_args()

    process_file(
        input_path=args.input,
        output_path=args.output,
        language=args.language,
        prefer_brysbaert=not args.no_prefer_brysbaert,
        min_aoa_known=args.min_aoa_known,
        sort_output=not args.no_sort,
    )

    logger.info("")
    logger.info("V2 enrichment pipeline complete")


if __name__ == '__main__':
    main()
