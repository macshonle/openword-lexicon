#!/usr/bin/env python3
"""
wordnet_yaml_parser.py — Parse Open English WordNet YAML files.

Extracts words, synsets, and relationships from OEWN's YAML source format.
This provides direct access to OEWN data without requiring XML compilation.

Usage:
    from openword.wordnet_yaml_parser import OEWNParser

    parser = OEWNParser('data/raw/en/english-wordnet-2024.tar.gz')

    # Iterate all words
    for word_entry in parser.iter_words():
        print(word_entry['lemma'], word_entry['pos'])

    # Get synset info
    synset = parser.get_synset('00001740-n')
    print(synset['definition'], synset['members'])
"""

import tarfile
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Iterator, Optional, Set
import unicodedata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class OEWNParser:
    """Parser for Open English WordNet YAML files."""

    # POS mappings
    POS_MAP = {
        'n': 'noun',
        'v': 'verb',
        'a': 'adjective',
        's': 'adjective',  # Adjective satellite
        'r': 'adverb',
    }

    # Lexical domains that indicate concreteness
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

    def __init__(self, archive_path: str):
        """
        Initialize parser with path to OEWN tarball.

        Args:
            archive_path: Path to english-wordnet-2024.tar.gz
        """
        self.archive_path = Path(archive_path)
        if not self.archive_path.exists():
            raise FileNotFoundError(f"OEWN archive not found: {archive_path}")

        self._synsets_cache = None
        self._words_cache = None

    def _load_yaml_from_tar(self, filename: str) -> Dict:
        """Load a YAML file from the tarball."""
        with tarfile.open(self.archive_path, 'r:gz') as tar:
            # Try to find the file in the archive
            member_name = None
            for member in tar.getmembers():
                if member.name.endswith(filename):
                    member_name = member.name
                    break

            if member_name is None:
                raise FileNotFoundError(f"File {filename} not found in archive")

            file_obj = tar.extractfile(member_name)
            if file_obj is None:
                raise FileNotFoundError(f"Could not extract {filename}")

            return yaml.safe_load(file_obj)

    def _normalize_word(self, word: str) -> str:
        """Normalize word to NFKC Unicode and lowercase."""
        normalized = unicodedata.normalize('NFKC', word)
        return normalized.lower()

    def load_synsets(self) -> Dict[str, Dict]:
        """
        Load all synsets from YAML files.

        Returns:
            Dictionary mapping synset ID to synset data
        """
        if self._synsets_cache is not None:
            return self._synsets_cache

        logger.info("Loading OEWN synsets from YAML...")
        synsets = {}

        # Synset files
        synset_files = [
            'noun.Tops.yaml',
            'noun.act.yaml',
            'noun.animal.yaml',
            'noun.artifact.yaml',
            'noun.attribute.yaml',
            'noun.body.yaml',
            'noun.cognition.yaml',
            'noun.communication.yaml',
            'noun.event.yaml',
            'noun.feeling.yaml',
            'noun.food.yaml',
            'adj.all.yaml',
            'adj.pert.yaml',
            'adj.ppl.yaml',
            'adv.all.yaml',
        ]

        for synset_file in synset_files:
            try:
                data = self._load_yaml_from_tar(f'src/yaml/{synset_file}')
                synsets.update(data)
                logger.debug(f"  Loaded {len(data)} synsets from {synset_file}")
            except FileNotFoundError:
                logger.warning(f"  Synset file not found: {synset_file}")
                continue
            except Exception as e:
                logger.warning(f"  Error loading {synset_file}: {e}")
                continue

        self._synsets_cache = synsets
        logger.info(f"  Loaded {len(synsets):,} total synsets")
        return synsets

    def load_words(self) -> Dict[str, Dict]:
        """
        Load all word entries from YAML files.

        Returns:
            Dictionary mapping lemma to entry data
        """
        if self._words_cache is not None:
            return self._words_cache

        logger.info("Loading OEWN word entries from YAML...")
        words = {}

        # Entry files (a-z + 0)
        entry_files = [f'entries-{letter}.yaml' for letter in '0abcdefghijklmnopqrstuvwxyz']

        for entry_file in entry_files:
            try:
                data = self._load_yaml_from_tar(f'src/yaml/{entry_file}')
                words.update(data)
                logger.debug(f"  Loaded {len(data)} entries from {entry_file}")
            except FileNotFoundError:
                logger.warning(f"  Entry file not found: {entry_file}")
                continue
            except Exception as e:
                logger.warning(f"  Error loading {entry_file}: {e}")
                continue

        self._words_cache = words
        logger.info(f"  Loaded {len(words):,} total word entries")
        return words

    def get_synset(self, synset_id: str) -> Optional[Dict]:
        """Get synset by ID."""
        synsets = self.load_synsets()
        return synsets.get(synset_id)

    def iter_words(self) -> Iterator[Dict]:
        """
        Iterate all words with their POS and senses.

        Yields:
            Dictionary with keys: lemma, pos, senses, synset_ids
        """
        words = self.load_words()

        for lemma, entry_data in words.items():
            # Each lemma can have multiple POS
            for pos_tag, pos_data in entry_data.items():
                if pos_tag not in self.POS_MAP:
                    continue

                pos_full = self.POS_MAP[pos_tag]
                senses = pos_data.get('sense', [])
                synset_ids = [sense['synset'] for sense in senses if 'synset' in sense]

                yield {
                    'lemma': lemma,
                    'pos': pos_full,
                    'pos_tag': pos_tag,
                    'senses': senses,
                    'synset_ids': synset_ids,
                    'pronunciation': pos_data.get('pronunciation', []),
                }

    def get_word_synsets(self, word: str, pos: Optional[str] = None) -> List[Dict]:
        """
        Get all synsets for a word.

        Args:
            word: The word to look up
            pos: Optional POS filter ('noun', 'verb', etc.)

        Returns:
            List of synset dictionaries
        """
        normalized = self._normalize_word(word)
        words = self.load_words()
        synsets = self.load_synsets()

        result = []

        # Look up word (case-insensitive)
        for lemma, entry_data in words.items():
            if self._normalize_word(lemma) != normalized:
                continue

            # Check each POS
            for pos_tag, pos_data in entry_data.items():
                if pos_tag not in self.POS_MAP:
                    continue

                pos_full = self.POS_MAP[pos_tag]
                if pos and pos != pos_full:
                    continue

                # Get synsets for this POS
                senses = pos_data.get('sense', [])
                for sense in senses:
                    synset_id = sense.get('synset')
                    if synset_id and synset_id in synsets:
                        synset_data = synsets[synset_id].copy()
                        synset_data['id'] = synset_id
                        synset_data['pos'] = pos_full
                        result.append(synset_data)

        return result

    def get_stats(self) -> Dict:
        """Get statistics about the OEWN data."""
        words = self.load_words()
        synsets = self.load_synsets()

        # Count by POS
        pos_counts = {}
        total_senses = 0

        for lemma, entry_data in words.items():
            for pos_tag in entry_data.keys():
                if pos_tag in self.POS_MAP:
                    pos_full = self.POS_MAP[pos_tag]
                    pos_counts[pos_full] = pos_counts.get(pos_full, 0) + 1
                    senses = entry_data[pos_tag].get('sense', [])
                    total_senses += len(senses)

        return {
            'total_words': len(words),
            'total_synsets': len(synsets),
            'total_senses': total_senses,
            'words_by_pos': pos_counts,
        }


def main():
    """Test the parser."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python wordnet_yaml_parser.py <path-to-oewn-tarball>")
        sys.exit(1)

    parser = OEWNParser(sys.argv[1])

    print("=== OEWN Statistics ===")
    stats = parser.get_stats()
    print(f"Total words: {stats['total_words']:,}")
    print(f"Total synsets: {stats['total_synsets']:,}")
    print(f"Total senses: {stats['total_senses']:,}")
    print("\nWords by POS:")
    for pos, count in sorted(stats['words_by_pos'].items()):
        print(f"  {pos}: {count:,}")

    print("\n=== Sample Words ===")
    count = 0
    for word in parser.iter_words():
        print(f"{word['lemma']:20} {word['pos']:10} synsets: {len(word['synset_ids'])}")
        count += 1
        if count >= 20:
            break

    print("\n=== Test: castle ===")
    castle_synsets = parser.get_word_synsets('castle')
    for synset in castle_synsets:
        print(f"  {synset['id']}: {synset.get('definition', ['(no definition)'])[0]}")
        print(f"    Members: {', '.join(synset.get('members', []))}")


if __name__ == '__main__':
    main()
