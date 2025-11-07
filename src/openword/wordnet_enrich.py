#!/usr/bin/env python3
"""
wordnet_enrich.py — Enrich entries with WordNet data (concreteness, POS backfill).

Reads:
  - data/intermediate/{core,plus}/*_entries.jsonl

Outputs:
  - data/intermediate/{core,plus}/*_entries_enriched.jsonl

Enrichment:
  - Adds 'concreteness' field for nouns: concrete|abstract|mixed
  - Backfills POS tags where confident and missing
  - Uses NLTK's WordNet interface
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


def get_concreteness(word: str) -> Optional[str]:
    """
    Determine concreteness for a noun using WordNet.

    Returns: 'concrete', 'abstract', 'mixed', or None
    """
    synsets = wn.synsets(word, pos=wn.NOUN)

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
    """Get POS tags from WordNet for a word."""
    pos_tags = set()

    # Check each WordNet POS
    if wn.synsets(word, pos=wn.NOUN):
        pos_tags.add('noun')
    if wn.synsets(word, pos=wn.VERB):
        pos_tags.add('verb')
    if wn.synsets(word, pos=wn.ADJ):
        pos_tags.add('adjective')
    if wn.synsets(word, pos=wn.ADV):
        pos_tags.add('adverb')

    return sorted(pos_tags)


def enrich_entry(entry: dict) -> dict:
    """Enrich a single entry with WordNet data."""
    word = entry['word']

    # Skip multi-word phrases (WordNet doesn't handle them well)
    if entry.get('is_phrase', False):
        return entry

    # Backfill POS if empty
    if not entry.get('pos'):
        wn_pos = get_wordnet_pos(word)
        if wn_pos:
            entry['pos'] = wn_pos

    # Add concreteness for nouns
    if 'noun' in entry.get('pos', []):
        concreteness = get_concreteness(word)
        if concreteness:
            entry['concreteness'] = concreteness

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

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                logger.info(f"  Processed {line_num:,} entries...")

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
            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in entries:
            line = orjson.dumps(entry) + b'\n'
            f.write(line)

    logger.info(f"  ✓ Enriched {len(entries):,} entries")
    logger.info(f"    Concreteness added: {enriched_count:,}")
    logger.info(f"    POS backfilled: {pos_backfilled:,}")
    logger.info(f"  → {output_path}")


def main():
    """Main enrichment pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate"

    logger.info("=" * 60)
    logger.info("PHASE 7: WordNet enrichment")
    logger.info("=" * 60)

    # Ensure WordNet data is available
    ensure_wordnet_data()

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
    logger.info("✓ WordNet enrichment complete")


if __name__ == '__main__':
    main()
