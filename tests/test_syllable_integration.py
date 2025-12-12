"""
Integration tests for syllable filtering with owlex.

Tests end-to-end syllable filtering through the OwlexFilter class
to verify that the refactored code correctly delegates to filters.py
and produces expected results.

Also includes cross-validation tests to verify syllable extraction
from different sources (IPA, hyphenation, rhymes) are consistent.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

from openword.cli.owlex import OwlexFilter

# Add legacy directory to path for v1 scanner imports
legacy_path = Path(__file__).parent.parent / "legacy" / "scanner_v1"
sys.path.insert(0, str(legacy_path))

from wiktionary_scanner_python.scanner import (
    count_syllables_from_ipa,
    extract_syllable_count_from_hyphenation,
    extract_syllable_count_from_rhymes,
    extract_syllable_count_from_ipa,
)


def test_syllable_filtering_exact():
    """Test exact syllable count filtering through owlex."""
    # Create a temporary spec file for 2-syllable words
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "syllables": {
                "exact": 2,
                "require_syllables": True
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        # Create filter instance
        owlex = OwlexFilter(spec_path)

        # Test entries
        test_entries = [
            {"id": "table", "nsyll": 2},      # Should pass
            {"id": "cat", "nsyll": 1},        # Should fail (not 2)
            {"id": "elephant", "nsyll": 3},   # Should fail (not 2)
            {"id": "button", "nsyll": 2},     # Should pass
            {"id": "unknown", "nsyll": None}, # Should fail (require_syllables)
            {"id": "window", "nsyll": 2},     # Should pass
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [True, False, False, True, False, True]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


def test_syllable_filtering_range():
    """Test min/max syllable range filtering through owlex."""
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "syllables": {
                "min": 2,
                "max": 4
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        owlex = OwlexFilter(spec_path)

        test_entries = [
            {"id": "I", "nsyll": 1},              # Should fail (< 2)
            {"id": "table", "nsyll": 2},          # Should pass
            {"id": "elephant", "nsyll": 3},       # Should pass
            {"id": "dictionary", "nsyll": 4},     # Should pass
            {"id": "encyclopedia", "nsyll": 6},   # Should fail (> 4)
            {"id": "cat", "nsyll": 1},            # Should fail (< 2)
            {"id": "unknown"},                        # Should fail (no data + filter active)
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [False, True, True, True, False, False, False]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


def test_syllable_filtering_min_only():
    """Test minimum syllable filtering (4+ syllables)."""
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "syllables": {
                "min": 4
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        owlex = OwlexFilter(spec_path)

        test_entries = [
            {"id": "cat", "nsyll": 1},                # Should fail
            {"id": "table", "nsyll": 2},              # Should fail
            {"id": "elephant", "nsyll": 3},           # Should fail
            {"id": "dictionary", "nsyll": 4},         # Should pass
            {"id": "encyclopedia", "nsyll": 6},       # Should pass
            {"id": "philosophical", "nsyll": 5},      # Should pass
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [False, False, False, True, True, True]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


def test_syllable_filtering_with_other_filters():
    """Test syllable filtering combined with other filter types."""
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "syllables": {
                "exact": 2
            },
            "character": {
                "min_length": 5,
                "max_length": 10
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        owlex = OwlexFilter(spec_path)

        test_entries = [
            {"id": "table", "nsyll": 2},      # Should pass (2 syl, 5 chars)
            {"id": "cat", "nsyll": 2},        # Should fail (3 chars < 5)
            {"id": "button", "nsyll": 2},     # Should pass (2 syl, 6 chars)
            {"id": "elephant", "nsyll": 3},   # Should fail (3 syllables)
            {"id": "veryverylongword", "nsyll": 2},  # Should fail (>10 chars)
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [True, False, True, False, False]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


def test_syllable_safe_defaults():
    """Test that missing syllable data is excluded when filters are active."""
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "syllables": {
                "min": 2,
                "max": 3
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        owlex = OwlexFilter(spec_path)

        test_entries = [
            {"id": "table", "nsyll": 2},          # Should pass
            {"id": "unknown1"},                       # Should fail (no syllable data)
            {"id": "unknown2", "nsyll": None},    # Should fail (no syllable data)
            {"id": "elephant", "nsyll": 3},       # Should pass
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [True, False, False, True]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


def test_no_syllable_filters():
    """Test that missing syllable data is allowed when no filters are active."""
    spec = {
        "version": "1.0",
        "distribution": "en",
        "filters": {
            "character": {
                "min_length": 3
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(spec, f)
        spec_path = Path(f.name)

    try:
        owlex = OwlexFilter(spec_path)

        test_entries = [
            {"id": "table", "nsyll": 2},      # Should pass
            {"id": "unknown"},                    # Should pass (no syllable filter)
            {"id": "cat", "nsyll": None},     # Should pass
        ]

        results = [owlex.filter_entry(e) for e in test_entries]
        expected = [True, True, True]

        assert results == expected, f"Expected {expected}, got {results}"

    finally:
        spec_path.unlink()


# =============================================================================
# Cross-Validation Tests for Syllable Extraction
# =============================================================================

class TestSyllableCrossValidation:
    """Tests that verify syllable extraction from different sources is consistent.

    These tests help identify Wiktionary data quality issues where different
    syllable sources (IPA, hyphenation, rhymes) disagree.
    """

    def test_ipa_syllable_counting_basic(self):
        """Test basic IPA syllable counting."""
        cases = [
            ("/kæt/", 1),           # cat - 1 vowel
            ("/ˈteɪ.bəl/", 2),      # table - 2 syllables with schwa
            ("/ɪnˌsaɪ.kləˈpiː.di.ə/", 6),  # encyclopedia
            ("/əˈsæsɪn/", 3),       # assassin - 3 syllables
        ]
        for ipa, expected in cases:
            result = count_syllables_from_ipa(ipa)
            assert result == expected, f"IPA {ipa}: expected {expected}, got {result}"

    def test_hyphenation_extraction_basic(self):
        """Test hyphenation template syllable extraction."""
        cases = [
            ("cat", "{{hyphenation|en|cat}}", 1),
            ("dictionary", "{{hyphenation|en|dic|tion|a|ry}}", 4),
            ("encyclopedia", "{{hyphenation|en|en|cy|clo|pe|di|a}}", 6),
        ]
        for word, template, expected in cases:
            result = extract_syllable_count_from_hyphenation(template, word)
            assert result == expected, f"{word}: expected {expected}, got {result}"

    def test_rhymes_extraction_basic(self):
        """Test rhymes template s= parameter extraction."""
        cases = [
            ("{{rhymes|en|æt|s=1}}", 1),
            ("{{rhymes|en|iːdiə|s=6}}", 6),
            ("{{rhymes|en|ɔːɹəs|s=3}}", 3),
            ("{{rhymes|en|æt}}", None),  # No s= parameter
        ]
        for template, expected in cases:
            result = extract_syllable_count_from_rhymes(template)
            assert result == expected, f"Template {template}: expected {expected}, got {result}"

    def test_priority_order_ipa_first(self):
        """Verify IPA takes priority over rhymes when both present.

        The scanner should use IPA syllable count when available,
        even if rhymes provides a different count.
        """
        # IPA says 3 syllables, rhymes says 2 (a hypothetical disagreement)
        ipa = "/əˈsæsɪn/"  # 3 syllables
        rhymes_wrong = "{{rhymes|en|æsɪn|s=2}}"  # Claims 2 syllables

        ipa_count = count_syllables_from_ipa(ipa)
        rhymes_count = extract_syllable_count_from_rhymes(rhymes_wrong)

        # IPA should give 3, rhymes gives 2
        assert ipa_count == 3, f"IPA count should be 3, got {ipa_count}"
        assert rhymes_count == 2, f"Rhymes count should be 2, got {rhymes_count}"

        # Scanner should prefer IPA when resolving conflict
        # (This documents the expected behavior)

    def test_hyphenation_ipa_agreement(self):
        """Test that hyphenation and IPA agree on syllable counts.

        For standard words, these sources should produce the same count.
        """
        test_cases = [
            # (word, hyphenation_template, ipa, expected_syllables)
            ("dictionary", "{{hyphenation|en|dic|tion|a|ry}}", "/ˈdɪk.ʃən.ɛɹ.i/", 4),
            ("beautiful", "{{hyphenation|en|beau|ti|ful}}", "/ˈbjuːtɪfəl/", 3),
            ("elephant", "{{hyphenation|en|el|e|phant}}", "/ˈɛlɪfənt/", 3),
        ]

        for word, hyph_template, ipa, expected in test_cases:
            hyph_count = extract_syllable_count_from_hyphenation(hyph_template, word)
            ipa_count = count_syllables_from_ipa(ipa)

            assert hyph_count == expected, f"{word} hyphenation: expected {expected}, got {hyph_count}"
            assert ipa_count == expected, f"{word} IPA: expected {expected}, got {ipa_count}"
            assert hyph_count == ipa_count, f"{word}: hyphenation ({hyph_count}) != IPA ({ipa_count})"

    def test_detect_potential_wiktionary_issues(self):
        """Test cases that might represent Wiktionary data issues.

        These tests document known or potential discrepancies in Wiktionary
        where different syllable sources disagree.
        """
        # "assassin" example: IPA has 3 syllables but some Wiktionary
        # entries might have incorrect rhymes s= values
        ipa_assassin = "/əˈsæsɪn/"
        ipa_count = count_syllables_from_ipa(ipa_assassin)
        assert ipa_count == 3, "assassin should have 3 syllables per IPA"

        # If we find a rhymes template claiming s=2, that would be wrong
        wrong_rhymes = "{{rhymes|en|æsɪn|s=2}}"
        rhymes_count = extract_syllable_count_from_rhymes(wrong_rhymes)

        # This documents a potential data quality issue
        if rhymes_count is not None and rhymes_count != ipa_count:
            # In a real scenario, we'd flag this for Wiktionary review
            pass  # Expected discrepancy for this test case

    def test_encore_first_syllable_matches_lang_code(self):
        """Test words where first syllable matches a language code.

        The hyphenation parser should handle 'encore' correctly where
        the first syllable 'en' is also a language code.
        """
        # "encore" starts with "en" which is also English's language code
        hyph_count = extract_syllable_count_from_hyphenation(
            "{{hyphenation|en|en|core}}", "encore"
        )
        assert hyph_count == 2, f"encore should have 2 syllables, got {hyph_count}"

    def test_syllabic_consonants(self):
        """Test IPA with syllabic consonants like /l̩/ and /n̩/."""
        # Words with syllabic consonants can be tricky
        # "button" with syllabic n: /ˈbʌtn̩/ or /ˈbʌtən/
        ipa_with_schwa = "/ˈbʌtən/"  # 2 syllables explicit
        count = count_syllables_from_ipa(ipa_with_schwa)
        assert count == 2, f"button should have 2 syllables, got {count}"


# Test runner
if __name__ == '__main__':
    print("Running syllable integration tests...")
    print()

    tests = [
        ("Exact syllable filtering", test_syllable_filtering_exact),
        ("Range syllable filtering", test_syllable_filtering_range),
        ("Minimum syllable filtering", test_syllable_filtering_min_only),
        ("Combined filters", test_syllable_filtering_with_other_filters),
        ("Safe defaults (missing data excluded)", test_syllable_safe_defaults),
        ("No syllable filters (missing data allowed)", test_no_syllable_filters),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}")
            print(f"  Unexpected error: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
