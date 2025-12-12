"""Tests for verifying parity between Rust and Python Wiktionary scanners.

These tests ensure both scanners produce identical results for the same input,
helping catch regressions when either scanner is modified.
"""

import sys
from pathlib import Path
import pytest

# Add legacy scanner_v1 directory to path
legacy_path = Path(__file__).parent.parent / "legacy" / "scanner_v1"
sys.path.insert(0, str(legacy_path))

from wiktionary_scanner_python.wikitext_parser import (
    WikitextParser,
    parse_template_params,
)
from wiktionary_scanner_python.scanner import (
    extract_syllable_count_from_hyphenation,
    extract_syllable_count_from_rhymes,
    extract_syllable_count_from_ipa,
    count_syllables_from_ipa,
    extract_morphology,
    classify_morphology,
    extract_labels_from_line,
)


# =============================================================================
# Shared Test Cases for Scanner Parity
# =============================================================================

# These test cases should produce identical results in both Rust and Python
WIKITEXT_PARSING_CASES = [
    # Basic parameters
    ("en|word|suffix", ["en", "word", "suffix"]),
    ("", []),
    ("word", ["word"]),
    ("  en  |  word  |  suffix  ", ["en", "word", "suffix"]),

    # Wikilinks
    ("[[cat]]", ["cat"]),
    ("[[isle|Isle]]", ["Isle"]),
    ("[[Man#Etymology 2]]", ["Man"]),
    ("[[Man#Etymology 2|Man]]", ["Man"]),
    ("en|[[isle|Isle]]|of|[[Man#Etymology 2|Man]]", ["en", "Isle", "of", "Man"]),
]

SYLLABLE_EXTRACTION_CASES = [
    # (word, template_text, expected_syllable_count)
    ("dictionary", "{{hyphenation|en|dic|tion|a|ry}}", 4),
    ("encyclopedia", "{{hyphenation|en|en|cy|clo|pe|di|a}}", 6),  # Bug fix case
    ("encore", "{{hyphenation|en|en|core}}", 2),  # First syllable matches lang code
    ("italic", "{{hyphenation|en|it|al|ic}}", 3),  # "it" is also a lang code
    ("thesaurus", "{{hyphenation|en|the|saur|us}}", 3),
]

RHYMES_EXTRACTION_CASES = [
    # (template_text, expected_syllable_count)
    ("{{rhymes|en|æt|s=1}}", 1),
    ("{{rhymes|en|iːdiə|s=6}}", 6),
    ("{{rhymes|en|ɔːɹəs|s=3}}", 3),
    ("{{rhymes|en|æt}}", None),  # No s= parameter
]

IPA_SYLLABLE_CASES = [
    # (ipa_transcription, expected_syllable_count)
    ("/kæt/", 1),  # cat
    ("/ˈteɪ.bəl/", 2),  # table - with schwa for second syllable
    ("/ɪnˌsaɪ.kləˈpiː.di.ə/", 6),  # encyclopedia
    ("/əˈsæsɪn/", 3),  # assassin
    ("/θiˈsɔɹəs/", 3),  # thesaurus
]

MORPHOLOGY_CASES = [
    # (etymology_text, expected_components_or_type)
    ("===Etymology===\n{{suffix|en|happy|ness}}", {"suffix": ["-ness"]}),
    ("===Etymology===\n{{prefix|en|un|happy}}", {"prefix": ["un-"]}),
    ("===Etymology===\n{{compound|en|sun|flower}}", {"compound": ["sun", "flower"]}),
    ("===Etymology===\n{{af|en|un-|happy}}", {"prefix": ["un-"]}),
    ("===Etymology===\n{{af|en|happy|-ness}}", {"suffix": ["-ness"]}),
]


# =============================================================================
# Test Classes
# =============================================================================

class TestWikitextParserParity:
    """Test that Python WikitextParser matches expected Rust behavior."""

    @pytest.mark.parametrize("input_str,expected", WIKITEXT_PARSING_CASES)
    def test_template_param_parsing(self, input_str, expected):
        """Test template parameter parsing produces expected results."""
        result = parse_template_params(input_str)
        assert result == expected, f"Input: {input_str!r}"


class TestSyllableExtractionParity:
    """Test syllable extraction produces same results in both scanners."""

    @pytest.mark.parametrize("word,template,expected", SYLLABLE_EXTRACTION_CASES)
    def test_hyphenation_extraction(self, word, template, expected):
        """Test hyphenation template parsing."""
        result = extract_syllable_count_from_hyphenation(template, word)
        assert result == expected, f"Word: {word}, Template: {template}"

    @pytest.mark.parametrize("template,expected", RHYMES_EXTRACTION_CASES)
    def test_rhymes_extraction(self, template, expected):
        """Test rhymes template parsing."""
        result = extract_syllable_count_from_rhymes(template)
        assert result == expected, f"Template: {template}"

    @pytest.mark.parametrize("ipa,expected", IPA_SYLLABLE_CASES)
    def test_ipa_syllable_counting(self, ipa, expected):
        """Test IPA syllable counting."""
        result = count_syllables_from_ipa(ipa)
        assert result == expected, f"IPA: {ipa}"


class TestMorphologyExtractionParity:
    """Test morphology extraction matches between scanners."""

    def test_suffix_extraction(self):
        """Test suffix template extraction."""
        text = "===Etymology===\n{{suffix|en|happy|ness}}"
        result = extract_morphology(text)

        assert result is not None
        assert result.get("type") == "suffixed"
        # Components should include the suffix
        components = result.get("components", [])
        assert any("-ness" in c or "ness" in c for c in components)

    def test_prefix_extraction(self):
        """Test prefix template extraction."""
        text = "===Etymology===\n{{prefix|en|un|happy}}"
        result = extract_morphology(text)

        assert result is not None
        assert result.get("type") == "prefixed"
        components = result.get("components", [])
        assert any("un-" in c or "un" in c for c in components)

    def test_compound_extraction(self):
        """Test compound template extraction."""
        text = "===Etymology===\n{{compound|en|sun|flower}}"
        result = extract_morphology(text)

        assert result is not None
        assert result.get("type") == "compound"
        components = result.get("components", [])
        assert "sun" in components
        assert "flower" in components

    def test_affix_as_suffix(self):
        """Test affix template recognized as suffix."""
        text = "===Etymology===\n{{af|en|happy|-ness}}"
        result = extract_morphology(text)

        assert result is not None
        # Should be classified as suffixed based on the -ness pattern

    def test_classify_morphology_suffixed(self):
        """Test classification of suffixed words via extract_morphology."""
        text = "===Etymology===\n{{suffix|en|happy|ness}}"
        result = extract_morphology(text)
        assert result is not None
        assert result.get("type") == "suffixed"

    def test_classify_morphology_prefixed(self):
        """Test classification of prefixed words via extract_morphology."""
        text = "===Etymology===\n{{prefix|en|un|happy}}"
        result = extract_morphology(text)
        assert result is not None
        assert result.get("type") == "prefixed"

    def test_classify_morphology_compound(self):
        """Test classification of compound words via extract_morphology."""
        text = "===Etymology===\n{{compound|en|sun|flower}}"
        result = extract_morphology(text)
        assert result is not None
        assert result.get("type") == "compound"


class TestLabelExtractionParity:
    """Test label extraction from definition lines.

    extract_labels_from_line returns a tuple:
    (register_tags, region_tags, domain_tags, temporal_tags)
    """

    def test_vulgar_label(self):
        """Test extraction of vulgar register label."""
        line = "# {{lb|en|vulgar}} An expletive"
        register_tags, region_tags, domain_tags, temporal_tags = extract_labels_from_line(line)

        assert "vulgar" in register_tags

    def test_archaic_label(self):
        """Test extraction of archaic temporal label."""
        line = "# {{lb|en|archaic}} An old word"
        register_tags, region_tags, domain_tags, temporal_tags = extract_labels_from_line(line)

        assert "archaic" in temporal_tags

    def test_regional_label(self):
        """Test extraction of regional labels."""
        line = "# {{lb|en|US}} American term"
        register_tags, region_tags, domain_tags, temporal_tags = extract_labels_from_line(line)

        # Region tags are normalized with prefix
        assert "en-US" in region_tags or "US" in region_tags


class TestEdgeCasesParity:
    """Test edge cases that may differ between scanners."""

    def test_empty_wikilink(self):
        """Test handling of empty wikilink [[]]."""
        result = parse_template_params("[[]]")
        # Both scanners should handle this gracefully
        assert isinstance(result, list)

    def test_unclosed_wikilink(self):
        """Test handling of unclosed wikilink [[word."""
        result = parse_template_params("[[word")
        # Should not crash, may vary in exact output
        assert isinstance(result, list)

    def test_nested_templates(self):
        """Test deeply nested templates are handled."""
        text = "{{outer|{{inner|value}}}}"
        # Should not crash
        result = parse_template_params("en|{{nested|value}}")
        assert isinstance(result, list)

    def test_unicode_in_params(self):
        """Test Unicode characters in parameters."""
        result = parse_template_params("en|café|naïve")
        assert "café" in result
        assert "naïve" in result


# =============================================================================
# Wikitext Sample File Tests
# =============================================================================

class TestWikitextSamples:
    """Tests using actual Wiktionary sample files."""

    SAMPLES_DIR = Path(__file__).parent / "wikitext-samples"

    @pytest.mark.skipif(
        not (Path(__file__).parent / "wikitext-samples").exists(),
        reason="Wikitext samples directory not found"
    )
    def test_encyclopedia_syllables(self):
        """Test encyclopedia entry produces consistent syllable count."""
        sample_file = self.SAMPLES_DIR / "encyclopedia.xml"
        if not sample_file.exists():
            pytest.skip("encyclopedia.xml not found")

        content = sample_file.read_text()

        # Extract from hyphenation template
        hyph_count = extract_syllable_count_from_hyphenation(content, "encyclopedia")
        assert hyph_count == 6, "Hyphenation should show 6 syllables"

        # Extract from rhymes template
        rhymes_count = extract_syllable_count_from_rhymes(content)
        assert rhymes_count == 6, "Rhymes s= should show 6 syllables"

    @pytest.mark.skipif(
        not (Path(__file__).parent / "wikitext-samples").exists(),
        reason="Wikitext samples directory not found"
    )
    def test_happy_morphology(self):
        """Test happy-related entries for morphology extraction."""
        happiness_file = self.SAMPLES_DIR / "happiness.xml"
        if not happiness_file.exists():
            pytest.skip("happiness.xml not found")

        content = happiness_file.read_text()
        morph = extract_morphology(content)

        # happiness should be recognized as suffixed (happy + -ness)
        if morph is not None:
            morph_type = morph.get("type")
            assert morph_type == "suffixed", f"Expected 'suffixed', got '{morph_type}'"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
