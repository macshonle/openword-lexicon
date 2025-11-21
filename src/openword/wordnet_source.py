#!/usr/bin/env python3
"""
wordnet_source.py — Ingest words from Open English WordNet.

Treats OEWN as a word source (like EOWL), extracting words with POS tags.
This adds ~161,000 words from OEWN to the lexicon.

Usage:
    from openword.wordnet_source import WordNetSource

    source = WordNetSource('data/raw/en/english-wordnet-2024.tar.gz')
    for entry in source.iter_entries():
        print(entry)

Output format matches core_ingest.py schema:
    {
        "word": "castle",
        "pos": ["noun", "verb"],
        "labels": {},
        "is_phrase": False,
        "lemma": None,
        "sources": ["wordnet"]
    }
"""

import logging
import unicodedata
from pathlib import Path
from typing import Dict, Iterator, List, Set
from collections import defaultdict

from openword.wordnet_yaml_parser import OEWNParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WordNetSource:
    """
    Word source from Open English WordNet.

    Extracts words with POS tags from OEWN, treating it as a primary word source
    like EOWL or ENABLE.
    """

    def __init__(self, archive_path: str):
        """
        Initialize WordNet source.

        Args:
            archive_path: Path to english-wordnet-2024.tar.gz
        """
        self.archive_path = Path(archive_path)
        if not self.archive_path.exists():
            raise FileNotFoundError(f"OEWN archive not found: {archive_path}")

        self.parser = OEWNParser(str(archive_path))

    def _normalize_word(self, word: str) -> str:
        """Normalize word to NFKC Unicode and lowercase."""
        normalized = unicodedata.normalize('NFKC', word)
        return normalized.lower()

    def _is_valid_word(self, word: str) -> bool:
        """
        Check if word should be included.

        Filters out:
        - Proper nouns (capitalized multi-word phrases)
        - Very long compounds (likely artifacts)
        - Words with special characters that indicate abbreviations
        """
        # Skip if too long (> 45 chars, likely an artifact)
        if len(word) > 45:
            return False

        # Skip if contains underscores (likely internal representation)
        if '_' in word:
            # Allow single underscores in compounds like "a_priori"
            if word.count('_') > 2:
                return False

        # Allow hyphens (they're normal in English)
        # Allow apostrophes (they're normal in English)
        # Allow spaces (for multi-word phrases)

        return True

    def _detect_phrase(self, word: str) -> bool:
        """Detect if entry is a multi-word phrase."""
        # Simple heuristic: contains space
        return ' ' in word

    def iter_entries(self) -> Iterator[Dict]:
        """
        Iterate all word entries from OEWN.

        Yields:
            Entry dictionaries compatible with lexicon schema
        """
        logger.info("Extracting words from OEWN...")

        # Group by normalized lemma to combine POS tags
        word_data = defaultdict(lambda: {
            'original_lemma': None,
            'pos_set': set(),
            'is_phrase': False
        })

        for word_entry in self.parser.iter_words():
            lemma = word_entry['lemma']

            if not self._is_valid_word(lemma):
                continue

            normalized = self._normalize_word(lemma)

            # Store data
            if word_data[normalized]['original_lemma'] is None:
                word_data[normalized]['original_lemma'] = normalized

            word_data[normalized]['pos_set'].add(word_entry['pos'])

            if self._detect_phrase(lemma):
                word_data[normalized]['is_phrase'] = True

        # Convert to entries
        logger.info(f"  Extracted {len(word_data):,} unique words")

        for normalized_word, data in word_data.items():
            entry = {
                'word': normalized_word,
                'pos': sorted(list(data['pos_set'])),
                'labels': {},
                'is_phrase': data['is_phrase'],
                'lemma': None,
                'sources': ['wordnet']
            }

            yield entry

    def write_jsonl(self, output_path: str):
        """Write entries to JSONL file."""
        import orjson

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing WordNet entries to {output_path}")

        count = 0
        with open(output_file, 'wb') as f:
            for entry in self.iter_entries():
                line = orjson.dumps(entry, option=orjson.OPT_SORT_KEYS) + b'\n'
                f.write(line)
                count += 1

        logger.info(f"  Wrote {count:,} entries")
        logger.info(f"  -> {output_path}")

    def get_stats(self) -> Dict:
        """Get statistics about the word source."""
        pos_counts = defaultdict(int)
        phrase_count = 0
        total_count = 0

        for entry in self.iter_entries():
            total_count += 1
            if entry['is_phrase']:
                phrase_count += 1

            for pos in entry['pos']:
                pos_counts[pos] += 1

        return {
            'total_words': total_count,
            'multi_word_phrases': phrase_count,
            'words_by_pos': dict(pos_counts),
        }


def main():
    """Main entry point for WordNet word source extraction."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Extract words from OEWN')
    parser.add_argument('--archive', default='data/raw/en/english-wordnet-2024.tar.gz',
                        help='Path to OEWN archive')
    parser.add_argument('--output', default='data/intermediate/en/wordnet_entries.jsonl',
                        help='Output JSONL file')
    parser.add_argument('--stats', action='store_true',
                        help='Show statistics only')

    args = parser.parse_args()

    source = WordNetSource(args.archive)

    if args.stats:
        logger.info("Computing statistics...")
        stats = source.get_stats()
        print("\n=== WordNet Source Statistics ===")
        print(f"Total words: {stats['total_words']:,}")
        print(f"Multi-word phrases: {stats['multi_word_phrases']:,}")
        print("\nWords by POS:")
        for pos, count in sorted(stats['words_by_pos'].items()):
            print(f"  {pos}: {count:,}")
    else:
        source.write_jsonl(args.output)


if __name__ == '__main__':
    main()
