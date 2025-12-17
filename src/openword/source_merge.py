#!/usr/bin/env python3
"""
source_merge.py — Merge multiple word sources into a unified lexemes file.

This script combines words from multiple sources (Wiktionary, EOWL, WordNet)
into a single lexemes file with source tracking. This enables:
  - Runtime filtering by source selection
  - License-aware word list generation
  - Interactive word count estimates in the Word List Builder

Usage:
  uv run python src/openword/source_merge.py \
      --wikt-lexemes LEXEMES.jsonl \
      --eowl EOWL.txt \
      --wordnet WORDNET.tar.gz \
      --output OUTPUT.jsonl

Output format (lexeme entries):
  {
    "id": "castle",
    "sources": ["eowl", "wikt", "wordnet"],
    "license_sources": {"CC-BY-SA-4.0": ["wikt"], "UKACD": ["eowl"], "CC-BY-4.0": ["wordnet"]},
    "sense_offset": 0,
    "sense_length": 3,
    ...
  }

Words from secondary sources only (not in Wiktionary) get:
  - sense_offset: 0, sense_length: 0 (no Wiktionary senses available)
  - sources: list of sources that contain the word
  - license_sources: mapping of applicable licenses
"""

import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple

import orjson

from openword.progress_display import ProgressDisplay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# License mappings for each source
SOURCE_LICENSES = {
    "wikt": "CC-BY-SA-4.0",
    "eowl": "UKACD",
    "wordnet": "CC-BY-4.0",
    "brysbaert": "Brysbaert-Research",
}


def normalize_word(word: str) -> str:
    """Normalize word for comparison (NFKC, lowercase)."""
    return unicodedata.normalize("NFKC", word.lower().strip())


def load_eowl(eowl_path: Path) -> Set[str]:
    """Load EOWL word list."""
    words = set()

    if not eowl_path.exists():
        logger.warning(f"EOWL file not found: {eowl_path}")
        return words

    logger.info(f"Loading EOWL from {eowl_path}")

    with open(eowl_path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word:
                words.add(normalize_word(word))

    logger.info(f"  -> Loaded {len(words):,} EOWL words")
    return words


def load_wordnet(wordnet_path: Path) -> Tuple[Set[str], Dict[str, List[str]]]:
    """
    Load WordNet words and their lexnames from the OEWN tarball.

    Returns:
        Tuple of (words set, lexnames dict mapping word -> list of lexnames)
    """
    words = set()
    word_lexnames: Dict[str, List[str]] = {}

    if not wordnet_path.exists():
        logger.warning(f"WordNet archive not found: {wordnet_path}")
        return words, word_lexnames

    logger.info(f"Loading WordNet from {wordnet_path}")

    try:
        from openword.wordnet_yaml_parser import OEWNParser
        parser = OEWNParser(str(wordnet_path))

        # Iterate all words from WordNet
        for word_entry in parser.iter_words():
            lemma = word_entry.get("lemma", "")
            if lemma:
                words.add(normalize_word(lemma))

        # Build lexnames mapping (this loads synsets with lexname tracking)
        raw_lexnames = parser.build_word_lexnames()

        # Convert set values to sorted lists for JSON serialization
        for word, lexname_set in raw_lexnames.items():
            word_lexnames[word] = sorted(lexname_set)

    except ImportError:
        logger.error("WordNet YAML parser not available")
        return words, word_lexnames
    except Exception as e:
        logger.error(f"Error loading WordNet: {e}")
        return words, word_lexnames

    logger.info(f"  -> Loaded {len(words):,} WordNet words with {len(word_lexnames):,} lexname mappings")
    return words, word_lexnames


def load_wikt_lexemes(lexeme_path: Path) -> Tuple[Dict[str, dict], Dict[str, List[str]]]:
    """Load Wiktionary lexeme entries into a dictionary.

    Returns:
        Tuple of:
        - entries: Dict mapping original word (with case) -> entry
        - norm_to_words: Dict mapping normalized word -> list of original words
          (for matching against case-insensitive secondary sources)
    """
    entries = {}
    norm_to_words: Dict[str, List[str]] = {}  # normalized -> [original words]

    if not lexeme_path.exists():
        logger.error(f"Wiktionary lexeme file not found: {lexeme_path}")
        return entries, norm_to_words

    logger.info(f"Loading Wiktionary lexemes from {lexeme_path}")

    with ProgressDisplay("Loading lexemes", update_interval=10000) as progress:
        with open(lexeme_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry["id"]  # Preserve original case
                    norm = normalize_word(word)

                    # Initialize sources if not present
                    if "sources" not in entry:
                        entry["sources"] = ["wikt"]
                    if "license_sources" not in entry:
                        entry["license_sources"] = {"CC-BY-SA-4.0": ["wikt"]}

                    entries[word] = entry

                    # Build reverse index for secondary source matching
                    if norm not in norm_to_words:
                        norm_to_words[norm] = []
                    if word not in norm_to_words[norm]:
                        norm_to_words[norm].append(word)

                    progress.update(Lines=line_num, Entries=len(entries))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Line {line_num}: {e}")
                    continue

    logger.info(f"  -> Loaded {len(entries):,} Wiktionary entries ({len(norm_to_words):,} unique normalized forms)")
    return entries, norm_to_words


def add_source_to_entry(entry: dict, source: str) -> dict:
    """Add a source to an entry's source tracking."""
    # Add to sources list
    sources = entry.get("sources", [])
    if source not in sources:
        entry["sources"] = sorted(sources + [source])

    # Add to license_sources
    license_key = SOURCE_LICENSES.get(source)
    if license_key:
        license_sources = entry.get("license_sources", {})
        if license_key not in license_sources:
            license_sources[license_key] = [source]
        elif source not in license_sources[license_key]:
            license_sources[license_key] = sorted(license_sources[license_key] + [source])
        entry["license_sources"] = license_sources

    return entry


def create_secondary_entry(word: str, sources: list, lexnames: Optional[List[str]] = None) -> dict:
    """Create a lexeme entry for a word that only exists in secondary sources (not Wiktionary).

    Args:
        word: The word
        sources: List of sources that contain this word (e.g., ['eowl', 'wordnet'])
        lexnames: Optional list of WordNet lexnames (semantic categories)

    Returns:
        Lexeme entry with source tracking and no Wiktionary senses
    """
    license_sources = {}
    for source in sources:
        license_key = SOURCE_LICENSES.get(source)
        if license_key:
            if license_key not in license_sources:
                license_sources[license_key] = []
            license_sources[license_key].append(source)

    # Sort sources within each license
    for license_key in license_sources:
        license_sources[license_key] = sorted(license_sources[license_key])

    entry = {
        "id": word,
        "sources": sorted(sources),
        "license_sources": license_sources,
        "sense_offset": 0,
        "sense_length": 0,
        "sense_count": 0,
        "wc": len(word.split()),
    }

    # Add lexnames if available
    if lexnames:
        entry["lexnames"] = lexnames

    return entry


def merge_sources(
    wikt_entries: Dict[str, dict],
    norm_to_words: Dict[str, List[str]],
    eowl_words: Set[str],
    wordnet_words: Set[str],
    word_lexnames: Dict[str, List[str]],
    output_path: Path
):
    """
    Merge Wiktionary entries with secondary sources (EOWL, WordNet).

    - Words in Wiktionary: Add secondary source tags where applicable
    - Words only in secondary sources: Create new entries with no Wiktionary senses
    - Adds WordNet lexnames (semantic categories) to words in WordNet
    - Tracks source combinations for statistics

    Secondary sources (EOWL, WordNet) are matched case-insensitively using
    norm_to_words index. If "sat" is in EOWL, all Wiktionary case variants
    (sat, Sat, SAT) will get the 'eowl' source tag.
    """
    logger.info("Merging sources...")

    # Track statistics per source
    stats = {
        "wikt_only": 0,
        "eowl_only": 0,
        "wordnet_only": 0,
        "wikt_eowl": 0,
        "wikt_wordnet": 0,
        "eowl_wordnet": 0,
        "all_three": 0,
        "with_lexnames": 0,
    }

    # Track words not in Wiktionary that are in secondary sources
    # These need new entries created
    secondary_only: Dict[str, list] = {}  # normalized word -> list of sources

    # Process EOWL words (case-insensitive matching)
    if eowl_words:
        logger.info(f"  Processing {len(eowl_words):,} EOWL words...")
        for eowl_word in eowl_words:
            # eowl_word is already normalized (lowercase)
            if eowl_word in norm_to_words:
                # Add 'eowl' source to ALL case variants in Wiktionary
                for orig_word in norm_to_words[eowl_word]:
                    wikt_entries[orig_word] = add_source_to_entry(wikt_entries[orig_word], "eowl")
            else:
                if eowl_word not in secondary_only:
                    secondary_only[eowl_word] = []
                secondary_only[eowl_word].append("eowl")

    # Process WordNet words (and add lexnames) - case-insensitive matching
    if wordnet_words:
        logger.info(f"  Processing {len(wordnet_words):,} WordNet words...")
        for wn_word in wordnet_words:
            # wn_word is already normalized (lowercase)
            if wn_word in norm_to_words:
                # Add 'wordnet' source and lexnames to ALL case variants
                for orig_word in norm_to_words[wn_word]:
                    wikt_entries[orig_word] = add_source_to_entry(wikt_entries[orig_word], "wordnet")
                    # Add lexnames to existing entry
                    if wn_word in word_lexnames:
                        wikt_entries[orig_word]["lexnames"] = word_lexnames[wn_word]
            else:
                if wn_word not in secondary_only:
                    secondary_only[wn_word] = []
                secondary_only[wn_word].append("wordnet")

    # Create entries for words only in secondary sources
    if secondary_only:
        logger.info(f"  Creating {len(secondary_only):,} secondary-only entries...")
        for word, sources in secondary_only.items():
            lexnames = word_lexnames.get(word)
            wikt_entries[word] = create_secondary_entry(word, sources, lexnames)

    # Calculate statistics by examining source combinations
    for entry in wikt_entries.values():
        sources = set(entry.get("sources", []))
        has_wikt = "wikt" in sources
        has_eowl = "eowl" in sources
        has_wordnet = "wordnet" in sources

        if has_wikt and has_eowl and has_wordnet:
            stats["all_three"] += 1
        elif has_wikt and has_eowl:
            stats["wikt_eowl"] += 1
        elif has_wikt and has_wordnet:
            stats["wikt_wordnet"] += 1
        elif has_eowl and has_wordnet:
            stats["eowl_wordnet"] += 1
        elif has_wikt:
            stats["wikt_only"] += 1
        elif has_eowl:
            stats["eowl_only"] += 1
        elif has_wordnet:
            stats["wordnet_only"] += 1

        # Count entries with lexnames
        if entry.get("lexnames"):
            stats["with_lexnames"] += 1

    # Log statistics
    logger.info("Source statistics:")
    logger.info(f"  Wiktionary only:        {stats['wikt_only']:,}")
    if eowl_words:
        logger.info(f"  EOWL only:              {stats['eowl_only']:,}")
        logger.info(f"  Wiktionary + EOWL:      {stats['wikt_eowl']:,}")
    if wordnet_words:
        logger.info(f"  WordNet only:           {stats['wordnet_only']:,}")
        logger.info(f"  Wiktionary + WordNet:   {stats['wikt_wordnet']:,}")
    if eowl_words and wordnet_words:
        logger.info(f"  EOWL + WordNet:         {stats['eowl_wordnet']:,}")
        logger.info(f"  All three sources:      {stats['all_three']:,}")
    logger.info(f"  Total entries:          {len(wikt_entries):,}")
    if word_lexnames:
        logger.info(f"  With lexnames:          {stats['with_lexnames']:,}")

    # Sort entries by word and write output
    logger.info("Writing merged lexeme file...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_words = sorted(wikt_entries.keys())

    with open(output_path, "wb") as f:
        for word in sorted_words:
            entry = wikt_entries[word]
            line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b"\n"
            f.write(line)

    logger.info(f"  -> {output_path}")

    stats["total"] = len(wikt_entries)
    return stats


def main():
    """Main merge pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge multiple word sources into unified lexemes file"
    )
    parser.add_argument("--wikt-lexemes", type=Path, required=True,
                        help="Wiktionary lexemes JSONL file (base)")
    parser.add_argument("--eowl", type=Path,
                        help="EOWL word list file (optional)")
    parser.add_argument("--wordnet", type=Path,
                        help="WordNet tarball archive (optional)")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output merged JSONL file")
    args = parser.parse_args()

    logger.info("Source merge")
    logger.info(f"  Wiktionary: {args.wikt_lexemes}")
    if args.eowl:
        logger.info(f"  EOWL: {args.eowl}")
    if args.wordnet:
        logger.info(f"  WordNet: {args.wordnet}")
    logger.info(f"  Output: {args.output}")
    logger.info("")

    # Load Wiktionary lexemes (base)
    # Returns entries dict and norm_to_words index for case-insensitive secondary source matching
    wikt_entries, norm_to_words = load_wikt_lexemes(args.wikt_lexemes)
    if not wikt_entries:
        logger.error("No Wiktionary entries loaded")
        sys.exit(1)

    # Load EOWL words (optional)
    eowl_words = set()
    if args.eowl and args.eowl.exists():
        eowl_words = load_eowl(args.eowl)

    # Load WordNet words and lexnames (optional)
    wordnet_words = set()
    word_lexnames: Dict[str, List[str]] = {}
    if args.wordnet and args.wordnet.exists():
        wordnet_words, word_lexnames = load_wordnet(args.wordnet)

    # Merge all sources
    stats = merge_sources(wikt_entries, norm_to_words, eowl_words, wordnet_words, word_lexnames, args.output)

    logger.info("")
    logger.info("Source merge complete")
    logger.info(f"  Total entries: {stats['total']:,}")


if __name__ == "__main__":
    main()
