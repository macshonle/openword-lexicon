#!/usr/bin/env python3
"""
Tests for build_stats.py - Ensure statistics generation works correctly.
"""

from src.openword.build_stats import compute_statistics


def test_source_combinations_structure():
    """Test that source_combinations includes both count and licenses."""
    # Sample entries with different source combinations
    entries = {
        "word1": {
            "id": "word1",
            "sources": ["wikt"],
            "license_sources": {"CC-BY-SA-4.0": "wikt"},
            "pos": ["NOU"],
            "labels": {},
        },
        "word2": {
            "id": "word2",
            "sources": ["wikt", "wordnet"],
            "license_sources": {"CC-BY-SA-4.0": "wikt", "WordNet": "wordnet"},
            "pos": ["VRB"],
            "labels": {},
        },
        "word3": {
            "id": "word3",
            "sources": ["eowl", "wikt"],
            "license_sources": {"UKACD": "eowl", "CC-BY-SA-4.0": "wikt"},
            "pos": ["NOU"],
            "labels": {},
        },
    }

    stats = compute_statistics(entries)

    # Check structure
    assert "source_combinations" in stats
    assert "wikt" in stats["source_combinations"]
    assert "eowl,wikt" in stats["source_combinations"]
    assert "wikt,wordnet" in stats["source_combinations"]

    # Check each combination has count and licenses
    wikt_combo = stats["source_combinations"]["wikt"]
    assert "count" in wikt_combo
    assert "licenses" in wikt_combo
    assert wikt_combo["count"] == 1
    assert wikt_combo["licenses"] == "CC-BY-SA-4.0"

    eowl_wikt_combo = stats["source_combinations"]["eowl,wikt"]
    assert eowl_wikt_combo["count"] == 1
    assert eowl_wikt_combo["licenses"] == "CC-BY-SA-4.0,UKACD"

    wikt_wordnet_combo = stats["source_combinations"]["wikt,wordnet"]
    assert wikt_wordnet_combo["count"] == 1
    assert wikt_wordnet_combo["licenses"] == "CC-BY-SA-4.0,WordNet"


def test_no_duplicate_license_combinations():
    """Test that license_combinations is NOT in output (removed redundancy)."""
    entries = {
        "word1": {
            "id": "word1",
            "sources": ["wikt"],
            "license_sources": {"CC-BY-SA-4.0": "wikt"},
            "pos": ["NOU"],
            "labels": {},
        },
    }

    stats = compute_statistics(entries)

    # Ensure old license_combinations structure is not present
    assert "license_combinations" not in stats


def test_basic_statistics():
    """Test basic statistics are computed correctly."""
    entries = {
        "word1": {
            "id": "word1",
            "sources": ["wikt"],
            "license_sources": {"CC-BY-SA-4.0": "wikt"},
            "pos": ["NOU"],
            "labels": {"register": ["formal"]},
            "wc": 1,
        },
        "word2": {
            "id": "word2",
            "sources": ["wikt"],
            "license_sources": {"CC-BY-SA-4.0": "wikt"},
            "pos": ["VRB", "NOU"],
            "labels": {},
            "wc": 1,
        },
    }

    stats = compute_statistics(entries)

    # Check total
    assert stats["total_words"] == 2

    # Check sources tracking
    assert stats["sources"]["wikt"] == 2

    # Check metadata coverage
    assert stats["metadata_coverage"]["pos_tags"]["count"] == 2
    assert stats["metadata_coverage"]["pos_tags"]["percentage"] == 100.0

    # Check register labels
    assert stats["metadata_coverage"]["register_labels"]["count"] == 1
    assert stats["metadata_coverage"]["register_labels"]["percentage"] == 50.0


def test_empty_entries():
    """Test handling of empty entries."""
    entries = {}
    stats = compute_statistics(entries)

    assert stats["total_words"] == 0
    assert len(stats["source_combinations"]) == 0
    assert stats["metadata_coverage"]["pos_tags"]["count"] == 0


def test_sorted_by_count():
    """Test that source combinations are sorted by count descending."""
    entries = {
        f"word{i}": {
            "id": f"word{i}",
            "sources": ["wikt"] if i < 10 else ["eowl"],
            "license_sources": {"CC-BY-SA-4.0": "wikt"} if i < 10 else {"UKACD": "eowl"},
            "pos": ["NOU"],
            "labels": {},
        }
        for i in range(15)  # 10 wikt, 5 eowl
    }

    stats = compute_statistics(entries)

    combos = list(stats["source_combinations"].keys())
    counts = [stats["source_combinations"][k]["count"] for k in combos]

    # Verify descending order
    assert counts == sorted(counts, reverse=True)
    # First should be 'wikt' with 10
    assert combos[0] == "wikt"
    assert stats["source_combinations"]["wikt"]["count"] == 10
