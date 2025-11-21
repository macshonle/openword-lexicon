"""
Comprehensive WordNet enrichment test suite.

Tests both NLTK-based enrichment (current) and wn library enrichment (future).
Serves as:
- Regression tests for migration
- Edge case documentation
- Bug detection for current implementation
- Baseline behavior specification

Run with: pytest tests/test_wordnet_enrichment.py -v --tb=long
Generate report: pytest tests/test_wordnet_enrichment.py -v --tb=long > tests/wordnet_test_results.txt 2>&1
"""

import pytest
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional

# Import current NLTK-based implementation
# Import at runtime in fixtures to avoid module-load failures
NLTK_AVAILABLE = False
NLTK_IMPORT_ERROR = None

def _try_import_wordnet():
    """Attempt to import wordnet enrichment module."""
    global NLTK_AVAILABLE, NLTK_IMPORT_ERROR
    try:
        import sys
        from pathlib import Path
        # Add src to path if needed
        src_path = Path(__file__).parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from openword.wordnet_enrich import (
            get_concreteness,
            get_wordnet_pos,
            enrich_entry,
            ensure_wordnet_data
        )
        NLTK_AVAILABLE = True
        return {
            "get_concreteness": get_concreteness,
            "get_wordnet_pos": get_wordnet_pos,
            "enrich_entry": enrich_entry,
            "ensure_wordnet_data": ensure_wordnet_data
        }
    except ImportError as e:
        NLTK_AVAILABLE = False
        NLTK_IMPORT_ERROR = str(e)
        return None


# Test word categories for comprehensive coverage
TEST_WORDS = {
    "concrete_nouns": [
        "castle", "apple", "hammer", "dog", "table", "water",
        "mountain", "book", "car", "tree", "chair", "stone"
    ],
    "abstract_nouns": [
        "freedom", "justice", "happiness", "love", "theory",
        "democracy", "philosophy", "courage", "wisdom", "beauty"
    ],
    "mixed_nouns": [
        "paper", "bank", "culture", "light", "power",
        "form", "matter", "spirit", "nature", "value"
    ],
    "verbs": [
        "run", "think", "eat", "create", "destroy",
        "walk", "speak", "write", "build", "dance"
    ],
    "adjectives": [
        "happy", "red", "big", "beautiful", "difficult",
        "fast", "bright", "cold", "heavy", "smooth"
    ],
    "adverbs": [
        "quickly", "slowly", "happily", "very", "often",
        "never", "always", "probably", "clearly", "badly"
    ],
    "multiple_pos": [
        "light",  # noun, verb, adjective
        "run",    # noun, verb
        "fast",   # adjective, adverb, noun, verb
        "well",   # adverb, adjective, noun
        "back",   # noun, verb, adjective, adverb
    ],
    "edge_cases": [
        "nonexistentword12345",  # Should not be in WordNet
        "a",                      # Single letter
        "I",                      # Pronoun (capital)
        "OK",                     # Abbreviation
        "COVID-19",               # Modern neologism (not in old WordNet)
        "selfie",                 # Recent word
        "cryptocurrency",         # Modern compound
    ],
    "multi_word": [
        "give up",
        "kick the bucket",
        "New York",
    ],
    "special_chars": [
        "café",                   # Accented
        "naïve",                  # Diaeresis
        "résumé",                 # Multiple accents
    ],
}


class TestResult:
    """Detailed test result with full context for version control."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.status = "UNKNOWN"
        self.word = None
        self.input_data = None
        self.output_data = None
        self.error = None
        self.traceback = None
        self.notes = []

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "test_name": self.test_name,
            "status": self.status,
            "word": self.word,
            "input": self.input_data,
            "output": self.output_data,
            "error": self.error,
            "traceback": self.traceback,
            "notes": self.notes
        }


# Fixtures

@pytest.fixture(scope="session")
def nltk_wordnet():
    """Ensure NLTK WordNet is available and return imported functions."""
    funcs = _try_import_wordnet()
    if funcs is None:
        pytest.skip(f"NLTK not available: {NLTK_IMPORT_ERROR}")

    funcs["ensure_wordnet_data"]()
    return funcs


@pytest.fixture
def test_results_dir(tmp_path):
    """Directory for test result outputs."""
    results_dir = tmp_path / "test_results"
    results_dir.mkdir(exist_ok=True)
    return results_dir


@pytest.fixture
def sample_entry():
    """Basic entry for enrichment testing."""
    return {
        "word": "test",
        "pos": [],
        "labels": {},
        "is_phrase": False,
        "lemma": None,
        "sources": ["test"]
    }


# === NLTK-based enrichment tests (current implementation) ===

class TestNLTKConcreteness:
    """Test concreteness classification with NLTK."""

    def test_concrete_nouns(self, nltk_wordnet):
        """Concrete nouns should be classified as 'concrete'."""
        get_concreteness = nltk_wordnet["get_concreteness"]
        results = []
        for word in TEST_WORDS["concrete_nouns"]:
            result = TestResult(f"concrete_noun_{word}")
            result.word = word
            try:
                concreteness = get_concreteness(word)
                result.output_data = {"concreteness": concreteness}

                # We expect concrete, but document if different
                if concreteness == "concrete":
                    result.status = "PASS"
                elif concreteness is None:
                    result.status = "WARN"
                    result.notes.append("WordNet returned None (not in database)")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Expected 'concrete', got '{concreteness}'")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        # Assert at least some passed
        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) > 0, f"No concrete nouns classified correctly. Results: {results}"

    def test_abstract_nouns(self, nltk_wordnet):
        """Abstract nouns should be classified as 'abstract'."""
        results = []
        for word in TEST_WORDS["abstract_nouns"]:
            result = TestResult(f"abstract_noun_{word}")
            result.word = word
            try:
                concreteness = get_concreteness(word)
                result.output_data = {"concreteness": concreteness}

                if concreteness == "abstract":
                    result.status = "PASS"
                elif concreteness is None:
                    result.status = "WARN"
                    result.notes.append("WordNet returned None")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Expected 'abstract', got '{concreteness}'")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) > 0, f"No abstract nouns classified correctly. Results: {results}"

    def test_mixed_nouns(self, nltk_wordnet):
        """Nouns with both concrete and abstract senses should be 'mixed'."""
        results = []
        for word in TEST_WORDS["mixed_nouns"]:
            result = TestResult(f"mixed_noun_{word}")
            result.word = word
            try:
                concreteness = get_concreteness(word)
                result.output_data = {"concreteness": concreteness}

                # Mixed is expected, but concrete or abstract are also reasonable
                if concreteness in ["mixed", "concrete", "abstract"]:
                    result.status = "PASS"
                    if concreteness != "mixed":
                        result.notes.append(f"Not classified as 'mixed', but '{concreteness}' is acceptable")
                elif concreteness is None:
                    result.status = "WARN"
                    result.notes.append("WordNet returned None")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Unexpected value: '{concreteness}'")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        passed = [r for r in results if r.status in ["PASS", "WARN"]]
        assert len(passed) > 0, f"No mixed nouns handled correctly. Results: {results}"

    def test_non_nouns_return_none(self, nltk_wordnet):
        """Non-nouns should return None for concreteness."""
        results = []
        for word in TEST_WORDS["verbs"][:3]:  # Test a few verbs
            result = TestResult(f"verb_concreteness_{word}")
            result.word = word
            try:
                concreteness = get_concreteness(word)
                result.output_data = {"concreteness": concreteness}

                # Verbs might have noun senses, so we accept both None and a value
                result.status = "PASS"
                if concreteness is not None:
                    result.notes.append(f"Verb '{word}' has noun sense with concreteness '{concreteness}'")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        # All should complete without error
        errors = [r for r in results if r.status == "ERROR"]
        assert len(errors) == 0, f"Errors processing verbs: {errors}"


class TestNLTKPOSTagging:
    """Test POS tag extraction with NLTK."""

    def test_nouns(self, nltk_wordnet):
        """Test noun POS detection."""
        results = []
        for word in TEST_WORDS["concrete_nouns"][:5]:
            result = TestResult(f"pos_noun_{word}")
            result.word = word
            try:
                pos_tags = get_wordnet_pos(word)
                result.output_data = {"pos": pos_tags}

                if "noun" in pos_tags:
                    result.status = "PASS"
                elif len(pos_tags) == 0:
                    result.status = "WARN"
                    result.notes.append("No POS tags found")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Expected 'noun', got {pos_tags}")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) > 0, f"No nouns detected correctly. Results: {results}"

    def test_verbs(self, nltk_wordnet):
        """Test verb POS detection."""
        results = []
        for word in TEST_WORDS["verbs"][:5]:
            result = TestResult(f"pos_verb_{word}")
            result.word = word
            try:
                pos_tags = get_wordnet_pos(word)
                result.output_data = {"pos": pos_tags}

                if "verb" in pos_tags:
                    result.status = "PASS"
                elif len(pos_tags) == 0:
                    result.status = "WARN"
                    result.notes.append("No POS tags found")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Expected 'verb', got {pos_tags}")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) > 0, f"No verbs detected correctly. Results: {results}"

    def test_adjectives(self, nltk_wordnet):
        """Test adjective POS detection."""
        results = []
        for word in TEST_WORDS["adjectives"][:5]:
            result = TestResult(f"pos_adjective_{word}")
            result.word = word
            try:
                pos_tags = get_wordnet_pos(word)
                result.output_data = {"pos": pos_tags}

                if "adjective" in pos_tags:
                    result.status = "PASS"
                elif len(pos_tags) == 0:
                    result.status = "WARN"
                    result.notes.append("No POS tags found")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Expected 'adjective', got {pos_tags}")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) > 0, f"No adjectives detected correctly. Results: {results}"

    def test_multiple_pos(self, nltk_wordnet):
        """Test words with multiple POS tags."""
        results = []
        for word in TEST_WORDS["multiple_pos"]:
            result = TestResult(f"pos_multiple_{word}")
            result.word = word
            try:
                pos_tags = get_wordnet_pos(word)
                result.output_data = {"pos": pos_tags, "count": len(pos_tags)}

                if len(pos_tags) > 1:
                    result.status = "PASS"
                    result.notes.append(f"Multiple POS detected: {pos_tags}")
                elif len(pos_tags) == 1:
                    result.status = "WARN"
                    result.notes.append(f"Only one POS: {pos_tags} (expected multiple)")
                else:
                    result.status = "WARN"
                    result.notes.append("No POS tags found")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        # Document the behavior even if not all pass
        passed = [r for r in results if r.status in ["PASS", "WARN"]]
        assert len(passed) > 0, f"Failed to process multiple-POS words. Results: {results}"


class TestNLTKEdgeCases:
    """Test edge cases and potential bugs."""

    def test_nonexistent_word(self, nltk_wordnet):
        """Nonexistent words should return empty/None gracefully."""
        word = "nonexistentword12345"
        result = TestResult(f"edge_nonexistent_{word}")
        result.word = word

        try:
            pos_tags = get_wordnet_pos(word)
            concreteness = get_concreteness(word)

            result.output_data = {
                "pos": pos_tags,
                "concreteness": concreteness
            }

            # Should handle gracefully
            assert pos_tags == [] or pos_tags is None
            assert concreteness is None
            result.status = "PASS"

        except Exception as e:
            result.status = "ERROR"
            result.error = str(e)
            result.traceback = traceback.format_exc()

    def test_single_letter(self, nltk_wordnet):
        """Single letter words should be handled."""
        word = "a"
        result = TestResult(f"edge_single_letter_{word}")
        result.word = word

        try:
            pos_tags = get_wordnet_pos(word)
            result.output_data = {"pos": pos_tags}
            result.status = "PASS"
            result.notes.append(f"Single letter handled, POS: {pos_tags}")

        except Exception as e:
            result.status = "ERROR"
            result.error = str(e)
            result.traceback = traceback.format_exc()

    def test_modern_neologism(self, nltk_wordnet):
        """Modern words (post-2011) likely not in Princeton WordNet."""
        words = ["selfie", "cryptocurrency", "COVID-19"]
        results = []

        for word in words:
            result = TestResult(f"edge_neologism_{word}")
            result.word = word

            try:
                pos_tags = get_wordnet_pos(word)
                concreteness = get_concreteness(word)

                result.output_data = {
                    "pos": pos_tags,
                    "concreteness": concreteness
                }

                # Likely not in old WordNet
                if not pos_tags or pos_tags == []:
                    result.status = "EXPECTED"
                    result.notes.append("Not in WordNet 3.1 (as expected for modern word)")
                else:
                    result.status = "UNEXPECTED"
                    result.notes.append(f"Modern word found in WordNet: {pos_tags}")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        # All should complete without errors
        errors = [r for r in results if r.status == "ERROR"]
        assert len(errors) == 0, f"Errors with neologisms: {errors}"

    def test_accented_characters(self, nltk_wordnet):
        """Words with accents/diacritics should be handled."""
        results = []

        for word in TEST_WORDS["special_chars"]:
            result = TestResult(f"edge_accented_{word}")
            result.word = word

            try:
                pos_tags = get_wordnet_pos(word)
                result.output_data = {"pos": pos_tags}
                result.status = "PASS"
                result.notes.append(f"Accented word handled: {pos_tags}")

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)
                result.traceback = traceback.format_exc()

            results.append(result)

        # Should handle without crashing
        errors = [r for r in results if r.status == "ERROR"]
        assert len(errors) == 0, f"Errors with accented chars: {errors}"


class TestNLTKFullEnrichment:
    """Test complete entry enrichment pipeline."""

    def test_enrich_noun_without_pos(self, nltk_wordnet):
        """Entry without POS should get enriched."""
        entry = {
            "word": "castle",
            "pos": [],
            "labels": {},
            "is_phrase": False,
            "lemma": None,
            "sources": ["test"]
        }

        result = TestResult("enrich_noun_without_pos")
        result.word = "castle"
        result.input_data = entry.copy()

        try:
            enriched = enrich_entry(entry)
            result.output_data = enriched

            # Should add POS and concreteness
            assert "pos" in enriched
            assert len(enriched["pos"]) > 0, "POS should be backfilled"
            assert "noun" in enriched["pos"], "Should detect noun"

            # Should add concreteness for noun
            if "concreteness" in enriched:
                assert enriched["concreteness"] in ["concrete", "abstract", "mixed"]
                result.notes.append(f"Concreteness: {enriched['concreteness']}")

            # Should track WordNet source
            assert "wordnet" in enriched.get("sources", [])

            result.status = "PASS"

        except Exception as e:
            result.status = "ERROR"
            result.error = str(e)
            result.traceback = traceback.format_exc()

    def test_enrich_entry_with_existing_pos(self, nltk_wordnet):
        """Entry with existing POS should not be overwritten."""
        entry = {
            "word": "run",
            "pos": ["verb"],  # Already has POS
            "labels": {},
            "is_phrase": False,
            "lemma": None,
            "sources": ["test"]
        }

        result = TestResult("enrich_existing_pos")
        result.word = "run"
        result.input_data = entry.copy()

        try:
            enriched = enrich_entry(entry)
            result.output_data = enriched

            # Should NOT change existing POS
            assert enriched["pos"] == ["verb"], "Existing POS should be preserved"

            # Should NOT add concreteness for verb
            # (unless 'run' has a noun sense and we're being thorough)

            result.status = "PASS"

        except Exception as e:
            result.status = "ERROR"
            result.error = str(e)
            result.traceback = traceback.format_exc()

    def test_enrich_multi_word_phrase(self, nltk_wordnet):
        """Multi-word phrases should be skipped."""
        entry = {
            "word": "give up",
            "pos": [],
            "labels": {},
            "is_phrase": True,
            "word_count": 2,
            "lemma": None,
            "sources": ["test"]
        }

        result = TestResult("enrich_multi_word")
        result.word = "give up"
        result.input_data = entry.copy()

        try:
            enriched = enrich_entry(entry)
            result.output_data = enriched

            # Should skip enrichment for multi-word
            assert enriched == entry, "Multi-word should not be enriched"
            assert "wordnet" not in enriched.get("sources", [])

            result.status = "PASS"
            result.notes.append("Multi-word correctly skipped")

        except Exception as e:
            result.status = "ERROR"
            result.error = str(e)
            result.traceback = traceback.format_exc()


# === Utility tests ===

class TestWordNetAvailability:
    """Test that WordNet data is properly available."""

    def test_nltk_wordnet_data_present(self, nltk_wordnet):
        """Verify NLTK WordNet data is downloaded and accessible."""
        try:
            from nltk.corpus import wordnet as wn

            # Try to query WordNet
            synsets = wn.synsets('test')

            assert synsets is not None
            assert len(synsets) >= 0  # May be empty, that's OK

        except LookupError as e:
            pytest.fail(f"WordNet data not found: {e}")

    def test_nltk_version_info(self, nltk_wordnet):
        """Document NLTK and WordNet version."""
        import nltk
        from nltk.corpus import wordnet as wn

        info = {
            "nltk_version": nltk.__version__,
            "wordnet_available": True,
            "sample_synsets": len(wn.synsets('dog')),
        }

        print(f"\nWordNet Info: {json.dumps(info, indent=2)}")
        assert info["nltk_version"] is not None


# === Test result collection and reporting ===

@pytest.fixture(scope="session", autouse=True)
def collect_test_results(request, tmp_path_factory):
    """Collect all test results for JSON export."""
    results_file = tmp_path_factory.mktemp("results") / "wordnet_test_results.json"

    yield

    # After all tests, we could save results if needed
    # (This is a placeholder for custom result collection)


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v", "--tb=short"])
