# Openword Lexicon Tests

This directory contains the test suite for the Openword Lexicon project.

## Running Tests

```bash
# Run all tests
make test

# Or with uv directly
uv run pytest

# Run specific test file
uv run pytest tests/test_trie_building.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src/openword --cov-report=html
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_trie_building.py` - Tests for MARISA trie creation and querying
- `test_pipeline_smoke.py` - Basic smoke tests for pipeline components

## Test Data

Tests use small, generated datasets (≤100 entries) defined in `conftest.py`:
- `sample_words` - List of 100 animal names for testing
- `sample_metadata` - Corresponding metadata entries

## Coverage

Current test coverage focuses on:
- ✅ Trie building and querying
- ✅ Basic file I/O (JSONL, JSON)
- ✅ Word deduplication and normalization

Future additions:
- Schema validation (when format stabilizes)
- Integration tests for full pipeline
- Performance benchmarks
