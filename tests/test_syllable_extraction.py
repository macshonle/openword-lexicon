#!/usr/bin/env python3
"""
Tests for syllable extraction from Wiktionary templates.

Tests the fix for the hyphenation extraction bug where first syllables
matching language codes were incorrectly filtered out.
"""

import sys
from pathlib import Path

# Add legacy scanner_v1 directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "legacy" / "scanner_v1"))

from wiktionary_scanner_python.scanner import (
    extract_syllable_count_from_hyphenation,
    extract_syllable_count_from_rhymes,
    extract_syllable_count_from_categories,
)


def test_hyphenation_basic():
    """Test basic hyphenation extraction."""
    text = "Some text {{hyphenation|en|dic|tion|a|ry}} more text"
    count = extract_syllable_count_from_hyphenation(text, "dictionary")
    assert count == 4, f"Expected 4 syllables, got {count}"


def test_hyphenation_with_first_syllable_matching_lang_code():
    """Test the bug fix: first syllable matching language code should not be filtered."""
    # This is the bug we fixed - "en" should count as a syllable, not be filtered as a lang code
    text = "{{hyphenation|en|en|cy|clo|pe|di|a}}"
    count = extract_syllable_count_from_hyphenation(text, "encyclopedia")
    assert count == 6, f"Expected 6 syllables for encyclopedia, got {count}"


def test_hyphenation_with_alternatives():
    """Test hyphenation with alternative pronunciations."""
    text = "{{hyphenation|en|dic|tion|a|ry||dic|tion|ary}}"
    count = extract_syllable_count_from_hyphenation(text, "dictionary")
    assert count == 4, f"Expected 4 syllables (using first alternative), got {count}"


def test_hyphenation_with_parameters():
    """Test hyphenation with parameter assignments."""
    text = "{{hyphenation|en|lang=en-US|dic|tion|a|ry}}"
    count = extract_syllable_count_from_hyphenation(text, "dictionary")
    assert count == 4, f"Expected 4 syllables (filtering parameters), got {count}"


def test_hyphenation_single_short_word():
    """Test hyphenation for very short words (1-3 chars)."""
    text = "{{hyphenation|en|it}}"
    count = extract_syllable_count_from_hyphenation(text, "it")
    assert count == 1, f"Expected 1 syllable for 'it', got {count}"


def test_hyphenation_incomplete_template():
    """Test that incomplete templates (single unseparated part > 3 chars) return None."""
    text = "{{hyphenation|en|encyclopedia}}"  # Should be separated into syllables
    count = extract_syllable_count_from_hyphenation(text, "encyclopedia")
    assert count is None, f"Expected None for incomplete template, got {count}"


def test_hyphenation_empty():
    """Test empty hyphenation template."""
    text = "{{hyphenation|en|}}"
    count = extract_syllable_count_from_hyphenation(text, "test")
    assert count is None, f"Expected None for empty template, got {count}"


def test_hyphenation_not_found():
    """Test when no hyphenation template exists."""
    text = "Some text without hyphenation template"
    count = extract_syllable_count_from_hyphenation(text, "test")
    assert count is None, f"Expected None when no template found, got {count}"


def test_rhymes_extraction():
    """Test syllable extraction from rhymes template."""
    text = "{{rhymes|en|æt|s=1}}"
    count = extract_syllable_count_from_rhymes(text)
    assert count == 1, f"Expected 1 syllable from rhymes, got {count}"


def test_rhymes_multi_syllable():
    """Test rhymes template with multiple syllables."""
    text = "{{rhymes|en|ɪkʃənɛəɹi|s=4}}"
    count = extract_syllable_count_from_rhymes(text)
    assert count == 4, f"Expected 4 syllables from rhymes, got {count}"


def test_rhymes_not_found():
    """Test when no rhymes template with syllable count exists."""
    text = "Some text {{rhymes|en|æt}} without s= parameter"
    count = extract_syllable_count_from_rhymes(text)
    assert count is None, f"Expected None when no s= parameter, got {count}"


def test_category_extraction():
    """Test syllable extraction from category labels."""
    text = "[[Category:English 3-syllable words]]"
    count = extract_syllable_count_from_categories(text)
    assert count == 3, f"Expected 3 syllables from category, got {count}"


def test_category_not_found():
    """Test when no syllable category exists."""
    text = "[[Category:English nouns]]"
    count = extract_syllable_count_from_categories(text)
    assert count is None, f"Expected None when no syllable category, got {count}"


def test_all_sources_agree():
    """Test when all three sources agree on syllable count."""
    text = """
    {{hyphenation|en|the|saur|us}}
    {{rhymes|en|ɔːɹəs|s=3}}
    [[Category:English 3-syllable words]]
    """
    hyph = extract_syllable_count_from_hyphenation(text, "thesaurus")
    rhyme = extract_syllable_count_from_rhymes(text)
    cat = extract_syllable_count_from_categories(text)

    assert hyph == 3, f"Expected 3 from hyphenation, got {hyph}"
    assert rhyme == 3, f"Expected 3 from rhymes, got {rhyme}"
    assert cat == 3, f"Expected 3 from category, got {cat}"


def test_sources_conflict_encyclopedia():
    """Test the encyclopedia case where sources used to conflict (bug)."""
    text = """
    {{hyphenation|en|en|cy|clo|pe|di|a}}
    {{rhymes|en|iːdiə|s=6}}
    """
    hyph = extract_syllable_count_from_hyphenation(text, "encyclopedia")
    rhyme = extract_syllable_count_from_rhymes(text)

    # After bug fix, both should agree on 6
    assert hyph == 6, f"Expected 6 from hyphenation (bug fixed), got {hyph}"
    assert rhyme == 6, f"Expected 6 from rhymes, got {rhyme}"


def test_edge_cases():
    """Test various edge cases."""
    # Word with syllable matching multiple lang codes
    text1 = "{{hyphenation|en|en|core}}"  # "en" and "core"
    count1 = extract_syllable_count_from_hyphenation(text1, "encore")
    assert count1 == 2, f"Expected 2 syllables for 'encore', got {count1}"

    # Word starting with "it"
    text2 = "{{hyphenation|en|it|al|ic}}"
    count2 = extract_syllable_count_from_hyphenation(text2, "italic")
    assert count2 == 3, f"Expected 3 syllables for 'italic', got {count2}"

    # Word starting with "ja"
    text3 = "{{hyphenation|en|ja|pan|ese}}"
    count3 = extract_syllable_count_from_hyphenation(text3, "japanese")
    assert count3 == 3, f"Expected 3 syllables for 'japanese', got {count3}"


if __name__ == "__main__":
    # Run all tests
    import inspect

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
    sys.exit(0 if failed == 0 else 1)
