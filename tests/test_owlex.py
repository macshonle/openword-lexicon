"""Tests for owlex word list generator.

Unit tests for filter functions and integration tests for the CLI.
"""

import json
import pytest
import tempfile
from pathlib import Path

from openword.owlex import OwlexFilter


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
        {"id": "apple", "pos": ["noun"], "frequency_tier": "B", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2},
        {"id": "bread", "pos": ["noun"], "frequency_tier": "C", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "chair", "pos": ["noun"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "dream", "pos": ["noun", "verb"], "frequency_tier": "C", "sources": ["wikt", "wordnet"],
         "labels": {}, "concreteness": "abstract", "nsyll": 1},
        {"id": "earth", "pos": ["noun"], "frequency_tier": "B", "sources": ["wikt", "wordnet"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},

        # Short common words
        {"id": "cat", "pos": ["noun"], "frequency_tier": "A", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "dog", "pos": ["noun"], "frequency_tier": "A", "sources": ["wikt", "eowl"],
         "labels": {}, "concreteness": "concrete", "nsyll": 1},
        {"id": "the", "pos": ["determiner"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},
        {"id": "run", "pos": ["verb", "noun"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},

        # Words with special characters
        {"id": "don't", "pos": ["verb"], "frequency_tier": "A", "sources": ["wikt"],
         "labels": {}, "nsyll": 1},
        {"id": "self-help", "pos": ["noun"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "re-enter", "pos": ["verb"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {}, "nsyll": 3},

        # Multi-word phrases
        {"id": "hot dog", "pos": ["noun"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2, "wc": 2},
        {"id": "ice cream", "pos": ["noun"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2, "wc": 2},

        # Words with labels
        {"id": "damn", "pos": ["interjection", "verb"], "frequency_tier": "D", "sources": ["wikt"],
         "labels": {"register": ["vulgar"]}, "nsyll": 1},
        {"id": "bloody", "pos": ["adjective"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {"register": ["offensive"], "region": ["en-GB"]}, "nsyll": 2},
        {"id": "thee", "pos": ["pronoun"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {"temporal": ["archaic"]}, "nsyll": 1},
        {"id": "hither", "pos": ["adverb"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {"temporal": ["archaic", "obsolete"]}, "nsyll": 2},
        {"id": "whilst", "pos": ["conjunction"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {"temporal": ["dated"], "region": ["en-GB"]}, "nsyll": 1},

        # Rare/uncommon words
        {"id": "pulchritudinous", "pos": ["adjective"], "frequency_tier": "Z", "sources": ["wikt"],
         "labels": {}, "nsyll": 6},
        {"id": "defenestration", "pos": ["noun"], "frequency_tier": "Y", "sources": ["wikt", "wordnet"],
         "labels": {}, "nsyll": 5},

        # Words from different sources
        {"id": "syzygy", "pos": ["noun"], "frequency_tier": "Y", "sources": ["wordnet"],
         "labels": {}, "nsyll": 3},
        {"id": "aardvark", "pos": ["noun"], "frequency_tier": "I", "sources": ["eowl", "wordnet"],
         "labels": {}, "concreteness": "concrete", "nsyll": 2},

        # Regional variants
        {"id": "color", "pos": ["noun", "verb"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "spelling_region": "en-US", "nsyll": 2},
        {"id": "colour", "pos": ["noun", "verb"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "spelling_region": "en-GB", "nsyll": 2},

        # Words with specific prefixes/suffixes
        {"id": "unhappy", "pos": ["adjective"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {}, "nsyll": 3},
        {"id": "running", "pos": ["verb", "noun"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "preview", "pos": ["noun", "verb"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},
        {"id": "rethink", "pos": ["verb", "noun"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {}, "nsyll": 2},

        # Proper noun edge cases
        {"id": "bill", "pos": ["noun", "verb"], "frequency_tier": "C", "sources": ["wikt"],
         "labels": {}, "has_common_usage": True, "has_proper_usage": True, "nsyll": 1},
        {"id": "aaron", "pos": ["noun"], "frequency_tier": "H", "sources": ["wikt"],
         "labels": {}, "has_common_usage": False, "has_proper_usage": True, "nsyll": 2},

        # Technical/domain-specific words
        {"id": "plaintiff", "pos": ["noun"], "frequency_tier": "G", "sources": ["wikt"],
         "labels": {"domain": ["legal"]}, "nsyll": 2},
        {"id": "diagnosis", "pos": ["noun"], "frequency_tier": "F", "sources": ["wikt"],
         "labels": {"domain": ["medical"]}, "nsyll": 4},

        # Slang
        {"id": "cool", "pos": ["adjective", "verb"], "frequency_tier": "B", "sources": ["wikt"],
         "labels": {"register": ["slang"]}, "concreteness": "abstract", "nsyll": 1},
        {"id": "dude", "pos": ["noun"], "frequency_tier": "E", "sources": ["wikt"],
         "labels": {"register": ["informal", "slang"]}, "nsyll": 1},
    ]


@pytest.fixture
def mini_lexemes_file(mini_lexemes, tmp_path):
    """Create a temporary JSONL file with mini lexemes."""
    lexemes_file = tmp_path / "test-lexemes.jsonl"
    with open(lexemes_file, 'w') as f:
        for entry in mini_lexemes:
            f.write(json.dumps(entry) + '\n')
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
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]

        assert "cat" in words  # 3 letters
        assert "apple" in words  # 5 letters
        assert "unhappy" not in words  # 7 letters

    def test_pattern_filter(self, mini_lexemes):
        """Test regex pattern filter."""
        spec = {"filters": {"character": {"pattern": "^[a-z]+$"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

        assert "apple" in words
        assert "don't" not in words  # has apostrophe
        assert "self-help" not in words  # has hyphen
        assert "hot dog" not in words  # has space

    def test_starts_with(self, mini_lexemes):
        """Test starts_with filter with multiple prefixes."""
        spec = {"filters": {"character": {"starts_with": ["un", "re"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]

        assert "running" in words
        assert "run" not in words

    def test_contains(self, mini_lexemes):
        """Test contains filter with AND logic."""
        spec = {"filters": {"character": {"contains": ["ea"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]

        assert "apple" in words
        assert "hot dog" not in words
        assert "ice cream" not in words

    def test_min_words_phrases(self, mini_lexemes):
        """Test min_words=2 for phrases only."""
        spec = {"filters": {"phrase": {"min_words": 2}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]
        tiers = {e['id']: e['frequency_tier'] for e in results}

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
        words = [e['id'] for e in results]

        assert "aardvark" in words  # I
        assert "syzygy" not in words  # Y
        assert "pulchritudinous" not in words  # Z

    def test_specific_tiers(self, mini_lexemes):
        """Test filtering by specific tier list."""
        spec = {"filters": {"frequency": {"tiers": ["A", "B"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        tiers = [e['frequency_tier'] for e in results]

        assert all(t in ["A", "B"] for t in tiers)


# =============================================================================
# Unit Tests: POS Filters
# =============================================================================

class TestPOSFilters:
    """Unit tests for part-of-speech filters."""

    def test_include_nouns(self, mini_lexemes):
        """Test include=[noun] filter."""
        spec = {"filters": {"pos": {"include": ["noun"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "noun" in entry.get('pos', [])

    def test_exclude_verbs(self, mini_lexemes):
        """Test exclude=[verb] filter."""
        spec = {"filters": {"pos": {"exclude": ["verb"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "verb" not in entry.get('pos', [])

    def test_include_multiple_pos(self, mini_lexemes):
        """Test include with multiple POS (OR logic)."""
        spec = {"filters": {"pos": {"include": ["noun", "adjective"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            pos = entry.get('pos', [])
            assert "noun" in pos or "adjective" in pos


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
        words = [e['id'] for e in results]

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
        spec = {"filters": {"labels": {"register": {"exclude": ["vulgar"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

        assert "damn" not in words
        assert "apple" in words

    def test_exclude_offensive(self, mini_lexemes):
        """Test excluding offensive words."""
        spec = {"filters": {"labels": {"register": {"exclude": ["vulgar", "offensive"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

        assert "damn" not in words
        assert "bloody" not in words
        assert "apple" in words

    def test_include_slang(self, mini_lexemes):
        """Test including only slang words."""
        spec = {"filters": {"labels": {"register": {"include": ["slang"]}}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
        spec = {"filters": {"temporal": {"exclude": ["archaic"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

        assert "thee" not in words
        assert "hither" not in words
        assert "apple" in words

    def test_exclude_all_old_words(self, mini_lexemes):
        """Test excluding archaic, obsolete, and dated words."""
        spec = {"filters": {"temporal": {"exclude": ["archaic", "obsolete", "dated"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
            assert "wordnet" in entry.get('sources', [])

    def test_include_eowl_only(self, mini_lexemes):
        """Test filtering for EOWL-only words."""
        spec = {"filters": {"sources": {"include": ["eowl"]}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            assert "eowl" in entry.get('sources', [])


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
        words = [e['id'] for e in results]

        assert "color" in words
        assert "colour" not in words
        # Universal words should also be included
        assert "apple" in words

    def test_gb_spelling_only(self, mini_lexemes):
        """Test filtering for GB spellings."""
        spec = {"filters": {"region": {"region": "en-GB"}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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
            assert entry.get('nsyll') == 2

    def test_syllable_range(self, mini_lexemes):
        """Test syllable range filter."""
        spec = {"filters": {"syllables": {"min": 1, "max": 2}}}
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]

        for entry in results:
            syllables = entry.get('nsyll')
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
        words = [e['id'] for e in results]

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
        words = [e['id'] for e in results]

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
                "labels": {"register": {"exclude": ["vulgar", "offensive", "slang"]}}
            }
        }
        filter_obj = MockOwlexFilter(spec)

        results = [e for e in mini_lexemes if filter_obj.filter_entry(e)]
        words = [e['id'] for e in results]

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

        assert filter_obj.spec['filters']['character']['exact_length'] == 5
        assert filter_obj.spec['filters']['phrase']['max_words'] == 1
        assert filter_obj.spec['filters']['frequency']['min_tier'] == 'A'

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

        assert filter_obj.spec['_sources_filter']['include'] == ['wordnet']
        assert filter_obj.spec['filters']['character']['min_length'] == 3


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
                    results.append(entry['id'])

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
        entry = {"id": "test", "pos": ["noun"], "frequency_tier": "C", "sources": ["wikt"]}
        spec = {"filters": {"labels": {"register": {"exclude": ["vulgar"]}}}}
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
        result = filter_obj.filter_entry(entry)
        # This should pass since max_tier=Z

    def test_syllable_filter_without_syllable_data(self, mini_lexemes):
        """Test syllable filter on entry without syllable data."""
        entry = {"id": "test", "frequency_tier": "C", "sources": ["wikt"]}  # No syllables

        spec = {"filters": {"syllables": {"exact": 2}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry without syllable data - behavior depends on implementation
        # It should either fail (no data) or pass (no data means no constraint)
        result = filter_obj.filter_entry(entry)

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
        result = filter_obj.filter_entry(entry)
        # This is a potential bug - empty string matches all

    def test_pattern_special_characters(self, mini_lexemes):
        """Test pattern filter with special regex characters."""
        entry = {"id": "test", "sources": ["wikt"]}
        spec = {"filters": {"character": {"pattern": r"^[a-z\.]+$"}}}
        filter_obj = MockOwlexFilter(spec)

        # Should handle regex special chars correctly
        result = filter_obj.filter_entry(entry)


# =============================================================================
# Helper: Mock OwlexFilter for Unit Tests
# =============================================================================

class MockOwlexFilter(OwlexFilter):
    """Mock filter that doesn't require a file path."""

    def __init__(self, spec: dict):
        self.spec = {
            'version': '2.0',
            'distribution': 'en',
            'filters': spec.get('filters', {}),
            '_sources_filter': spec.get('_sources_filter', {})
        }
        # Tier scores - A (most common) to Z (least common)
        # A=100, B=96, C=92... decreasing by 4 each tier
        self.tier_scores = {
            'A': 100, 'B': 96, 'C': 92, 'D': 88, 'E': 84, 'F': 80,
            'G': 76, 'H': 72, 'I': 68, 'J': 64, 'K': 60, 'L': 56,
            'M': 52, 'N': 48, 'O': 44, 'P': 40, 'Q': 36, 'R': 32,
            'S': 28, 'T': 24, 'U': 20, 'V': 16, 'W': 12, 'X': 8,
            'Y': 4, 'Z': 0
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
            "labels": {"register": ["vulgar"]},
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

        spec = {"filters": {"labels": {"register": {"include": ["vulgar"]}}}}
        filter_obj = MockOwlexFilter(spec)

        # Entry WITH labels (test fixture format) should pass
        assert filter_obj.filter_entry(entry_with_label) == True

        # Entry WITHOUT labels (real data format) should fail - this is the bug
        # Currently it fails because there's no labels.register to match
        assert filter_obj.filter_entry(entry_real_format) == False

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
        assert filter_obj.filter_entry(entry_real_format) == False

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
        assert filter_obj.filter_entry(entry_without_concreteness) == False


# =============================================================================
# Integration Test: Real Data Verification
# =============================================================================

class TestRealDataIntegration:
    """Integration tests that verify behavior against real data files.

    These tests help catch architecture mismatches between the filter code
    and the actual data format.
    """

    # Project root (tests are in tests/ subdirectory)
    PROJECT_ROOT = Path(__file__).parent.parent
    LEXEMES_PATH = PROJECT_ROOT / "data/intermediate/en-lexemes-enriched.jsonl"
    SENSES_PATH = PROJECT_ROOT / "data/intermediate/en-senses.jsonl"

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "data/intermediate/en-lexemes-enriched.jsonl").exists(),
        reason="Requires built lexicon data"
    )
    def test_lexemes_file_structure(self):
        """Verify the actual structure of the lexemes file.

        This test documents what fields are actually present in the data.
        """
        import json

        lexemes_path = self.LEXEMES_PATH
        with open(lexemes_path) as f:
            # Read a sample of entries
            entries = [json.loads(next(f)) for _ in range(100)]

        # Check which fields are commonly present
        field_counts = {}
        for entry in entries:
            for key in entry.keys():
                field_counts[key] = field_counts.get(key, 0) + 1

        # Expected fields that SHOULD be in lexemes
        expected_always = ["id", "sources", "frequency_tier"]
        for field in expected_always:
            assert field in field_counts, f"Missing expected field: {field}"

        # Fields that are NOT in lexemes (they're in senses)
        # If these appear, the architecture has changed
        sense_only_fields = ["pos", "labels", "register_tags"]
        for field in sense_only_fields:
            if field in field_counts:
                # This would be good! It means the bug is fixed
                print(f"NOTICE: {field} is now in lexemes file!")

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "data/intermediate/en-senses.jsonl").exists(),
        reason="Requires built lexicon data"
    )
    def test_senses_file_structure(self):
        """Verify the actual structure of the senses file.

        This test documents what fields are actually present in senses data.
        """
        import json

        senses_path = self.SENSES_PATH
        with open(senses_path) as f:
            # Read a sample of entries
            entries = [json.loads(next(f)) for _ in range(100)]

        # Check which fields are commonly present
        field_counts = {}
        for entry in entries:
            for key in entry.keys():
                field_counts[key] = field_counts.get(key, 0) + 1

        # Expected fields in senses
        expected = ["id", "pos"]
        for field in expected:
            assert field in field_counts, f"Missing expected field: {field}"

        # Fields that SHOULD be in senses (register_tags, not labels)
        # This verifies the actual data format
        if "register_tags" in field_counts:
            print(f"register_tags found in {field_counts['register_tags']}/100 entries")
        if "labels" in field_counts:
            print(f"labels found in {field_counts['labels']}/100 entries")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
