"""Smoke tests for pipeline components."""
import pytest
import json
from pathlib import Path


def test_sample_metadata_format(sample_metadata):
    """Test that sample metadata has correct structure."""
    assert len(sample_metadata) > 0  # At least some test data

    for entry in sample_metadata:
        # Check required fields
        assert "id" in entry
        assert "pos" in entry
        assert "labels" in entry
        assert "sources" in entry

        # Check types
        assert isinstance(entry["id"], str)
        assert isinstance(entry["pos"], list)
        assert isinstance(entry["labels"], dict)
        assert isinstance(entry["sources"], list)

        # Check id is non-empty
        assert len(entry["id"]) > 0


def test_metadata_to_jsonl(sample_metadata, temp_dir):
    """Test writing metadata to JSONL format."""
    jsonl_path = temp_dir / "test.jsonl"

    # Write JSONL
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for entry in sample_metadata:
            f.write(json.dumps(entry, sort_keys=True) + '\n')

    # Verify file
    assert jsonl_path.exists()

    # Read back and verify
    entries_read = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            entries_read.append(json.loads(line))

    assert len(entries_read) == len(sample_metadata)
    assert entries_read == sample_metadata


def test_metadata_to_json_array(sample_metadata, temp_dir):
    """Test writing metadata to JSON array format."""
    json_path = temp_dir / "test.meta.json"

    # Write JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(sample_metadata, f, indent=2, ensure_ascii=False)

    # Verify file
    assert json_path.exists()

    # Read back and verify
    with open(json_path, 'r', encoding='utf-8') as f:
        entries_read = json.load(f)

    assert len(entries_read) == len(sample_metadata)
    assert entries_read == sample_metadata


def test_word_deduplication(sample_words):
    """Test that words are properly deduplicated."""
    words_with_dupes = sample_words + sample_words[:10]  # Add some duplicates

    # Deduplicate
    unique_words = list(dict.fromkeys(words_with_dupes))  # Preserves order

    assert len(unique_words) == len(sample_words)
    assert set(unique_words) == set(sample_words)


def test_word_normalization():
    """Test basic word normalization operations."""
    test_cases = [
        ("HELLO", "hello"),  # Lowercase
        ("  word  ", "word"),  # Strip whitespace
        ("hello\nworld", "hello"),  # Split on newline (take first)
    ]

    for input_word, expected in test_cases:
        normalized = input_word.strip().lower().split()[0]
        assert normalized == expected
