"""Tests for trie building and querying functionality."""
import pytest
import marisa_trie
from pathlib import Path


def test_trie_creation_and_basic_operations(sample_words, temp_dir):
    """Test creating a trie and basic operations."""
    # Create trie
    trie = marisa_trie.Trie(sample_words)

    # Test membership
    assert "cat" in trie
    assert "dog" in trie
    assert "elephant" in trie
    assert "notaword" not in trie

    # Test size
    assert len(trie) == len(sample_words)

    # Test iteration
    all_words = list(trie)
    assert len(all_words) == len(sample_words)
    assert set(all_words) == set(sample_words)


def test_trie_save_and_load(sample_words, temp_dir):
    """Test saving and loading a trie."""
    trie_path = temp_dir / "test.trie"

    # Create and save trie
    trie = marisa_trie.Trie(sample_words)
    trie.save(str(trie_path))

    # Verify file exists
    assert trie_path.exists()
    assert trie_path.stat().st_size > 0

    # Load trie
    loaded_trie = marisa_trie.Trie()
    loaded_trie.load(str(trie_path))

    # Verify loaded trie works
    assert "cat" in loaded_trie
    assert "dog" in loaded_trie
    assert len(loaded_trie) == len(sample_words)


def test_trie_prefix_search(sample_words):
    """Test prefix search functionality."""
    trie = marisa_trie.Trie(sample_words)

    # Search for words starting with 'c'
    c_words = list(trie.keys("c"))
    assert "cat" in c_words
    assert "cow" in c_words
    assert "crow" in c_words
    assert "dog" not in c_words

    # Search for words starting with 'el'
    el_words = list(trie.keys("el"))
    assert "elephant" in el_words
    assert len(el_words) >= 1  # At least elephant

    # Empty prefix returns all words
    all_words = list(trie.keys(""))
    assert len(all_words) == len(sample_words)


def test_trie_with_empty_list():
    """Test trie creation with empty word list."""
    trie = marisa_trie.Trie([])
    assert len(trie) == 0
    assert "anything" not in trie


def test_trie_with_duplicates(sample_words):
    """Test trie handles duplicates correctly."""
    # Add duplicates
    words_with_dupes = sample_words + ["cat", "dog", "cat"]

    trie = marisa_trie.Trie(words_with_dupes)

    # Trie should automatically deduplicate
    assert len(trie) == len(sample_words)
    assert "cat" in trie


def test_trie_case_sensitivity():
    """Test that trie is case-sensitive."""
    words = ["Cat", "cat", "CAT"]
    trie = marisa_trie.Trie(words)

    assert "Cat" in trie
    assert "cat" in trie
    assert "CAT" in trie
    assert "cAt" not in trie


def test_trie_special_characters():
    """Test trie with special characters and phrases."""
    words = ["hello-world", "don't", "it's", "test phrase"]
    trie = marisa_trie.Trie(words)

    assert "hello-world" in trie
    assert "don't" in trie
    assert "it's" in trie
    assert "test phrase" in trie


def test_trie_ordering(sample_words):
    """Test that trie maintains consistent order."""
    trie = marisa_trie.Trie(sample_words)

    all_words = list(trie)
    # Trie should return all words consistently
    assert len(all_words) == len(sample_words)
    assert set(all_words) == set(sample_words)


def test_trie_with_unicode():
    """Test trie with Unicode characters."""
    words = ["café", "naïve", "résumé", "日本語"]
    trie = marisa_trie.Trie(words)

    assert "café" in trie
    assert "naïve" in trie
    assert "résumé" in trie
    assert "日本語" in trie
    assert len(trie) == 4
