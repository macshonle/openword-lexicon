#!/usr/bin/env python3
"""
wordnet_enrich.py — Enrich entries with WordNet data (POS backfill).

IMPORTANT: Concreteness enrichment is deprecated in this module!
Use brysbaert_enrich.py INSTEAD for concreteness data (more accurate, better coverage).
WordNet's concreteness heuristic has known issues (see tests/WORDNET_BASELINE_FINDINGS.md).

UNIFIED BUILD MODE:
Reads:
  - data/intermediate/unified/entries_merged.jsonl

Outputs:
  - data/intermediate/unified/entries_enriched.jsonl

LEGACY MODE (Core/Plus):
Reads:
  - data/intermediate/{core,plus}/*_entries.jsonl

Outputs:
  - data/intermediate/{core,plus}/*_entries_enriched.jsonl

Enrichment:
  - Backfills POS tags where confident and missing (highly accurate)
  - [DEPRECATED] Concreteness for nouns (use Brysbaert instead!)
  - Tracks 'wordnet' source when enrichment is applied
  - Updates license_sources to include WordNet license
  - Uses NLTK's WordNet interface

Recommended pipeline order:
  1. merge_all.py - Combine word sources
  2. brysbaert_enrich.py - Add concreteness (PRIMARY SOURCE)
  3. wordnet_enrich.py - Backfill POS only
  4. frequency_tiers.py - Add frequency data
"""

import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Optional

import nltk
from nltk.corpus import wordnet as wn
import orjson

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Physical/concrete domains (simplified heuristic)
CONCRETE_DOMAINS = {
    'artifact', 'object', 'substance', 'food', 'plant', 'animal',
    'body', 'person', 'location', 'shape', 'container', 'vehicle',
    'building', 'furniture', 'clothing', 'tool', 'weapon', 'device'
}

ABSTRACT_DOMAINS = {
    'attribute', 'state', 'feeling', 'cognition', 'communication',
    'act', 'phenomenon', 'process', 'time', 'relation', 'quantity',
    'motivation', 'possession'
}


def ensure_wordnet_data():
    """Download WordNet data if not present."""
    try:
        # Check if WordNet is available
        wn.synsets('test')
        logger.info("WordNet data found")
    except LookupError:
        logger.info("Downloading WordNet data...")
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)  # Open Multilingual WordNet
        logger.info("WordNet data downloaded")


def normalize_for_lookup(word: str) -> str:
    """
    Normalize word for dictionary lookup.

    Handles:
    - Unicode NFKC normalization (café -> café)
    - Lowercase conversion
    - Accent stripping for fallback lookups

    Returns normalized word suitable for WordNet lookup.
    """
    # NFKC normalization (canonical decomposition + compatibility composition)
    normalized = unicodedata.normalize('NFKC', word)
    # Lowercase
    normalized = normalized.lower()
    return normalized


def strip_accents(word: str) -> str:
    """
    Strip accents from word for fallback lookups.

    Example: café -> cafe, naïve -> naive

    Used when direct lookup fails, to find English equivalents.
    """
    # NFD normalization splits accents from base characters
    nfd = unicodedata.normalize('NFD', word)
    # Filter out combining diacritical marks
    without_accents = ''.join(
        char for char in nfd
        if not unicodedata.combining(char)
    )
    # Re-normalize to NFC
    return unicodedata.normalize('NFC', without_accents)


def get_concreteness(word: str) -> Optional[str]:
    """
    Determine concreteness for a noun using WordNet.

    **DEPRECATED**: This heuristic has accuracy issues (~45% on test data).
    Use Brysbaert concreteness ratings instead (brysbaert_enrich.py).

    Known issues:
    - Over-classifies as "mixed" (castle, dog, hammer → mixed, should be concrete)
    - Under-estimates concrete/abstract distinctions

    See tests/WORDNET_BASELINE_FINDINGS.md for details.

    Returns: 'concrete', 'abstract', 'mixed', or None
    """
    # Normalize word for lookup
    normalized = normalize_for_lookup(word)

    # Try direct lookup first
    synsets = wn.synsets(normalized, pos=wn.NOUN)

    # If no results and word has accents, try without accents
    if not synsets and normalized != strip_accents(normalized):
        synsets = wn.synsets(strip_accents(normalized), pos=wn.NOUN)

    if not synsets:
        return None

    concrete_count = 0
    abstract_count = 0

    for synset in synsets:
        # Get lexname (lexicographer file name) which indicates broad category
        lexname = synset.lexname()

        # Check hypernyms for physical entities
        is_concrete = False
        is_abstract = False

        # Check lexname
        if any(domain in lexname for domain in CONCRETE_DOMAINS):
            is_concrete = True
        if any(domain in lexname for domain in ABSTRACT_DOMAINS):
            is_abstract = True

        # Check hypernym path for physical entity
        hypernym_names = set()
        for hypernym_path in synset.hypernym_paths():
            for syn in hypernym_path:
                hypernym_names.add(syn.name())

        # Physical entity is a strong indicator of concreteness
        if any('physical_entity' in name or 'object' in name
               for name in hypernym_names):
            is_concrete = True

        # Abstraction is a strong indicator of abstractness
        if any('abstraction' in name or 'abstract_entity' in name
               for name in hypernym_names):
            is_abstract = True

        if is_concrete:
            concrete_count += 1
        if is_abstract:
            abstract_count += 1

    # Classify based on counts
    if concrete_count > 0 and abstract_count > 0:
        return 'mixed'
    elif concrete_count > 0:
        return 'concrete'
    elif abstract_count > 0:
        return 'abstract'

    # Default to concrete if uncertain (conservative)
    return None


def get_wordnet_pos(word: str) -> List[str]:
    """
    Get POS tags from WordNet for a word.

    Handles accent normalization automatically (café -> cafe for lookup).
    This function has high accuracy (100% on test data).
    """
    pos_tags = set()

    # Normalize word for lookup
    normalized = normalize_for_lookup(word)

    # Try direct lookup first
    if wn.synsets(normalized, pos=wn.NOUN):
        pos_tags.add('noun')
    if wn.synsets(normalized, pos=wn.VERB):
        pos_tags.add('verb')
    if wn.synsets(normalized, pos=wn.ADJ):
        pos_tags.add('adjective')
    if wn.synsets(normalized, pos=wn.ADV):
        pos_tags.add('adverb')

    # If no results and word has accents, try without accents
    if not pos_tags and normalized != strip_accents(normalized):
        normalized_no_accent = strip_accents(normalized)

        if wn.synsets(normalized_no_accent, pos=wn.NOUN):
            pos_tags.add('noun')
        if wn.synsets(normalized_no_accent, pos=wn.VERB):
            pos_tags.add('verb')
        if wn.synsets(normalized_no_accent, pos=wn.ADJ):
            pos_tags.add('adjective')
        if wn.synsets(normalized_no_accent, pos=wn.ADV):
            pos_tags.add('adverb')

    return sorted(pos_tags)


def add_wordnet_source(entry: dict) -> dict:
    """Add 'wordnet' to sources and update license_sources if enrichment was applied."""
    sources = entry.get('sources', [])

    # Only add if enrichment actually happened
    if 'wordnet' not in sources:
        entry['sources'] = sorted(sources + ['wordnet'])

        # Update license_sources
        license_sources = entry.get('license_sources', {})
        wordnet_license = 'WordNet'
        if wordnet_license not in license_sources:
            license_sources[wordnet_license] = ['wordnet']
        elif 'wordnet' not in license_sources[wordnet_license]:
            license_sources[wordnet_license] = sorted(license_sources[wordnet_license] + ['wordnet'])

        entry['license_sources'] = license_sources

    return entry


def enrich_entry(entry: dict) -> dict:
    """Enrich a single entry with WordNet data."""
    word = entry['word']
    enriched = False

    # Skip multi-word phrases (WordNet doesn't handle them well)
    if entry.get('word_count', 1) > 1:
        return entry

    # Backfill POS if empty
    if not entry.get('pos'):
        wn_pos = get_wordnet_pos(word)
        if wn_pos:
            entry['pos'] = wn_pos
            enriched = True

    # Add concreteness for nouns
    if 'noun' in entry.get('pos', []):
        if not entry.get('concreteness'):  # Only add if missing
            concreteness = get_concreteness(word)
            if concreteness:
                entry['concreteness'] = concreteness
                enriched = True

    # Track WordNet as a source if we enriched the entry
    if enriched:
        entry = add_wordnet_source(entry)

    return entry


def process_file(input_path: Path, output_path: Path):
    """Process a JSONL file and enrich entries."""
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return

    logger.info(f"Processing {input_path.name}")

    entries = []
    enriched_count = 0
    pos_backfilled = 0

    with ProgressDisplay(f"Enriching {input_path.name}", update_interval=1000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    original_pos = entry.get('pos', [])

                    enriched = enrich_entry(entry)

                    # Track stats
                    if 'concreteness' in enriched:
                        enriched_count += 1
                    if not original_pos and enriched.get('pos'):
                        pos_backfilled += 1

                    entries.append(enriched)
                    progress.update(Lines=line_num, Entries=len(entries), Enriched=enriched_count)

                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in entries:
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"  Enriched {len(entries):,} entries")
    logger.info(f"    Concreteness added: {enriched_count:,}")
    logger.info(f"    POS backfilled: {pos_backfilled:,}")
    logger.info(f"  -> {output_path}")


def main():
    """Main enrichment pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Enrich entries with WordNet data')
    parser.add_argument('--unified', action='store_true',
                        help='Use unified build mode (language-based structure)')
    parser.add_argument('--language', default='en',
                        help='Language code (default: en)')
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate"

    logger.info("WordNet enrichment")

    # Ensure WordNet data is available
    ensure_wordnet_data()

    if args.unified:
        # UNIFIED BUILD MODE (language-based)
        logger.info(f"Mode: Unified build ({args.language})")

        lang_dir = intermediate_dir / args.language
        unified_input = lang_dir / "entries_merged.jsonl"
        unified_output = lang_dir / "entries_enriched.jsonl"

        if unified_input.exists():
            process_file(unified_input, unified_output)
        else:
            logger.error(f"Unified input file not found: {unified_input}")
            logger.error("Run merge_all.py first")
            sys.exit(1)
    else:
        # LEGACY MODE (Core/Plus separate) - deprecated
        logger.warning("Legacy mode is deprecated. Use --unified flag.")
        logger.info("Mode: Legacy (Core/Plus separate)")

        # Process core entries
        core_input = intermediate_dir / "core" / "core_entries.jsonl"
        core_output = intermediate_dir / "core" / "core_entries_enriched.jsonl"

        if core_input.exists():
            process_file(core_input, core_output)

        # Process wikt entries
        plus_input = intermediate_dir / "plus" / "wikt_entries.jsonl"
        plus_output = intermediate_dir / "plus" / "wikt_entries_enriched.jsonl"

        if plus_input.exists():
            process_file(plus_input, plus_output)

    logger.info("")
    logger.info("WordNet enrichment complete")


if __name__ == '__main__':
    main()
