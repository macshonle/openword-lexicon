# WordNet Enrichment Test Suite

Comprehensive test suite for WordNet enrichment, designed to support the migration from NLTK's WordNet to the `wn` library with OEWN 2024.

## Purpose

1. **Baseline Documentation**: Capture current NLTK-based enrichment behavior
2. **Edge Case Coverage**: Test unusual inputs, modern words, special characters
3. **Bug Detection**: Find issues in current implementation
4. **Regression Prevention**: Ensure `wn` library migration doesn't break functionality
5. **Future Developer Documentation**: Serve as examples and edge case reference

## Test Structure

### Test Files

- `test_wordnet_enrichment.py` - Main test suite
  - `TestNLTKConcreteness` - Concreteness classification tests
  - `TestNLTKPOSTagging` - Part-of-speech detection tests
  - `TestNLTKEdgeCases` - Edge cases and unusual inputs
  - `TestNLTKFullEnrichment` - End-to-end enrichment pipeline tests
  - `TestWordNetAvailability` - Infrastructure verification

- `conftest_wordnet.py` - Custom pytest configuration for detailed reporting
- `run_wordnet_tests.sh` - Test runner with output capture

### Test Categories

#### Concrete Nouns
Words that should be classified as `concrete`:
- castle, apple, hammer, dog, table, water, mountain, book, car, tree, chair, stone

#### Abstract Nouns
Words that should be classified as `abstract`:
- freedom, justice, happiness, love, theory, democracy, philosophy, courage, wisdom, beauty

#### Mixed Nouns
Words with both concrete and abstract senses:
- paper, bank, culture, light, power, form, matter, spirit, nature, value

#### Edge Cases
- Nonexistent words (should handle gracefully)
- Single letters (a, I)
- Modern neologisms (selfie, cryptocurrency, COVID-19)
- Accented characters (café, naïve, résumé)
- Multi-word phrases (give up, kick the bucket)
- Abbreviations (OK)

#### Multiple POS
Words that function as multiple parts of speech:
- light (noun, verb, adjective)
- run (noun, verb)
- fast (adjective, adverb, noun, verb)
- well (adverb, adjective, noun)
- back (noun, verb, adjective, adverb)

## Running Tests

### Quick Run

```bash
# Run all WordNet tests
pytest tests/test_wordnet_enrichment.py -v

# Run specific test class
pytest tests/test_wordnet_enrichment.py::TestNLTKConcreteness -v

# Run with detailed traceback
pytest tests/test_wordnet_enrichment.py -v --tb=long
```

### Full Run with Output Capture

```bash
# Generate both human-readable and JSON outputs
bash tests/run_wordnet_tests.sh
```

This produces:
- `tests/wordnet_test_results.txt` - Human-readable output
- `tests/wordnet_test_detailed_results.json` - Machine-readable results

### Direct Python Execution

```bash
# Run the test file directly
uv run python tests/test_wordnet_enrichment.py
```

## Test Output Format

### Console Output

- **PASS**: Expected behavior
- **WARN**: Unexpected but acceptable (documented)
- **UNEXPECTED**: Different from expected (may indicate bug)
- **ERROR**: Exception raised (definite bug)
- **EXPECTED**: Known behavior for edge cases

### JSON Results (`wordnet_test_detailed_results.json`)

```json
{
  "start_time": "2024-11-20T17:00:00.000Z",
  "end_time": "2024-11-20T17:00:30.000Z",
  "duration_seconds": 30.5,
  "exit_status": 0,
  "python_version": "3.11.x",
  "test_count": 45,
  "passed": 40,
  "failed": 2,
  "skipped": 3,
  "results": [
    {
      "test_id": "tests/test_wordnet_enrichment.py::TestNLTKConcreteness::test_concrete_nouns",
      "outcome": "passed",
      "duration": 0.123,
      "keywords": ["test", "nltk", "concreteness"],
      "output": {...}
    }
  ]
}
```

### Text Results (`wordnet_test_results.txt`)

Full pytest output with:
- Test names and outcomes
- Assertion details
- Stack traces for failures
- Print statements and logging

## Adding New Tests

### Example Test

```python
def test_my_feature(nltk_wordnet):
    """Test description."""
    result = TestResult("my_test_name")
    result.word = "test_word"

    try:
        output = get_concreteness("test_word")
        result.output_data = {"concreteness": output}

        assert output == "concrete"
        result.status = "PASS"

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        result.traceback = traceback.format_exc()
```

### Best Practices

1. **Use TestResult objects** for detailed tracking
2. **Document expected behavior** in docstrings
3. **Handle exceptions gracefully** - capture don't crash
4. **Add notes for unexpected results** - explain deviations
5. **Test both happy and sad paths** - success and failure cases

## Known Issues to Test For

Based on analysis of current implementation:

1. **WordNet 3.1 Age**: Missing modern words (selfie, cryptocurrency, COVID-19)
2. **Multi-word handling**: Should skip phrases, verify it does
3. **Accent normalization**: How are café, résumé handled?
4. **POS preservation**: Existing POS shouldn't be overwritten
5. **Source tracking**: WordNet source should be added when enrichment occurs
6. **Concreteness for verbs**: Should return None or skip gracefully

## Future: wn Library Tests

After NLTK baseline is established, add:

- `TestWnConcreteness` - Same tests with wn library
- `TestWnPOSTagging` - Same tests with wn library
- `TestWnVsNltk` - Direct comparison tests
- Performance benchmarks

## Committing Test Results

Test results can be committed to version control to track:
- Baseline behavior before migration
- Edge cases discovered
- Regression detection
- Historical test coverage

```bash
# After running tests
git add tests/wordnet_test_results.txt
git add tests/wordnet_test_detailed_results.json
git commit -m "Add WordNet enrichment baseline test results"
```

## Troubleshooting

### Tests Skip with "NLTK not available"

```bash
# Ensure NLTK is installed
uv pip install nltk

# Download WordNet data
uv run python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

### ImportError for openword modules

```bash
# Install in development mode
uv pip install -e .
```

### No test results JSON file

- Check that conftest_wordnet.py is in tests/ directory
- Verify pytest version >= 8
- Run with -v flag to enable detailed reporter

## References

- Current implementation: `src/openword/wordnet_enrich.py`
- NLTK WordNet docs: https://www.nltk.org/howto/wordnet.html
- Princeton WordNet: https://wordnet.princeton.edu/
- Open English WordNet: https://en-word.net/
