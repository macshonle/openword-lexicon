#!/usr/bin/env python3
"""
Tests for syllable filtering in wordlist generation.

Tests the syllable filtering functionality in both filters.py and owlex.py.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openword.filters import matches_syllables


def test_exact_syllables():
    """Test exact syllable count filtering."""
    entry_2syl = {"id": "table", "nsyll": 2}
    entry_3syl = {"id": "dictionary", "nsyll": 4}
    entry_none = {"id": "unknown", "nsyll": None}

    # Exact match
    assert matches_syllables(entry_2syl, exact_syllables=2)
    assert not matches_syllables(entry_3syl, exact_syllables=2)

    # Without require_syllables, None is excluded when filter is active
    assert not matches_syllables(entry_none, exact_syllables=2)

    # With require_syllables=True, None is also excluded
    assert not matches_syllables(entry_none, exact_syllables=2, require_syllables=True)


def test_min_syllables():
    """Test minimum syllable count filtering."""
    entry_1syl = {"id": "cat", "nsyll": 1}
    entry_2syl = {"id": "table", "nsyll": 2}
    entry_4syl = {"id": "dictionary", "nsyll": 4}
    entry_none = {"id": "unknown", "nsyll": None}

    # Min filter
    assert not matches_syllables(entry_1syl, min_syllables=2)
    assert matches_syllables(entry_2syl, min_syllables=2)
    assert matches_syllables(entry_4syl, min_syllables=2)

    # None is excluded when filter is active
    assert not matches_syllables(entry_none, min_syllables=2)


def test_max_syllables():
    """Test maximum syllable count filtering."""
    entry_1syl = {"id": "cat", "nsyll": 1}
    entry_2syl = {"id": "table", "nsyll": 2}
    entry_4syl = {"id": "dictionary", "nsyll": 4}
    entry_none = {"id": "unknown", "nsyll": None}

    # Max filter
    assert matches_syllables(entry_1syl, max_syllables=2)
    assert matches_syllables(entry_2syl, max_syllables=2)
    assert not matches_syllables(entry_4syl, max_syllables=2)

    # None is excluded when filter is active
    assert not matches_syllables(entry_none, max_syllables=2)


def test_range_syllables():
    """Test syllable range filtering (min and max together)."""
    entry_1syl = {"id": "cat", "nsyll": 1}
    entry_2syl = {"id": "table", "nsyll": 2}
    entry_3syl = {"id": "elephant", "nsyll": 3}
    entry_4syl = {"id": "dictionary", "nsyll": 4}

    # Range: 2-3 syllables
    assert not matches_syllables(entry_1syl, min_syllables=2, max_syllables=3)
    assert matches_syllables(entry_2syl, min_syllables=2, max_syllables=3)
    assert matches_syllables(entry_3syl, min_syllables=2, max_syllables=3)
    assert not matches_syllables(entry_4syl, min_syllables=2, max_syllables=3)


def test_require_syllables():
    """Test require_syllables flag."""
    entry_with = {"id": "table", "nsyll": 2}
    entry_without = {"id": "unknown", "nsyll": None}

    # require_syllables=True excludes entries without data
    assert matches_syllables(entry_with, require_syllables=True)
    assert not matches_syllables(entry_without, require_syllables=True)

    # require_syllables=False includes entries without data if no other filter
    assert matches_syllables(entry_with, require_syllables=False)
    assert matches_syllables(entry_without, require_syllables=False)


def test_no_filters():
    """Test that entries pass when no syllable filters are specified."""
    entry_with = {"id": "table", "nsyll": 2}
    entry_without = {"id": "unknown", "nsyll": None}

    # No filters = all pass
    assert matches_syllables(entry_with)
    assert matches_syllables(entry_without)


def test_exact_takes_precedence():
    """Test that exact filter takes precedence over min/max."""
    entry_2syl = {"id": "table", "nsyll": 2}
    entry_3syl = {"id": "elephant", "nsyll": 3}

    # Exact=2 should override min/max
    assert matches_syllables(entry_2syl, exact_syllables=2, min_syllables=1, max_syllables=3)
    assert not matches_syllables(entry_3syl, exact_syllables=2, min_syllables=1, max_syllables=3)


def test_safe_defaults():
    """Test safe default behavior: missing data is excluded when filters are active."""
    entry_none = {"id": "unknown", "nsyll": None}

    # Any active filter excludes None (safe default)
    assert not matches_syllables(entry_none, min_syllables=1)
    assert not matches_syllables(entry_none, max_syllables=5)
    assert not matches_syllables(entry_none, exact_syllables=2)
    assert not matches_syllables(entry_none, require_syllables=True)

    # No filters = include None
    assert matches_syllables(entry_none)


def test_children_word_game_use_case():
    """Test the children's word game use case: 2-syllable words only."""
    words = [
        {"id": "cat", "nsyll": 1},
        {"id": "table", "nsyll": 2},
        {"id": "button", "nsyll": 2},
        {"id": "elephant", "nsyll": 3},
        {"id": "unknown", "nsyll": None},
    ]

    # Filter for exact 2 syllables, require data
    filtered = [
        w for w in words
        if matches_syllables(w, exact_syllables=2, require_syllables=True)
    ]

    assert len(filtered) == 2
    assert filtered[0]["id"] == "table"
    assert filtered[1]["id"] == "button"


def test_poetry_meter_use_case():
    """Test poetry meter use case: 3-5 syllable words."""
    words = [
        {"id": "cat", "nsyll": 1},
        {"id": "table", "nsyll": 2},
        {"id": "elephant", "nsyll": 3},
        {"id": "dictionary", "nsyll": 4},
        {"id": "encyclopedia", "nsyll": 6},
        {"id": "unknown", "nsyll": None},
    ]

    # Filter for 3-5 syllables
    filtered = [
        w for w in words
        if matches_syllables(w, min_syllables=3, max_syllables=5)
    ]

    assert len(filtered) == 2
    assert filtered[0]["id"] == "elephant"
    assert filtered[1]["id"] == "dictionary"


def test_simple_words_use_case():
    """Test simple words use case: 1-3 syllables for reading practice."""
    words = [
        {"id": "cat", "nsyll": 1},
        {"id": "table", "nsyll": 2},
        {"id": "elephant", "nsyll": 3},
        {"id": "dictionary", "nsyll": 4},
        {"id": "simple", "nsyll": None},  # No data, but not filtered if no require
    ]

    # Filter for 1-3 syllables, but allow missing data
    filtered = [
        w for w in words
        if matches_syllables(w, min_syllables=1, max_syllables=3)
    ]

    # Should include cat, table, elephant (1-3 syllables with data)
    # Should exclude dictionary (4 syllables)
    # Should exclude simple (no data, filter is active)
    assert len(filtered) == 3
    assert filtered[0]["id"] == "cat"
    assert filtered[1]["id"] == "table"
    assert filtered[2]["id"] == "elephant"


if __name__ == "__main__":
    # Run all tests
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
