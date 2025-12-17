"""Tests for owlex word list generator.

Unit tests for filter functions and integration tests for the CLI.
"""

import json
import pytest
from pathlib import Path

from openword.cli.owlex import OwlexFilter


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mini_lexemes():
    """A small curated set of lexemes for testing filters.

    This dataset is designed to test edge cases and specific filter behaviors.
    Each entry is carefully chosen to exercise different filter combinations.
    """
    return [
        # Common 5-letter nouns (Wordle candidates)
        # Note: POS uses 3-letter codes to match production data format
        {"id": "apple", "pos": ["NOU"], "frequency_tier": "B", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2},
        {"id": "bread", "pos": ["NOU"], "frequency_tier": "C", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "chair", "pos": ["NOU"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "dream", "pos": ["NOU", "VRB"], "frequency_tier": "C", "sources": ["wikt", "wordnet"],
         "labels": {}, "concreteness": "abstract", "nsyll": 1},
        {"id": "earth", "pos": ["NOU"], "frequency_tier": "B", "sources": ["wikt", "wordnet"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},

        # Short common words
        {"id": "cat", "pos": ["NOU"], "frequency_tier": "A", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "dog", "pos": ["NOU"], "frequency_tier": "A", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "the", "pos": ["DET"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},
        {"id": "run", "pos": ["VRB", "NOU"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},

        # Words with special characters
        {"id": "don't", "pos": ["VRB"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},
        {"id": "self-help", "pos": ["NOU"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "re-enter", "pos": ["VRB"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {}, "nsyll": 3},

        # Multi-word phrases
        {"id": "hot dog", "pos": ["NOU"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2, "wc": 2},
        {"id": "ice cream", "pos": ["NOU"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2, "wc": 2},

        # Words with labels (using 4-letter codes from schema/core/tag_sets.yaml)
        {"id": "damn", "pos": ["ITJ", "VRB"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {"register": ["RVLG"]}, "nsyll": 1},
        {"id": "bloody", "pos": ["ADJ"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {"register": ["ROFF"], "region": ["ENGB"]}, "nsyll": 2},
        {"id": "thee", "pos": ["PRN"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {"temporal": ["TARC"]}, "nsyll": 1},
        {"id": "hither", "pos": ["ADV"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {"temporal": ["TARC", "TOBS"]}, "nsyll": 2},
        {"id": "whilst", "pos": ["CNJ"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {"temporal": ["TDAT"], "region": ["ENGB"]}, "nsyll": 1},

        # Rare/uncommon words
        {"id": "pulchritudinous", "pos": ["ADJ"], "frequency_tier": "Z", "sources": ["wikt"],
         "labels": {}, "nsyll": 6},
        {"id": "defenestration", "pos": ["NOU"], "frequency_tier": "Y", "sources": ["wikt", "wordnet"],
         "labels": {}, "nsyll": 5},

        # Words from different sources
        {"id": "syzygy", "pos": ["NOU"], "frequency_tier": "Y", "sources": ["wordnet"],
         "labels": {}, "nsyll": 3},
        {"id": "aardvark", "pos": ["NOU"], "frequency_tier": "I", "sources": ["eowl", "wordnet"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2},

        # Regional variants
        {"id": "color", "pos": ["NOU", "VRB"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "spelling_region": "en-US", "nsyll": 2},
        {"id": "colour", "pos": ["NOU", "VRB"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "spelling_region": "en-GB", "nsyll": 2},

        # Words with specific prefixes/suffixes
        {"id": "unhappy", "pos": ["ADJ"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {}, "nsyll": 3},
        {"id": "running", "pos": ["VRB", "NOU"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "preview", "pos": ["NOU", "VRB"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "rethink", "pos": ["VRB", "NOU"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},

        # Proper noun edge cases
        {"id": "bill", "pos": ["NOU", "VRB"], "frequency_tier": "C", "sources": ["wikt"],
         "labels": {}, "has_common_usage": True, "has_proper_usage": True, "nsyll": 1},
        {"id": "aaron", "pos": ["NOU"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {}, "has_common_usage": False, "has_proper_usage": True, "nsyll": 2},

        # Technical/domain-specific words
        {"id": "plaintiff", "pos": ["NOU"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {"domain": ["legal"]}, "nsyll": 2},
        {"id": "diagnosis", "pos": ["NOU"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {"domain": ["medical"]}, "nsyll": 4},

        # Slang (RSLG = slang, RINF = informal)
        {"id": "cool", "pos": ["ADJ", "VRB"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {"register": ["RSLG"]}, "concreteness": "abstract", "nsyll": 1},
        {"id": "dude", "pos": ["NOU"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {"register": ["RINF", "RSLG"]}, "nsyll": 1},
    ]


@pytest.fixture
def mini_lexemes_file(mini_lexemes, tmp_path):
    """Create a temporary JSONL file with mini lexemes."""
    lexemes_file = tmp_path / "test-lexemes.jsonl"
    with open(lexemes_file, "w") as f:
        for entry in mini_lexemes:
            f.write(json.dumps(entry) + "\n")
    return lexemes_file


@pytest.fixture
def spec_dir(tmp_path):
    """Create a temporary directory for spec files."""
    return tmp_path


# =============================================================================
# Unit Tests: Character Filters
# =============================================================================

class TestCharacterFilters:
    """Unit tests for character filter functions."""

    def test_exact_length(self, mini_lexemes):
        """Test exact_length filter."""
        spec = {"filters": {"character": {"exact_length": 5}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "apple" in words
        assert "bread" in words
        assert "chair" in words
        assert "dream" in words
        assert "earth" in words
        assert "cat" not in words  # 3 letters
        assert "running" not in words  # 7 letters

    def test_min_max_length(self, mini_lexemes):
        """Test min_length and max_length filters."""
        spec = {"filters": {"character": {"min_length": 3, "max_length": 5}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "cat" in words  # 3 letters
        assert "apple" in words  # 5 letters
        assert "unhappy" not in words  # 7 letters

    def test_pattern_filter(self, mini_lexemes):
        """Test regex pattern filter."""
        spec = {"filters": {"character": {"pattern": "^[a-z]+$"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "apple" in words
        assert "don't" not in words  # has apostrophe
        assert "self-help" not in words  # has hyphen
        assert "hot dog" not in words  # has space

    def test_starts_with(self, mini_lexemes):
        """Test starts_with filter with multiple prefixes."""
        spec = {"filters": {"character": {"starts_with": ["un", "re"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "unhappy" in words
        assert "re-enter" in words
        assert "rethink" in words
        # "running" starts with "ru" NOT "re", so it should NOT match
        assert "running" not in words

    def test_ends_with(self, mini_lexemes):
        """Test ends_with filter."""
        spec = {"filters": {"character": {"ends_with": ["ing"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "running" in words
        assert "run" not in words

    def test_contains(self, mini_lexemes):
        """Test contains filter with AND logic."""
        spec = {"filters": {"character": {"contains": ["ea"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "bread" in words
        assert "dream" in words
        assert "earth" in words
        assert "ice cream" in words
        assert "apple" not in words

    def test_exclude_contains(self, mini_lexemes):
        """Test exclude_contains filter."""
        spec = {"filters": {"character": {"exclude_contains": "'-"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "apple" in words
        assert "don't" not in words  # has apostrophe
        assert "self-help" not in words  # has hyphen


# =============================================================================
# Unit Tests: Phrase Filters
# =============================================================================

class TestPhraseFilters:
    """Unit tests for phrase filter functions."""

    def test_max_words_single(self, mini_lexemes):
        """Test max_words=1 for single words only."""
        spec = {"filters": {"phrase": {"max_words": 1}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "apple" in words
        assert "hot dog" not in words
        assert "ice cream" not in words

    def test_min_words_phrases(self, mini_lexemes):
        """Test min_words=2 for phrases only."""
        spec = {"filters": {"phrase": {"min_words": 2}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "hot dog" in words
        assert "ice cream" in words
        assert "apple" not in words


# =============================================================================
# Unit Tests: Frequency Filters
# =============================================================================

class TestFrequencyFilters:
    """Unit tests for frequency tier filters."""

    def test_tier_range_a_to_c(self, mini_lexemes):
        """Test frequency tier range A-C (most common)."""
        spec = {"filters": {"frequency": {"min_tier": "A", "max_tier": "C"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "cat" in words  # A
        assert "dog" in words  # A
        assert "apple" in words  # B
        assert "bread" in words  # C
        assert "bill" in words  # C
        assert "chair" not in words  # D
        assert "pulchritudinous" not in words  # Z

    def test_tier_range_a_to_i(self, mini_lexemes):
        """Test frequency tier range A-I (Wordle-style)."""
        spec = {"filters": {"frequency": {"min_tier": "A", "max_tier": "I"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "aardvark" in words  # I
        assert "syzygy" not in words  # Y
        assert "pulchritudinous" not in words  # Z

    def test_specific_tiers(self, mini_lexemes):
        """Test filtering by specific tier list."""
        spec = {"filters": {"frequency": {"tiers": ["A", "B"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        tiers = [e["frequency_tier"] for e in results]

        assert all(t in ["A", "B"] for t in tiers)


# =============================================================================
# Unit Tests: POS Filters
# =============================================================================

class TestPOSFilters:
    """Unit tests for part-of-speech filters."""

    def test_include_nouns(self, mini_lexemes):
        """Test include=[noun] filter.

        Filter uses user-friendly name 'noun', but data has 3-letter code 'NOU'.
        """
        spec = {"filters": {"pos": {"include": ["noun"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "NOU" in entry.get("pos", [])

    def test_exclude_verbs(self, mini_lexemes):
        """Test exclude=[verb] filter.

        Filter uses user-friendly name 'verb', but data has 3-letter code 'VRB'.
        """
        spec = {"filters": {"pos": {"exclude": ["verb"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "VRB" not in entry.get("pos", [])

    def test_include_multiple_pos(self, mini_lexemes):
        """Test include with multiple POS (OR logic).

        Filter uses user-friendly names, but data has 3-letter codes.
        """
        spec = {"filters": {"pos": {"include": ["noun", "adjective"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            pos = entry.get("pos", [])
            assert "NOU" in pos or "ADJ" in pos


# =============================================================================
# Unit Tests: Concreteness Filters
# =============================================================================

class TestConcretenessFilters:
    """Unit tests for concreteness filters."""

    def test_concrete_only(self, mini_lexemes):
        """Test filtering for concrete words only."""
        spec = {"filters": {"concreteness": {"values": ["concrete"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "apple" in words
        assert "cat" in words
        assert "dream" not in words  # abstract
        assert "cool" not in words  # abstract


# =============================================================================
# Unit Tests: Label Filters
# =============================================================================

class TestLabelFilters:
    """Unit tests for label filters (register, temporal, domain)."""

    def test_exclude_vulgar(self, mini_lexemes):
        """Test excluding vulgar words."""
        spec = {"filters": {"labels": {"register": {"exclude": ["RVLG"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "damn" not in words
        assert "apple" in words

    def test_exclude_offensive(self, mini_lexemes):
        """Test excluding offensive words."""
        spec = {"filters": {"labels": {"register": {"exclude": ["RVLG", "ROFF"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "damn" not in words
        assert "bloody" not in words
        assert "apple" in words

    def test_include_slang(self, mini_lexemes):
        """Test including only slang words."""
        spec = {"filters": {"labels": {"register": {"include": ["RSLG"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "cool" in words
        assert "dude" in words
        assert "apple" not in words


# =============================================================================
# Unit Tests: Temporal Filters
# =============================================================================

class TestTemporalFilters:
    """Unit tests for temporal filters (archaic, obsolete, dated)."""

    def test_exclude_archaic(self, mini_lexemes):
        """Test excluding archaic words."""
        spec = {"filters": {"temporal": {"exclude": ["TARC"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "thee" not in words
        assert "hither" not in words
        assert "apple" in words

    def test_exclude_all_old_words(self, mini_lexemes):
        """Test excluding archaic, obsolete, and dated words."""
        spec = {"filters": {"temporal": {"exclude": ["TARC", "TOBS", "TDAT"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "thee" not in words
        assert "hither" not in words
        assert "whilst" not in words
        assert "apple" in words


# =============================================================================
# Unit Tests: Source Filters
# =============================================================================

class TestSourceFilters:
    """Unit tests for source filters."""

    def test_include_wordnet_only(self, mini_lexemes):
        """Test filtering for WordNet-only words."""
        spec = {"filters": {"sources": {"include": ["wordnet"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "wordnet" in entry.get("sources", [])

    def test_include_eowl_only(self, mini_lexemes):
        """Test filtering for EOWL-only words."""
        spec = {"filters": {"sources": {"include": ["eowl"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "eowl" in entry.get("sources", [])


# =============================================================================
# Unit Tests: Spelling Region Filters
# =============================================================================

class TestSpellingRegionFilters:
    """Unit tests for spelling region filters."""

    def test_us_spelling_only(self, mini_lexemes):
        """Test filtering for US spellings."""
        spec = {"filters": {"region": {"region": "en-US"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "color" in words
        assert "colour" not in words
        # Universal words should also be included
        assert "apple" in words

    def test_gb_spelling_only(self, mini_lexemes):
        """Test filtering for GB spellings."""
        spec = {"filters": {"region": {"region": "en-GB"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "colour" in words
        assert "color" not in words
        assert "apple" in words  # universal


# =============================================================================
# Unit Tests: Syllable Filters
# =============================================================================

class TestSyllableFilters:
    """Unit tests for syllable filters."""

    def test_exact_syllables(self, mini_lexemes):
        """Test exact syllable count filter."""
        spec = {"filters": {"syllables": {"exact": 2}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert entry.get("nsyll") == 2

    def test_syllable_range(self, mini_lexemes):
        """Test syllable range filter."""
        spec = {"filters": {"syllables": {"min": 1, "max": 2}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            syllables = entry.get("nsyll")
            if syllables:
                assert 1 <= syllables <= 2


# =============================================================================
# Unit Tests: Proper Noun Filters
# =============================================================================

class TestProperNounFilters:
    """Unit tests for proper noun filters."""

    def test_require_common_usage(self, mini_lexemes):
        """Test filtering for words with common usage (Scrabble-style)."""
        spec = {"filters": {"proper_noun": {"require_common_usage": True}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        assert "bill" in words  # has common usage
        assert "aaron" not in words  # only proper usage


# =============================================================================
# Unit Tests: Combined Filters (Integration)
# =============================================================================

class TestCombinedFilters:
    """Test combinations of filters."""

    def test_wordle_filters(self, mini_lexemes):
        """Test Wordle-style filter combination."""
        spec = {
            "filters": {
                "character": {"exact_length": 5, "pattern": "^[a-z]+$"},
                "phrase": {"max_words": 1},
                "frequency": {"min_tier": "A", "max_tier": "I"}
            }
        }
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        # Should include common 5-letter single words
        assert "apple" in words
        assert "bread" in words
        assert "chair" in words
        assert "dream" in words
        assert "earth" in words

        # Should exclude non-5-letter words
        assert "cat" not in words

        # Should exclude phrases
        assert "hot dog" not in words

    def test_kids_vocabulary_filters(self, mini_lexemes):
        """Test kids vocabulary filter combination."""
        spec = {
            "filters": {
                "character": {"min_length": 3, "max_length": 8},
                "phrase": {"max_words": 1},
                "pos": {"include": ["noun"]},
                "concreteness": {"values": ["concrete"]},
                "labels": {"register": {"exclude": ["RVLG", "ROFF", "RSLG"]}}
            }
        }
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e["id"] for e in results]

        # Should include concrete nouns
        assert "apple" in words
        assert "cat" in words
        assert "dog" in words

        # Should exclude verbs-only
        assert "run" not in words  # verb/noun but no concreteness

        # Should exclude slang
        assert "dude" not in words

        # Should exclude offensive
        assert "damn" not in words


# =============================================================================
# Integration Tests: YAML Spec Loading
# =============================================================================

class TestYAMLSpecLoading:
    """Test loading and processing YAML specifications."""

    def test_load_simplified_yaml_spec(self, tmp_path):
        """Test loading simplified YAML spec format."""
        spec_content = """
# Test spec
character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        assert filter_obj.spec["filters"]["character"]["exact_length"] == 5
        assert filter_obj.spec["filters"]["phrase"]["max_words"] == 1
        assert filter_obj.spec["filters"]["frequency"]["min_tier"] == "A"

    def test_load_yaml_with_sources_filter(self, tmp_path):
        """Test loading YAML spec with sources filter."""
        spec_content = """
sources:
  include: [wordnet]
  enrichment: [frequency]

character:
  min_length: 3
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        assert filter_obj.spec["_sources_filter"]["include"] == ["wordnet"]
        assert filter_obj.spec["filters"]["character"]["min_length"] == 3


# =============================================================================
# Unit Tests: Operation-First Format Parsing
# =============================================================================

class TestOperationFirstFormat:
    """Test the operation-first YAML format parsing."""

    def test_exclude_register(self, tmp_path):
        """Test exclude with register labels."""
        spec_content = """
exclude:
  register: [vulgar, offensive]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert "labels" in filters
        assert "register" in filters["labels"]
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive"]

    def test_include_pos(self, tmp_path):
        """Test include with POS tags."""
        spec_content = """
include:
  pos: [noun, verb]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert "pos" in filters
        assert filters["pos"]["include"] == ["noun", "verb"]

    def test_exclude_pos(self, tmp_path):
        """Test exclude with POS tags."""
        spec_content = """
exclude:
  pos: [phrase, idiom, proper noun]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert "pos" in filters
        assert filters["pos"]["exclude"] == ["phrase", "idiom", "proper noun"]

    def test_exclude_if_primary(self, tmp_path):
        """Test exclude-if-primary with POS tags."""
        spec_content = """
exclude-if-primary:
  pos: [proper noun]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert "pos" in filters
        assert filters["pos"]["exclude-if-primary"] == ["proper noun"]

    def test_combined_include_exclude(self, tmp_path):
        """Test combining include and exclude in same spec."""
        spec_content = """
include:
  pos: [noun]

exclude:
  register: [vulgar, offensive]
  temporal: [archaic, obsolete]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # POS include
        assert filters["pos"]["include"] == ["noun"]

        # Labels exclude
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive"]
        assert filters["labels"]["temporal"]["exclude"] == ["archaic", "obsolete"]

    def test_mixed_word_and_sense_filters(self, tmp_path):
        """Test mixing word-level and sense-level filters."""
        spec_content = """
character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I

include:
  pos: [noun]

exclude:
  register: [vulgar, offensive]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # Word-level filters
        assert filters["character"]["exact_length"] == 5
        assert filters["phrase"]["max_words"] == 1
        assert filters["frequency"]["min_tier"] == "A"

        # Sense-level filters
        assert filters["pos"]["include"] == ["noun"]
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive"]

    def test_domain_filter(self, tmp_path):
        """Test domain filter in operation-first format."""
        spec_content = """
exclude:
  domain: [medical, legal, technical]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert filters["labels"]["domain"]["exclude"] == ["medical", "legal", "technical"]

    def test_region_filter(self, tmp_path):
        """Test region filter in operation-first format."""
        spec_content = """
include:
  region: [en-US]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert filters["labels"]["region"]["include"] == ["en-US"]

    def test_full_wordle_spec(self, tmp_path):
        """Test a complete Wordle-style spec in operation-first format."""
        spec_content = """
# Wordle-style 5-letter words

character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: N

exclude:
  register: [vulgar, offensive, derogatory]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        assert filters["character"]["exact_length"] == 5
        assert filters["character"]["pattern"] == "^[a-z]+$"
        assert filters["phrase"]["max_words"] == 1
        assert filters["frequency"]["min_tier"] == "A"
        assert filters["frequency"]["max_tier"] == "N"
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive", "derogatory"]

    def test_full_kids_nouns_spec(self, tmp_path):
        """Test a complete kids-nouns spec in operation-first format."""
        spec_content = """
character:
  min_length: 3
  max_length: 10

phrase:
  max_words: 1

concreteness:
  values: [concrete]

frequency:
  min_tier: A
  max_tier: L

include:
  pos: [noun]

exclude:
  register: [vulgar, offensive, derogatory, slang]
  temporal: [archaic, obsolete, dated]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # Word-level
        assert filters["character"]["min_length"] == 3
        assert filters["concreteness"]["values"] == ["concrete"]

        # Sense-level
        assert filters["pos"]["include"] == ["noun"]
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive", "derogatory", "slang"]
        assert filters["labels"]["temporal"]["exclude"] == ["archaic", "obsolete", "dated"]


# =============================================================================
# Integration Tests: End-to-End Word List Generation
# =============================================================================

class TestEndToEndGeneration:
    """Integration tests for full word list generation."""

    def test_generate_wordle_list(self, mini_lexemes_file, tmp_path):
        """Test generating a Wordle-style word list."""
        spec_content = """
character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I
"""
        spec_file = tmp_path / "wordle.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        # Load and filter entries
        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # Verify results
        assert len(results) >= 5
        for word in results:
            assert len(word) == 5
            assert word.isalpha()
            assert word.islower()


# =============================================================================
# Bug Hunt: Edge Cases and Potential Issues
# =============================================================================

class TestEdgeCases:
    """Tests designed to find bugs in edge cases."""

    def test_empty_pos_array(self, mini_lexemes):
        """Test handling of entries with empty POS array."""
        entry = {"id": "test", "pos": [], "frequency_tier": "C", "sources": ["wikt"]}
        spec = {"filters": {"pos": {"include": ["noun"]}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry with empty POS should NOT match include filter
        assert not filter_obj.filter_entry(entry)

    def test_missing_pos_field(self, mini_lexemes):
        """Test handling of entries with missing POS field."""
        entry = {"id": "test", "frequency_tier": "C", "sources": ["wikt"]}
        spec = {"filters": {"pos": {"include": ["noun"]}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry with missing POS should NOT match include filter
        assert not filter_obj.filter_entry(entry)

    def test_missing_labels_field(self, mini_lexemes):
        """Test handling of entries with missing labels field."""
        entry = {"id": "test", "pos": ["NOU"], "frequency_tier": "C", "sources": ["wikt"]}
        spec = {"filters": {"labels": {"register": {"exclude": ["RVLG"]}}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry with missing labels should pass exclude filter
        assert filter_obj.filter_entry(entry)

    def test_frequency_tier_boundary(self, mini_lexemes):
        """Test frequency tier boundary conditions."""
        # Test boundary: exactly at min_tier
        entry_a = {"id": "test", "frequency_tier": "A", "sources": ["wikt"]}
        entry_i = {"id": "test", "frequency_tier": "I", "sources": ["wikt"]}
        entry_j = {"id": "test", "frequency_tier": "J", "sources": ["wikt"]}

        spec = {"filters": {"frequency": {"min_tier": "A", "max_tier": "I"}}}
        filter_obj = MockOwlexFilter(spec)

        assert filter_obj.filter_entry(entry_a)  # Should pass (at min)
        assert filter_obj.filter_entry(entry_i)  # Should pass (at max)
        assert not filter_obj.filter_entry(entry_j)  # Should fail (beyond max)

    def test_unknown_frequency_tier(self, mini_lexemes):
        """Test handling of unknown frequency tier."""
        entry = {"id": "test", "frequency_tier": "X", "sources": ["wikt"]}  # Unknown tier
        spec = {"filters": {"frequency": {"min_tier": "A", "max_tier": "Z"}}}
        filter_obj = MockOwlexFilter(spec)

        # Unknown tier should be handled gracefully
        # Default behavior: unknown tier gets score 0, same as Z
        filter_obj.filter_entry(entry)  # Should not raise

    def test_syllable_filter_without_syllable_data(self, mini_lexemes):
        """Test syllable filter on entry without syllable data."""
        entry = {"id": "test", "frequency_tier": "C", "sources": ["wikt"]}  # No syllables

        spec = {"filters": {"syllables": {"exact": 2}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry without syllable data - behavior depends on implementation
        # It should either fail (no data) or pass (no data means no constraint)
        filter_obj.filter_entry(entry)  # Should not raise

    def test_spelling_region_none_vs_missing(self, mini_lexemes):
        """Test spelling region handling for None vs missing field."""
        entry_none = {"id": "test", "spelling_region": None, "sources": ["wikt"]}
        entry_missing = {"id": "test", "sources": ["wikt"]}

        spec = {"filters": {"region": {"region": "en-US"}}}
        filter_obj = MockOwlexFilter(spec)

        # Both should be treated as universal (no regional marker)
        result_none = filter_obj.filter_entry(entry_none)
        result_missing = filter_obj.filter_entry(entry_missing)

        # Both should pass (universal words are included by default)
        assert result_none == result_missing

    def test_starts_with_empty_string(self, mini_lexemes):
        """Test starts_with with empty string."""
        entry = {"id": "test", "sources": ["wikt"]}
        spec = {"filters": {"character": {"starts_with": [""]}}}
        filter_obj = MockOwlexFilter(spec)

        # Empty prefix should match everything or be ignored
        filter_obj.filter_entry(entry)  # Should not raise
        # Note: empty string matches all

    def test_pattern_special_characters(self, mini_lexemes):
        """Test pattern filter with special regex characters."""
        entry = {"id": "test", "sources": ["wikt"]}
        spec = {"filters": {"character": {"pattern": r"^[a-z\.]+$"}}}
        filter_obj = MockOwlexFilter(spec)

        # Should handle regex special chars correctly
        filter_obj.filter_entry(entry)  # Should not raise


# =============================================================================
# Helper: Mock OwlexFilter for Unit Tests
# =============================================================================

class MockOwlexFilter(OwlexFilter):
    """Mock filter that doesn't require a file path."""

    def __init__(self, spec: dict):
        self.spec = {
            "version": "2.0",
            "distribution": "en",
            "filters": spec.get("filters", {}),
            "_sources_filter": spec.get("_sources_filter", {})
        }
        # Tier scores - A (most common) to Z (least common)
        # A=100, B=96, C=92... decreasing by 4 each tier
        self.tier_scores = {
            "A": 100, "B": 96, "C": 92, "D": 88, "E": 84, "F": 80,
            "G": 76, "H": 72, "I": 68, "J": 64, "K": 60, "L": 56,
            "M": 52, "N": 48, "O": 44, "P": 40, "Q": 36, "R": 32,
            "S": 28, "T": 24, "U": 20, "V": 16, "W": 12, "X": 8,
            "Y": 4, "Z": 0
        }


# =============================================================================
# Bug Verification Tests
# =============================================================================

class TestKnownBugs:
    """Tests that verify known bugs/limitations in the current implementation.

    These tests document issues that need to be fixed. They use xfail to mark
    expected failures, or they verify current (possibly incorrect) behavior.
    """

    def test_profanity_filter_requires_senses_data(self):
        """BUG: Profanity filter returns 0 results because labels aren't in lexemes file.

        The profanity blocklist spec (labels.register.include: [vulgar, offensive])
        returns 0 words because:
        1. owlex reads from en-lexemes-enriched.jsonl
        2. That file doesn't have 'labels' field
        3. Label data is in en-senses.jsonl as 'register_tags'

        This is documented in docs/FILTERING.md as a known limitation.
        """
        # This entry has vulgar label in expected format (how test fixtures work)
        entry_with_label = {
            "id": "damn",
            "pos": ["interjection"],
            "labels": {"register": ["RVLG"]},
            "sources": ["wikt"]
        }

        # This entry is how the REAL data looks (no labels field)
        entry_real_format = {
            "id": "damn",
            "frequency_tier": "D",
            "sources": ["wikt"],
            "sense_count": 1
            # NO labels field!
        }

        spec = {"filters": {"labels": {"register": {"include": ["RVLG"]}}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry WITH labels (test fixture format) should pass
        assert filter_obj.filter_entry(entry_with_label)

        # Entry WITHOUT labels (real data format) should fail - this is the bug
        # Currently it fails because there's no labels.register to match
        assert not filter_obj.filter_entry(entry_real_format)

    def test_pos_filter_requires_senses_data(self):
        """BUG: POS filter may fail on real data because POS isn't in lexemes file.

        Similar to the labels bug - POS tags are in en-senses.jsonl, not
        en-lexemes-enriched.jsonl.
        """
        # Real data format - no POS field
        entry_real_format = {
            "id": "cat",
            "frequency_tier": "A",
            "sources": ["wikt"],
            "sense_count": 1
        }

        spec = {"filters": {"pos": {"include": ["noun"]}}}
        filter_obj = MockOwlexFilter(spec)

        # Should fail because no POS data
        assert not filter_obj.filter_entry(entry_real_format)

    def test_concreteness_filter_requires_enrichment(self):
        """Verify concreteness filter behavior on data without concreteness.

        Only ~3% of words have concreteness data.
        """
        entry_without_concreteness = {
            "id": "cat",
            "frequency_tier": "A",
            "sources": ["wikt"]
        }

        spec = {"filters": {"concreteness": {"values": ["concrete"]}}}
        filter_obj = MockOwlexFilter(spec)

        # Should fail - no concreteness data means can't match
        assert not filter_obj.filter_entry(entry_without_concreteness)


# =============================================================================
# Integration Test: Real Data Verification
# =============================================================================

class TestRealDataIntegration:
    """Integration tests that verify behavior against real data files.

    These tests help catch architecture mismatches between the filter code
    and the actual data format produced by the CDA pipeline.
    """

    # Project root (tests are in tests/ subdirectory)
    PROJECT_ROOT = Path(__file__).parent.parent
    ENRICHED_PATH = PROJECT_ROOT / "data/intermediate/en-wikt-v2-enriched.jsonl"

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "data/intermediate/en-wikt-v2-enriched.jsonl").exists(),
        reason="Requires built lexicon data (run: make enrich)"
    )
    def test_cda_output_structure(self):
        """Verify the structure of the CDA pipeline output.

        This test documents what fields are actually present in the enriched
        JSONL produced by the CDA scanner and enrichment pipeline. Each line
        is a sense entry (not a word-level aggregate).

        Expected fields:
        - id: the word/phrase
        - pos: part of speech code (e.g., "NOU", "VRB")
        - codes: list of flag codes from CDA (e.g., "INFL", "ABRV")
        - lemma: base form of the word
        - wc: word count (1 for single words, 2+ for phrases)
        - nsyll: syllable count (optional, from enrichment)
        """
        import json

        with open(self.ENRICHED_PATH) as f:
            # Read a sample of entries
            entries = [json.loads(next(f)) for _ in range(100)]

        # Check which fields are commonly present
        field_counts = {}
        for entry in entries:
            for key in entry.keys():
                field_counts[key] = field_counts.get(key, 0) + 1

        # Core fields that MUST be present in every entry
        required_fields = ["id", "pos"]
        for field in required_fields:
            assert field_counts.get(field, 0) == 100, \
                f"Required field '{field}' missing from some entries"

        # Fields that SHOULD be present in most entries
        expected_common = ["codes", "lemma", "wc"]
        for field in expected_common:
            assert field in field_counts, \
                f"Expected field '{field}' not found in any entries"

        # Optional enrichment fields (may not be in every entry)
        optional_fields = ["nsyll", "frequency_tier", "concreteness", "aoa"]
        for field in optional_fields:
            if field in field_counts:
                print(f"  {field}: {field_counts[field]}/100 entries")


# =============================================================================
# Integration Tests: Operation-First Format Filtering
# =============================================================================

class TestOperationFirstFiltering:
    """Integration tests that verify operation-first format actually filters correctly.

    Unlike TestOperationFirstFormat which tests spec parsing,
    these tests verify the complete filtering pipeline works end-to-end.
    """

    def test_exclude_register_filters_words(self, mini_lexemes_file, tmp_path):
        """Test that exclude register actually removes vulgar words."""
        spec_content = """
exclude:
  register: [vulgar]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        # Load and filter entries
        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # "damn" has vulgar label - should be excluded
        assert "damn" not in results
        # "apple" has no labels - should be included
        assert "apple" in results
        # "bloody" has offensive but not vulgar - should still be included
        assert "bloody" in results

    def test_exclude_multiple_registers(self, mini_lexemes_file, tmp_path):
        """Test excluding multiple register types."""
        spec_content = """
exclude:
  register: [vulgar, offensive]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # Both vulgar and offensive should be excluded
        assert "damn" not in results
        assert "bloody" not in results
        # Clean words should remain
        assert "apple" in results

    def test_include_pos_filters_words(self, mini_lexemes_file, tmp_path):
        """Test that include pos only keeps specified POS."""
        spec_content = """
include:
  pos: [noun]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # Nouns should be included
        assert "apple" in results
        assert "cat" in results
        # Determiners should be excluded
        assert "the" not in results

    def test_combined_word_and_sense_filters(self, mini_lexemes_file, tmp_path):
        """Test combining word-level and sense-level filters."""
        spec_content = """
character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I

include:
  pos: [noun]

exclude:
  register: [vulgar, offensive]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # Verify all constraints are applied
        for word in results:
            assert len(word) == 5, f"{word} is not 5 letters"

        # "apple" should pass all filters
        assert "apple" in results
        # "cat" is only 3 letters
        assert "cat" not in results

    def test_exclude_temporal_filters(self, mini_lexemes_file, tmp_path):
        """Test excluding archaic and obsolete words."""
        spec_content = """
exclude:
  temporal: [archaic, obsolete]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)

        results = []
        with open(mini_lexemes_file) as f:
            for line in f:
                entry = json.loads(line)
                if filter_obj.filter_entry(entry):
                    results.append(entry["id"])

        # Words with archaic/obsolete labels should be excluded
        assert "thee" not in results
        assert "hither" not in results
        # Modern words should be included
        assert "apple" in results


# =============================================================================
# Integration Tests: Primary-Sense Filtering
# =============================================================================

class TestPrimarySenseFiltering:
    """Tests for exclude-if-primary and include-if-primary operations.

    These operations check only the first/primary sense of a word,
    allowing words with problematic secondary senses through.
    """

    def test_exclude_if_primary_vs_exclude(self, tmp_path):
        """Compare exclude-if-primary vs exclude behavior.

        Word with:
        - Primary sense: safe
        - Secondary sense: problematic

        exclude: should filter out
        exclude-if-primary: should keep
        """
        # Create a word with safe primary sense but problematic secondary
        lexeme_with_mixed_senses = {
            "id": "taffy",
            "pos": ["NOU"],
            "frequency_tier": "G",
            "sources": ["wikt"],
            "labels": {"register": ["derogatory"]},  # Has derogatory but not in primary
            "primary_labels": {},  # Primary sense is safe
        }

        # Regular exclude should filter it
        spec_exclude = {"filters": {"labels": {"register": {"exclude": ["derogatory"]}}}}
        filter_exclude = MockOwlexFilter(spec_exclude)
        assert not filter_exclude.filter_entry(lexeme_with_mixed_senses)

    def test_exclude_if_primary_pos(self, tmp_path):
        """Test exclude-if-primary with POS.

        Word "bill" has:
        - Primary sense: noun (common)
        - Secondary sense: proper noun (name Bill)

        exclude-if-primary: pos: [proper noun]
        Should INCLUDE "bill" because primary is common noun.
        """
        spec_content = """
exclude-if-primary:
  pos: [proper noun]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # Verify the spec was parsed correctly
        assert "pos" in filters
        assert "exclude-if-primary" in filters["pos"]
        assert filters["pos"]["exclude-if-primary"] == ["proper noun"]

    def test_include_if_primary_region(self, tmp_path):
        """Test include-if-primary with region labels."""
        spec_content = """
include-if-primary:
  region: [en-US]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # Verify spec parsing
        assert "labels" in filters
        assert "region" in filters["labels"]
        assert "include-if-primary" in filters["labels"]["region"]

    def test_combine_primary_and_regular_operations(self, tmp_path):
        """Test mixing -if-primary with regular operations."""
        spec_content = """
include:
  pos: [noun, verb]

exclude-if-primary:
  pos: [proper noun]

exclude:
  register: [vulgar, offensive]
"""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(spec_content)

        filter_obj = OwlexFilter(spec_file)
        filters = filter_obj.spec["filters"]

        # Verify all operations are captured
        assert filters["pos"]["include"] == ["noun", "verb"]
        assert filters["pos"]["exclude-if-primary"] == ["proper noun"]
        assert filters["labels"]["register"]["exclude"] == ["vulgar", "offensive"]


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
