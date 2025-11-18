#!/usr/bin/env python3
"""
wikt_ingest.py — Parse Wiktionary extractions and normalize to schema.

Reads:
  - data/intermediate/en/wikt.jsonl (from custom scanner parser)

Outputs:
  - data/intermediate/en/wikt_entries.jsonl

Maps scanner parser output to our schema with:
  - POS tags
  - Region labels (en-GB, en-US, etc.)
  - Register labels (vulgar, offensive, archaic, etc.)
  - Multi-word phrases (word_count > 1)
  - Lemmatization info
  - Morphology data (derivation, compounds, affixes)
  - Syllable counts

Note: wiktextract was initially considered but replaced with a custom
scanner parser (wiktionary_scanner_parser.py) for better performance
and control. This module processes output from that custom parser.
"""

import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Optional

import orjson

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# POS tag mapping from Wiktextract to our schema
POS_MAP = {
    'noun': 'noun',
    'verb': 'verb',
    'adj': 'adjective',
    'adjective': 'adjective',
    'adv': 'adverb',
    'adverb': 'adverb',
    'pron': 'pronoun',
    'pronoun': 'pronoun',
    'prep': 'preposition',
    'preposition': 'preposition',
    'conj': 'conjunction',
    'conjunction': 'conjunction',
    'intj': 'interjection',
    'interjection': 'interjection',
    'det': 'determiner',
    'determiner': 'determiner',
    'particle': 'particle',
    'aux': 'auxiliary',
    'auxiliary': 'auxiliary',
}


# Tag/label mapping from Wiktextract to our schema
REGISTER_MAP = {
    'vulgar': 'vulgar',
    'offensive': 'offensive',
    'derogatory': 'derogatory',
    'slang': 'slang',
    'colloquial': 'colloquial',
    'informal': 'informal',
    'formal': 'formal',
    'euphemism': 'euphemistic',
    'euphemistic': 'euphemistic',
    'humorous': 'humorous',
    'literary': 'literary',
}

TEMPORAL_MAP = {
    'archaic': 'archaic',
    'obsolete': 'obsolete',
    'dated': 'dated',
    'historical': 'historical',
}

DOMAIN_MAP = {
    'medicine': 'medical',
    'medical': 'medical',
    'law': 'legal',
    'legal': 'legal',
    'technical': 'technical',
    'science': 'scientific',
    'scientific': 'scientific',
    'military': 'military',
    'nautical': 'nautical',
    'botany': 'botanical',
    'botanical': 'botanical',
    'zoology': 'zoological',
    'zoological': 'zoological',
    'computing': 'computing',
    'mathematics': 'mathematics',
    'math': 'mathematics',
    'music': 'music',
    'art': 'art',
    'religion': 'religion',
    'religious': 'religion',
    'culinary': 'culinary',
    'cooking': 'culinary',
    'sports': 'sports',
    'sport': 'sports',
    'business': 'business',
    'finance': 'finance',
    'financial': 'finance',
}

# Region mapping
REGION_MAP = {
    'British': 'en-GB',
    'UK': 'en-GB',
    'US': 'en-US',
    'American': 'en-US',
    'Canadian': 'en-CA',
    'Australia': 'en-AU',
    'Australian': 'en-AU',
    'New Zealand': 'en-NZ',
    'Ireland': 'en-IE',
    'Irish': 'en-IE',
    'South Africa': 'en-ZA',
    'India': 'en-IN',
    'Indian': 'en-IN',
}


def normalize_word(word: str) -> str:
    """Apply Unicode NFKC normalization."""
    word = word.strip()
    word = unicodedata.normalize('NFKC', word)
    word = word.lower()
    return word


def extract_pos(wikt_entry: dict) -> List[str]:
    """Extract POS tags from scanner parser entry."""
    pos_list = []
    pos_raw = wikt_entry.get('pos', '')

    if isinstance(pos_raw, list):
        for p in pos_raw:
            if p.lower() in POS_MAP:
                pos_list.append(POS_MAP[p.lower()])
    elif isinstance(pos_raw, str) and pos_raw:
        if pos_raw.lower() in POS_MAP:
            pos_list.append(POS_MAP[pos_raw.lower()])

    return sorted(set(pos_list))


def extract_labels(wikt_entry: dict) -> dict:
    """Extract and categorize labels from scanner parser entry.

    Scanner parser outputs labels in a 'labels' dict with keys: register, region, temporal, domain.
    Falls back to raw tags/topics format for compatibility with legacy data.
    """

    # Primary: scanner parser format (pre-extracted labels)
    if 'labels' in wikt_entry and isinstance(wikt_entry['labels'], dict):
        extracted_labels = {}
        for key in ['register', 'region', 'temporal', 'domain']:
            if key in wikt_entry['labels']:
                values = wikt_entry['labels'][key]
                if isinstance(values, list) and values:
                    # Deduplicate and sort
                    extracted_labels[key] = sorted(set(values))
        return extracted_labels

    # Fallback: raw tags/topics format (legacy compatibility)
    labels = {
        'register': [],
        'region': [],
        'temporal': [],
        'domain': []
    }

    # Tags/labels can be in various fields
    tags = wikt_entry.get('tags', [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []

    # Also check 'topics' field for domain labels
    topics = wikt_entry.get('topics', [])
    if not isinstance(topics, list):
        topics = [topics] if topics else []

    # Process all tags
    for tag in tags:
        tag_lower = str(tag).lower()

        # Check register
        if tag_lower in REGISTER_MAP:
            labels['register'].append(REGISTER_MAP[tag_lower])

        # Check temporal
        if tag_lower in TEMPORAL_MAP:
            labels['temporal'].append(TEMPORAL_MAP[tag_lower])

        # Check region
        for region_key, region_code in REGION_MAP.items():
            if region_key.lower() in tag_lower:
                labels['region'].append(region_code)
                break

        # Check domain
        if tag_lower in DOMAIN_MAP:
            labels['domain'].append(DOMAIN_MAP[tag_lower])

    # Process topics for domain
    for topic in topics:
        topic_lower = str(topic).lower()
        if topic_lower in DOMAIN_MAP:
            labels['domain'].append(DOMAIN_MAP[topic_lower])

    # Deduplicate and sort
    for key in labels:
        labels[key] = sorted(set(labels[key]))

    # Remove empty label categories
    labels = {k: v for k, v in labels.items() if v}

    return labels


def process_wikt_entry(wikt_entry: dict) -> Optional[dict]:
    """Process a single scanner parser entry and map to our schema."""
    # Get the word
    word = wikt_entry.get('word', '').strip()
    if not word:
        return None

    # Skip non-English entries
    lang = wikt_entry.get('lang', '').lower()
    if lang and lang != 'english':
        return None

    # Normalize
    normalized_word = normalize_word(word)
    if not normalized_word:
        return None

    # Extract components
    pos = extract_pos(wikt_entry)
    labels = extract_labels(wikt_entry)
    word_count = len(normalized_word.split())

    # Check for lemma/form_of
    lemma = None
    form_of = wikt_entry.get('form_of')
    if form_of:
        if isinstance(form_of, list) and form_of:
            lemma = normalize_word(str(form_of[0]))
        elif isinstance(form_of, str):
            lemma = normalize_word(form_of)

    # Get is_proper_noun flag from scanner parser (if present)
    is_proper_noun = wikt_entry.get('is_proper_noun', False)

    # Create entry
    entry = {
        'word': normalized_word,
        'pos': pos,
        'labels': labels,
        'word_count': word_count,
        'lemma': lemma,
        'sources': ['wikt'],
        'is_proper_noun': is_proper_noun
    }

    # Pass through syllables field if present (from scanner parser)
    if 'syllables' in wikt_entry:
        entry['syllables'] = wikt_entry['syllables']

    # Pass through morphology field if present (from scanner parser)
    if 'morphology' in wikt_entry:
        entry['morphology'] = wikt_entry['morphology']

    return entry


def read_wiktionary_jsonl(filepath: Path) -> Dict[str, dict]:
    """Read scanner parser JSONL output and merge multiple senses per word."""
    entries = {}

    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return entries

    logger.info(f"Reading Wiktionary scanner parser data from {filepath}")

    with ProgressDisplay(f"Processing {filepath.name}", update_interval=1000) as progress:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    wikt_entry = json.loads(line)
                    entry = process_wikt_entry(wikt_entry)

                    if entry:
                        word = entry['word']

                        # Merge if word already exists
                        if word in entries:
                            # Union POS
                            entries[word]['pos'] = sorted(set(
                                entries[word]['pos'] + entry['pos']
                            ))

                            # Union labels
                            for label_cat in ['register', 'region', 'temporal', 'domain']:
                                if label_cat in entry['labels']:
                                    existing = entries[word]['labels'].get(label_cat, [])
                                    entries[word]['labels'][label_cat] = sorted(set(
                                        existing + entry['labels'][label_cat]
                                    ))

                            # Keep lemma if present
                            if entry['lemma'] and not entries[word]['lemma']:
                                entries[word]['lemma'] = entry['lemma']

                            # Keep syllables if present
                            if entry.get('syllables') and not entries[word].get('syllables'):
                                entries[word]['syllables'] = entry['syllables']

                            # Keep morphology if present
                            if entry.get('morphology') and not entries[word].get('morphology'):
                                entries[word]['morphology'] = entry['morphology']

                            # Track proper noun usage
                            # If any entry is proper noun, mark has_proper_usage
                            if entry.get('is_proper_noun'):
                                entries[word]['has_proper_usage'] = True
                            # If any entry is NOT proper noun, mark has_common_usage
                            if not entry.get('is_proper_noun'):
                                entries[word]['has_common_usage'] = True

                            # Keep is_proper_noun as True if any entry is proper
                            entries[word]['is_proper_noun'] = (
                                entries[word].get('is_proper_noun', False) or
                                entry.get('is_proper_noun', False)
                            )
                        else:
                            # New entry - set usage flags based on is_proper_noun
                            entry['has_proper_usage'] = entry.get('is_proper_noun', False)
                            entry['has_common_usage'] = not entry.get('is_proper_noun', False)
                            entries[word] = entry

                    progress.update(Lines=line_num, Words=len(entries))

                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue

    logger.info(f"  -> Loaded {len(entries):,} unique words from scanner parser")
    return entries


def write_jsonl(entries: List[dict], output_path: Path) -> None:
    """Write entries to JSONL format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing {len(entries):,} entries to {output_path}")

    with open(output_path, 'wb') as f:
        for entry in entries:
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
            f.write(line)

    logger.info(f"Written: {output_path}")


def main():
    """Main wiktionary ingestion pipeline."""
    # Paths
    data_root = Path(__file__).parent.parent.parent / "data"
    intermediate_dir = data_root / "intermediate" / "en"
    input_path = intermediate_dir / "wikt.jsonl"
    output_path = intermediate_dir / "wikt_entries.jsonl"

    logger.info("Wiktionary ingestion (English)")

    # Read scanner parser output
    entries_dict = read_wiktionary_jsonl(input_path)

    if not entries_dict:
        logger.error("No entries found. Run wiktionary_scanner_parser.py on the Wiktionary dump first.")
        sys.exit(1)

    # Convert to sorted list
    entries = [entries_dict[word] for word in sorted(entries_dict.keys())]

    # Write output
    write_jsonl(entries, output_path)

    # Stats
    logger.info("")
    logger.info("Statistics:")
    logger.info(f"  Total unique words: {len(entries):,}")
    logger.info(f"  Multi-word phrases: {sum(1 for e in entries if e.get('word_count', 1) > 1):,}")
    logger.info(f"  With POS tags: {sum(1 for e in entries if e['pos']):,}")
    logger.info(f"  With labels: {sum(1 for e in entries if e['labels']):,}")
    logger.info(f"  With lemma: {sum(1 for e in entries if e['lemma']):,}")
    logger.info("")
    logger.info("Wiktionary ingest complete")


if __name__ == '__main__':
    main()
