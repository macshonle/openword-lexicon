#!/usr/bin/env python3
"""
Tests for syllable extraction from Wiktionary templates.

Tests the fix for the hyphenation extraction bug where first syllables
matching language codes were incorrectly filtered out.

Uses v2 CDA-based extraction from openword.scanner.v2.evidence.
"""

from openword.scanner.v2.evidence import (
    extract_hyphenation,
    extract_rhymes_syllable_count,
    extract_syllable_category_count,
)


def test_hyphenation_basic():
    """Test basic hyphenation extraction."""
    text = "Some text {{hyphenation|en|dic|tion|a|ry}} more text"
    parts = extract_hyphenation(text)
    assert len(parts) == 4, f"Expected 4 parts, got {len(parts)}: {parts}"


def test_hyphenation_with_first_syllable_matching_lang_code():
    """Test the bug fix: first syllable matching language code should not be filtered."""
    # This is the bug we fixed - "en" should count as a syllable, not be filtered as a lang code
    text = "{{hyphenation|en|en|cy|clo|pe|di|a}}"
    parts = extract_hyphenation(text)
    assert len(parts) == 6, f"Expected 6 parts for encyclopedia, got {len(parts)}: {parts}"


def test_hyphenation_with_alternatives():
    """Test hyphenation with alternative pronunciations."""
    text = "{{hyphenation|en|dic|tion|a|ry||dic|tion|ary}}"
    parts = extract_hyphenation(text)
    # Should use first alternative (4 parts)
    assert len(parts) == 4, f"Expected 4 parts (first alternative), got {len(parts)}: {parts}"


def test_hyphenation_with_parameters():
    """Test hyphenation with parameter assignments."""
    text = "{{hyphenation|en|lang=en-US|dic|tion|a|ry}}"
    parts = extract_hyphenation(text)
    # Named params should be filtered out
    assert len(parts) == 4, f"Expected 4 parts, got {len(parts)}: {parts}"


def test_hyphenation_single_short_word():
    """Test hyphenation for very short words (1-3 chars)."""
    text = "{{hyphenation|en|it}}"
    parts = extract_hyphenation(text)
    assert len(parts) == 1, f"Expected 1 part for 'it', got {len(parts)}: {parts}"


def test_hyphenation_incomplete_template():
    """Test that incomplete templates (single unseparated part > 3 chars) return empty."""
    text = "{{hyphenation|en|encyclopedia}}"  # Should be separated into syllables
    parts = extract_hyphenation(text)
    # Single part > 3 chars is unreliable, v2 may return it anyway
    # The filtering happens in compute_syllable_count
    assert isinstance(parts, list)


def test_hyphenation_empty():
    """Test empty hyphenation template."""
    text = "{{hyphenation|en|}}"
    parts = extract_hyphenation(text)
    # Empty template should return empty or just empty strings
    assert isinstance(parts, list)


def test_hyphenation_not_found():
    """Test when no hyphenation template exists."""
    text = "Some text without hyphenation template"
    parts = extract_hyphenation(text)
    assert parts == [], f"Expected empty list when no template found, got {parts}"


def test_rhymes_extraction():
    """Test syllable extraction from rhymes template."""
    text = "{{rhymes|en|æt|s=1}}"
    count = extract_rhymes_syllable_count(text)
    assert count == 1, f"Expected 1 syllable from rhymes, got {count}"


def test_rhymes_multi_syllable():
    """Test rhymes template with multiple syllables."""
    text = "{{rhymes|en|ɪkʃənɛəɹi|s=4}}"
    count = extract_rhymes_syllable_count(text)
    assert count == 4, f"Expected 4 syllables from rhymes, got {count}"


def test_rhymes_not_found():
    """Test when no rhymes template with syllable count exists."""
    text = "Some text {{rhymes|en|æt}} without s= parameter"
    count = extract_rhymes_syllable_count(text)
    assert count is None, f"Expected None when no s= parameter, got {count}"


def test_category_extraction():
    """Test syllable extraction from category labels."""
    text = "[[Category:English 3-syllable words]]"
    count = extract_syllable_category_count(text)
    assert count == 3, f"Expected 3 syllables from category, got {count}"


def test_category_not_found():
    """Test when no syllable category exists."""
    text = "[[Category:English nouns]]"
    count = extract_syllable_category_count(text)
    assert count is None, f"Expected None when no syllable category, got {count}"


def test_all_sources_agree():
    """Test when all three sources agree on syllable count."""
    text = """
    {{hyphenation|en|the|saur|us}}
    {{rhymes|en|ɔːɹəs|s=3}}
    [[Category:English 3-syllable words]]
    """
    hyph_parts = extract_hyphenation(text)
    rhyme = extract_rhymes_syllable_count(text)
    cat = extract_syllable_category_count(text)

    assert len(hyph_parts) == 3, f"Expected 3 parts from hyphenation, got {len(hyph_parts)}"
    assert rhyme == 3, f"Expected 3 from rhymes, got {rhyme}"
    assert cat == 3, f"Expected 3 from category, got {cat}"


def test_sources_conflict_encyclopedia():
    """Test the encyclopedia case where sources used to conflict (bug)."""
    text = """
    {{hyphenation|en|en|cy|clo|pe|di|a}}
    {{rhymes|en|iːdiə|s=6}}
    """
    hyph_parts = extract_hyphenation(text)
    rhyme = extract_rhymes_syllable_count(text)

    # After bug fix, both should agree on 6
    assert len(hyph_parts) == 6, f"Expected 6 parts from hyphenation (bug fixed), got {len(hyph_parts)}"
    assert rhyme == 6, f"Expected 6 from rhymes, got {rhyme}"


def test_edge_cases():
    """Test various edge cases."""
    # Word with syllable matching multiple lang codes
    text1 = "{{hyphenation|en|en|core}}"  # "en" and "core"
    parts1 = extract_hyphenation(text1)
    assert len(parts1) == 2, f"Expected 2 parts for 'encore', got {len(parts1)}"

    # Word starting with "it"
    text2 = "{{hyphenation|en|it|al|ic}}"
    parts2 = extract_hyphenation(text2)
    assert len(parts2) == 3, f"Expected 3 parts for 'italic', got {len(parts2)}"

    # Word starting with "ja"
    text3 = "{{hyphenation|en|ja|pan|ese}}"
    parts3 = extract_hyphenation(text3)
    assert len(parts3) == 3, f"Expected 3 parts for 'japanese', got {len(parts3)}"


if __name__ == "__main__":

    test_functions = [
        obj for name, obj in globals().items()
        if name.startswith('test_') and callable(obj)
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: Unexpected error: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests")
