"""
Integration tests for syllable filtering with owlex.

Tests end-to-end syllable filtering through the OwlexFilter class
to verify that the refactored code correctly delegates to filters.py
and produces expected results.
"""

import json
import tempfile
from pathlib import Path
from openword.owlex import OwlexFilter


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
