"""Unit tests for lemma extraction from Wiktionary templates."""
import pytest
from openword.filters import (
    sense_is_base_form,
    sense_is_inflected,
    sense_has_lemma,
    sense_get_lemma,
)


class TestLemmaExtractionPredicates:
    """Test sense-level lemma predicates."""

    def test_sense_is_base_form_true_for_base_word(self):
        """Base words should be identified as base forms."""
        sense = {"word": "cat", "pos": "noun", "is_inflected": False}
        assert sense_is_base_form(sense) is True

    def test_sense_is_base_form_false_for_inflected(self):
        """Words marked as inflected should not be base forms."""
        sense = {"word": "cats", "pos": "noun", "is_inflected": True, "lemma": "cat"}
        assert sense_is_base_form(sense) is False

    def test_sense_is_base_form_false_when_lemma_present(self):
        """Words with lemma field should not be base forms."""
        sense = {"word": "running", "pos": "verb", "lemma": "run"}
        assert sense_is_base_form(sense) is False

    def test_sense_is_base_form_true_when_no_flags(self):
        """Words without inflection flags should be base forms."""
        sense = {"word": "run", "pos": "verb"}
        assert sense_is_base_form(sense) is True

    def test_sense_is_inflected_true(self):
        """Words marked as inflected should return True."""
        sense = {"word": "cats", "pos": "noun", "is_inflected": True}
        assert sense_is_inflected(sense) is True

    def test_sense_is_inflected_false(self):
        """Words not marked as inflected should return False."""
        sense = {"word": "cat", "pos": "noun", "is_inflected": False}
        assert sense_is_inflected(sense) is False

    def test_sense_is_inflected_default_false(self):
        """Missing is_inflected should default to False."""
        sense = {"word": "cat", "pos": "noun"}
        assert sense_is_inflected(sense) is False

    def test_sense_has_lemma_match(self):
        """Should return True when lemma matches target."""
        sense = {"word": "cats", "pos": "noun", "lemma": "cat"}
        assert sense_has_lemma(sense, "cat") is True

    def test_sense_has_lemma_no_match(self):
        """Should return False when lemma doesn't match."""
        sense = {"word": "cats", "pos": "noun", "lemma": "cat"}
        assert sense_has_lemma(sense, "dog") is False

    def test_sense_has_lemma_no_lemma(self):
        """Should return False when no lemma field exists."""
        sense = {"word": "cat", "pos": "noun"}
        assert sense_has_lemma(sense, "cat") is False

    def test_sense_get_lemma_returns_lemma(self):
        """Should return lemma when present."""
        sense = {"word": "cats", "pos": "noun", "lemma": "cat"}
        assert sense_get_lemma(sense) == "cat"

    def test_sense_get_lemma_returns_none(self):
        """Should return None when no lemma."""
        sense = {"word": "cat", "pos": "noun"}
        assert sense_get_lemma(sense) is None


class TestLemmaTemplatePatterns:
    """Test lemma extraction regex patterns match expected templates."""

    # These test the regex patterns defined in the Python scanner
    # We test by checking that known template strings would be matched

    @pytest.fixture
    def scanner_patterns(self):
        """Import the inflection template patterns from the scanner."""
        import sys
        from pathlib import Path

        # Add tools directory to path
        tools_path = Path(__file__).parent.parent / "tools"
        sys.path.insert(0, str(tools_path))

        try:
            from wiktionary_scanner_python.scanner import INFLECTION_TEMPLATES
            return INFLECTION_TEMPLATES
        except ImportError:
            pytest.skip("Python scanner not available")
        finally:
            sys.path.pop(0)

    def test_plural_of_pattern(self, scanner_patterns):
        """{{plural of|en|cat}} should extract 'cat'."""
        text = "# {{plural of|en|cat}}"
        for name, pattern in scanner_patterns:
            if "plural of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "cat"
                return
        pytest.fail("No 'plural of' pattern found")

    def test_past_tense_pattern(self, scanner_patterns):
        """{{past tense of|en|run}} should extract 'run'."""
        text = "# {{past tense of|en|run}}"
        for name, pattern in scanner_patterns:
            if "past tense of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "run"
                return
        pytest.fail("No 'past tense of' pattern found")

    def test_past_participle_pattern(self, scanner_patterns):
        """{{past participle of|en|write}} should extract 'write'."""
        text = "# {{past participle of|en|write}}"
        for name, pattern in scanner_patterns:
            if "past participle of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "write"
                return
        pytest.fail("No 'past participle of' pattern found")

    def test_present_participle_pattern(self, scanner_patterns):
        """{{present participle of|en|run}} should extract 'run'."""
        text = "# {{present participle of|en|run}}"
        for name, pattern in scanner_patterns:
            if "present participle of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "run"
                return
        pytest.fail("No 'present participle of' pattern found")

    def test_comparative_pattern(self, scanner_patterns):
        """{{comparative of|en|big}} should extract 'big'."""
        text = "# {{comparative of|en|big}}"
        for name, pattern in scanner_patterns:
            if "comparative of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "big"
                return
        pytest.fail("No 'comparative of' pattern found")

    def test_superlative_pattern(self, scanner_patterns):
        """{{superlative of|en|big}} should extract 'big'."""
        text = "# {{superlative of|en|big}}"
        for name, pattern in scanner_patterns:
            if "superlative of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "big"
                return
        pytest.fail("No 'superlative of' pattern found")

    def test_inflection_of_pattern(self, scanner_patterns):
        """{{inflection of|en|go||past|part}} should extract 'go'."""
        text = "# {{inflection of|en|go||past|part}}"
        for name, pattern in scanner_patterns:
            if "inflection of" in name:
                match = pattern.search(text)
                assert match is not None
                assert match.group(1).strip().lower() == "go"
                return
        pytest.fail("No 'inflection of' pattern found")


class TestGoldenLemmas:
    """Test known lemma mappings (golden test data)."""

    # These are well-known irregular inflections that should be extracted correctly
    GOLDEN_LEMMAS = {
        # Irregular plurals
        "mice": "mouse",
        "children": "child",
        "feet": "foot",
        "teeth": "tooth",
        "geese": "goose",
        "men": "man",
        "women": "woman",
        "people": "person",
        "oxen": "ox",

        # Irregular verb forms
        "went": "go",
        "gone": "go",
        "was": "be",
        "were": "be",
        "been": "be",
        "ate": "eat",
        "eaten": "eat",
        "took": "take",
        "taken": "take",
        "wrote": "write",
        "written": "write",
        "spoke": "speak",
        "spoken": "speak",
        "broke": "break",
        "broken": "break",
        "chose": "choose",
        "chosen": "choose",
        "froze": "freeze",
        "frozen": "freeze",
        "drove": "drive",
        "driven": "drive",

        # Irregular comparatives/superlatives
        "better": "good",
        "best": "good",
        "worse": "bad",
        "worst": "bad",
        "more": "much",
        "most": "much",
        "less": "little",
        "least": "little",
    }

    def test_golden_lemma_structure(self):
        """Verify golden lemmas are correctly structured."""
        for inflected, base in self.GOLDEN_LEMMAS.items():
            assert isinstance(inflected, str)
            assert isinstance(base, str)
            assert inflected != base  # Inflected form should differ from base
            assert len(inflected) > 0
            assert len(base) > 0

    def test_golden_lemmas_count(self):
        """Ensure we have a reasonable set of golden test cases."""
        # Should have at least 30 golden lemma test cases
        assert len(self.GOLDEN_LEMMAS) >= 30


class TestNormalizationPipeline:
    """Test lemma handling in the normalization pipeline."""

    def test_sense_projection_includes_lemma(self):
        """Verify sense_projection includes lemma for deduplication."""
        from openword.wikt_normalize import sense_projection

        # Two senses with same POS but different lemmas should be different
        sense1 = {"pos": "verb", "is_inflected": True, "lemma": "leave"}
        sense2 = {"pos": "verb", "is_inflected": True, "lemma": "left"}

        proj1 = sense_projection(sense1)
        proj2 = sense_projection(sense2)

        assert proj1 != proj2, "Different lemmas should produce different projections"

    def test_sense_projection_same_lemma(self):
        """Verify same lemma produces same projection."""
        from openword.wikt_normalize import sense_projection

        sense1 = {"pos": "noun", "is_inflected": True, "lemma": "cat"}
        sense2 = {"pos": "noun", "is_inflected": True, "lemma": "cat"}

        proj1 = sense_projection(sense1)
        proj2 = sense_projection(sense2)

        assert proj1 == proj2, "Same lemma should produce same projection"
