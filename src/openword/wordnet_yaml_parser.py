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
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class OEWNParser:
    """Parser for Open English WordNet YAML files."""

    # POS mappings (WordNet single-letter → 3-letter codes)
    POS_MAP = {
        "n": "NOU",
        "v": "VRB",
        "a": "ADJ",
        "s": "ADJ",  # Adjective satellite
        "r": "ADV",
    }

    # All synset files organized by POS with their lexnames
    # Each file contains synsets for a specific semantic domain
    SYNSET_FILES = {
        # Nouns (26 categories)
        "noun.Tops.yaml": "noun.Tops",
        "noun.act.yaml": "noun.act",
        "noun.animal.yaml": "noun.animal",
        "noun.artifact.yaml": "noun.artifact",
        "noun.attribute.yaml": "noun.attribute",
        "noun.body.yaml": "noun.body",
        "noun.cognition.yaml": "noun.cognition",
        "noun.communication.yaml": "noun.communication",
        "noun.event.yaml": "noun.event",
        "noun.feeling.yaml": "noun.feeling",
        "noun.food.yaml": "noun.food",
        "noun.group.yaml": "noun.group",
        "noun.location.yaml": "noun.location",
        "noun.motive.yaml": "noun.motive",
        "noun.object.yaml": "noun.object",
        "noun.person.yaml": "noun.person",
        "noun.phenomenon.yaml": "noun.phenomenon",
        "noun.plant.yaml": "noun.plant",
        "noun.possession.yaml": "noun.possession",
        "noun.process.yaml": "noun.process",
        "noun.quantity.yaml": "noun.quantity",
        "noun.relation.yaml": "noun.relation",
        "noun.shape.yaml": "noun.shape",
        "noun.state.yaml": "noun.state",
        "noun.substance.yaml": "noun.substance",
        "noun.time.yaml": "noun.time",
        # Verbs (15 categories)
        "verb.body.yaml": "verb.body",
        "verb.change.yaml": "verb.change",
        "verb.cognition.yaml": "verb.cognition",
        "verb.communication.yaml": "verb.communication",
        "verb.competition.yaml": "verb.competition",
        "verb.consumption.yaml": "verb.consumption",
        "verb.contact.yaml": "verb.contact",
        "verb.creation.yaml": "verb.creation",
        "verb.emotion.yaml": "verb.emotion",
        "verb.motion.yaml": "verb.motion",
        "verb.perception.yaml": "verb.perception",
        "verb.possession.yaml": "verb.possession",
        "verb.social.yaml": "verb.social",
        "verb.stative.yaml": "verb.stative",
        "verb.weather.yaml": "verb.weather",
        # Adjectives (3 categories)
        "adj.all.yaml": "adj.all",
        "adj.pert.yaml": "adj.pert",
        "adj.ppl.yaml": "adj.ppl",
        # Adverbs (1 category)
        "adv.all.yaml": "adv.all",
    }

    # Lexical domains that indicate concreteness (for children's games, etc.)
    CONCRETE_LEXNAMES = {
        "noun.animal", "noun.artifact", "noun.body", "noun.food",
        "noun.location", "noun.object", "noun.person", "noun.plant",
        "noun.shape", "noun.substance",
    }

    ABSTRACT_LEXNAMES = {
        "noun.Tops", "noun.act", "noun.attribute", "noun.cognition",
        "noun.communication", "noun.event", "noun.feeling", "noun.group",
        "noun.motive", "noun.phenomenon", "noun.possession", "noun.process",
        "noun.quantity", "noun.relation", "noun.state", "noun.time",
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
        self._synset_lexnames = None  # Maps synset_id -> lexname
        self._words_cache = None
        self._word_lexnames = None  # Maps normalized_word -> set of lexnames

    def _load_yaml_from_tar(self, filename: str) -> Dict:
        """Load a YAML file from the tarball."""
        with tarfile.open(self.archive_path, "r:gz") as tar:
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
        normalized = unicodedata.normalize("NFKC", word)
        return normalized.lower()

    def load_synsets(self) -> Dict[str, Dict]:
        """
        Load all synsets from YAML files.

        Returns:
            Dictionary mapping synset ID to synset data
        """
        if self._synsets_cache is not None:
            return self._synsets_cache

        logger.info("Loading OEWN synsets from YAML (all 45 categories)...")
        synsets = {}
        synset_lexnames = {}

        for synset_file, lexname in self.SYNSET_FILES.items():
            try:
                data = self._load_yaml_from_tar(f"src/yaml/{synset_file}")
                synsets.update(data)
                # Track lexname for each synset
                for synset_id in data.keys():
                    synset_lexnames[synset_id] = lexname
                logger.debug(f"  Loaded {len(data)} synsets from {synset_file}")
            except FileNotFoundError:
                logger.warning(f"  Synset file not found: {synset_file}")
                continue
            except Exception as e:
                logger.warning(f"  Error loading {synset_file}: {e}")
                continue

        self._synsets_cache = synsets
        self._synset_lexnames = synset_lexnames
        logger.info(f"  Loaded {len(synsets):,} total synsets across {len(self.SYNSET_FILES)} categories")
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
        entry_files = [f"entries-{letter}.yaml" for letter in "0abcdefghijklmnopqrstuvwxyz"]

        for entry_file in entry_files:
            try:
                data = self._load_yaml_from_tar(f"src/yaml/{entry_file}")
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

    def get_synset_lexname(self, synset_id: str) -> Optional[str]:
        """
        Get the lexname (semantic category) for a synset.

        Args:
            synset_id: The synset ID (e.g., '00001740-n')

        Returns:
            Lexname string (e.g., 'noun.animal') or None if not found
        """
        # Ensure synsets are loaded (which also populates lexnames)
        self.load_synsets()
        if self._synset_lexnames is None:
            return None
        return self._synset_lexnames.get(synset_id)

    def get_word_lexnames(self, word: str) -> Set[str]:
        """
        Get all lexnames (semantic categories) for a word.

        A word can belong to multiple categories if it has multiple senses.
        For example, 'bank' might be in noun.artifact (building) and
        noun.object (river bank).

        Args:
            word: The word to look up

        Returns:
            Set of lexname strings
        """
        normalized = self._normalize_word(word)
        words = self.load_words()
        self.load_synsets()  # Ensure lexnames are loaded

        if self._synset_lexnames is None:
            return set()

        lexnames = set()

        # Look up word (case-insensitive)
        for lemma, entry_data in words.items():
            if self._normalize_word(lemma) != normalized:
                continue

            # Check each POS
            for pos_tag, pos_data in entry_data.items():
                if pos_tag not in self.POS_MAP:
                    continue

                # Get synsets for this POS
                senses = pos_data.get("sense", [])
                for sense in senses:
                    synset_id = sense.get("synset")
                    if synset_id and synset_id in self._synset_lexnames:
                        lexnames.add(self._synset_lexnames[synset_id])

        return lexnames

    def build_word_lexnames(self) -> Dict[str, Set[str]]:
        """
        Build a mapping of all words to their lexnames.

        This is efficient for bulk lookups during source merging.

        Returns:
            Dictionary mapping normalized word -> set of lexnames
        """
        if self._word_lexnames is not None:
            return self._word_lexnames

        logger.info("Building word -> lexnames mapping...")
        words = self.load_words()
        self.load_synsets()  # Ensure lexnames are loaded

        if self._synset_lexnames is None:
            return {}

        word_lexnames: Dict[str, Set[str]] = {}

        for lemma, entry_data in words.items():
            normalized = self._normalize_word(lemma)

            # Check each POS
            for pos_tag, pos_data in entry_data.items():
                if pos_tag not in self.POS_MAP:
                    continue

                # Get synsets for this POS
                senses = pos_data.get("sense", [])
                for sense in senses:
                    synset_id = sense.get("synset")
                    if synset_id and synset_id in self._synset_lexnames:
                        if normalized not in word_lexnames:
                            word_lexnames[normalized] = set()
                        word_lexnames[normalized].add(self._synset_lexnames[synset_id])

        self._word_lexnames = word_lexnames
        logger.info(f"  Built lexname mapping for {len(word_lexnames):,} words")
        return word_lexnames

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
                senses = pos_data.get("sense", [])
                synset_ids = [sense["synset"] for sense in senses if "synset" in sense]

                yield {
                    "lemma": lemma,
                    "pos": pos_full,
                    "pos_tag": pos_tag,
                    "senses": senses,
                    "synset_ids": synset_ids,
                    "pronunciation": pos_data.get("pronunciation", []),
                }

    def get_word_synsets(self, word: str, pos: Optional[str] = None) -> List[Dict]:
        """
        Get all synsets for a word.

        Args:
            word: The word to look up
            pos: Optional POS filter ('NOU', 'VRB', etc.)

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
                senses = pos_data.get("sense", [])
                for sense in senses:
                    synset_id = sense.get("synset")
                    if synset_id and synset_id in synsets:
                        synset_data = synsets[synset_id].copy()
                        synset_data["id"] = synset_id
                        synset_data["pos"] = pos_full
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
                    senses = entry_data[pos_tag].get("sense", [])
                    total_senses += len(senses)

        return {
            "total_words": len(words),
            "total_synsets": len(synsets),
            "total_senses": total_senses,
            "words_by_pos": pos_counts,
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
    for pos, count in sorted(stats["words_by_pos"].items()):
        print(f"  {pos}: {count:,}")

    print("\n=== Sample Words ===")
    count = 0
    for word in parser.iter_words():
        print(f"{word['lemma']:20} {word['pos']:10} synsets: {len(word['synset_ids'])}")
        count += 1
        if count >= 20:
            break

    print("\n=== Test: castle ===")
    castle_synsets = parser.get_word_synsets("castle")
    for synset in castle_synsets:
        print(f"  {synset['id']}: {synset.get('definition', ['(no definition)'])[0]}")
        print(f"    Members: {', '.join(synset.get('members', []))}")


if __name__ == "__main__":
    main()
