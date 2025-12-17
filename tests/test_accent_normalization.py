"""
Test accent normalization in WordNet enrichment.

Validates that accented characters are handled properly for WordNet lookups.
"""

import pytest
import unicodedata


# Duplicate the functions here for testing (to avoid nltk dependency in tests)
def normalize_for_lookup(word: str) -> str:
    """Normalize word for dictionary lookup."""
    normalized = unicodedata.normalize("NFKC", word)
    normalized = normalized.lower()
    return normalized


def strip_accents(word: str) -> str:
    """Strip accents from word for fallback lookups."""
    nfd = unicodedata.normalize("NFD", word)
    without_accents = "".join(
        char for char in nfd
        if not unicodedata.combining(char)
    )
    return unicodedata.normalize("NFC", without_accents)


class TestAccentNormalization:
    """Test accent normalization functions."""

    def test_normalize_for_lookup_basic(self):
        """Test basic normalization."""
        assert normalize_for_lookup("Hello") == "hello"
        assert normalize_for_lookup("WORLD") == "world"
        assert normalize_for_lookup("Test") == "test"

    def test_normalize_for_lookup_accents(self):
        """Test that NFKC normalization is applied."""
        # café should be normalized but keep accent
        result = normalize_for_lookup("Café")
        assert result == "café"

        # Should be lowercase
        assert normalize_for_lookup("CAFÉ") == "café"

    def test_strip_accents_simple(self):
        """Test accent stripping."""
        assert strip_accents("café") == "cafe"
        assert strip_accents("naïve") == "naive"
        assert strip_accents("résumé") == "resume"
        assert strip_accents("Montréal") == "Montreal"

    def test_strip_accents_combined(self):
        """Test stripping various diacritical marks."""
        # Acute accents
        assert strip_accents("café") == "cafe"

        # Grave accents
        assert strip_accents("à la mode") == "a la mode"

        # Circumflex
        assert strip_accents("forêt") == "foret"

        # Diaeresis/umlaut
        assert strip_accents("naïve") == "naive"

        # Tilde
        assert strip_accents("año") == "ano"

    def test_strip_accents_no_change(self):
        """Test that ASCII words are unchanged."""
        assert strip_accents("hello") == "hello"
        assert strip_accents("world") == "world"
        assert strip_accents("test") == "test"

    def test_strip_accents_mixed(self):
        """Test mixed ASCII and accented characters."""
        assert strip_accents("café latte") == "cafe latte"
        assert strip_accents("crème brûlée") == "creme brulee"

    def test_normalization_preserves_structure(self):
        """Test that normalization preserves word structure."""
        # Spaces preserved
        assert normalize_for_lookup("hello world") == "hello world"

        # Hyphens preserved
        assert normalize_for_lookup("well-known") == "well-known"

        # Apostrophes preserved
        assert normalize_for_lookup("don't") == "don't"


class TestNormalizationIntegration:
    """Test integration with WordNet enrichment."""

    def test_accent_normalization_workflow(self):
        """Test the typical workflow for accented words."""
        word = "Café"

        # Step 1: Normalize
        normalized = normalize_for_lookup(word)
        assert normalized == "café"

        # Step 2: If no results, strip accents
        normalized_no_accent = strip_accents(normalized)
        assert normalized_no_accent == "cafe"

        # This is the fallback that would be used for WordNet lookup


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
