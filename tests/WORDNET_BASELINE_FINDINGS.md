# WordNet Enrichment Baseline Test Findings

**Date**: 2025-11-20
**NLTK Version**: 3.9.2
**WordNet Version**: Princeton WordNet (via NLTK, likely 3.0 or 3.1)
**Test File**: `tests/test_wordnet_standalone.py`
**Results**: `tests/wordnet_baseline_results.json`

## Summary

Comprehensive baseline testing of the current NLTK-based WordNet enrichment revealed **several issues** with concreteness classification and edge cases that should be addressed in the migration to OEWN 2024 with the `wn` library.

## Key Findings

### ✓ What Works Well

1. **POS Tagging**: Generally accurate, correctly identifies parts of speech
   - Successfully detects nouns, verbs, adjectives, adverbs
   - Correctly identifies multiple POS for ambiguous words
   - All tested words returned expected POS (12/12 = 100%)

2. **Edge Case Handling**: Graceful error handling
   - Nonexistent words return empty results (no crashes)
   - Modern neologisms correctly not found (expected for old WordNet)
   - Single-letter words handled without errors

3. **Full Enrichment Pipeline**: Works end-to-end
   - Backfills missing POS tags
   - Adds concreteness for nouns
   - Correctly tracks WordNet as a source
   - Skips multi-word phrases as designed

### ⚠️ Issues Discovered

#### 1. **Concreteness Over-Classification as "Mixed"** (Major)

Many clearly concrete or abstract nouns are being classified as "mixed":

**Concrete nouns misclassified as mixed**:
- `castle` → mixed (expected: concrete) ❌
- `hammer` → mixed (expected: concrete) ❌
- `dog` → mixed (expected: concrete) ❌

**Abstract nouns misclassified as mixed**:
- `justice` → mixed (expected: abstract) ❌
- `love` → mixed (expected: abstract) ❌

**Success rate**: Only 5/11 tested words classified as expected (45.5%)

**Root cause**: The heuristic in `wordnet_enrich.py:get_concreteness()` is too aggressive in marking words as "mixed" when synsets show both concrete and abstract properties. WordNet's semantic hierarchy often includes both physical and abstract aspects even for predominantly concrete/abstract nouns.

**Impact**: This reduces the usefulness of concreteness filtering for end users (e.g., children's word games would incorrectly exclude "dog" and "castle").

#### 2. **Accented Character Handling** (Minor)

Words with accents return empty results:
- `café` → pos=[], concreteness=None

**Root cause**: Likely a normalization issue. The word may need to be normalized to ASCII or the lookup may not match WordNet's internal representation.

**Impact**: Low (most English words don't have accents), but could affect borrowed words and proper nouns.

#### 3. **Missing Modern Vocabulary** (Expected, but documented)

As expected for Princeton WordNet 3.1 (2011), modern words are missing:
- `selfie` (popularized ~2013) → Not found
- `cryptocurrency` (popularized ~2009-2017) → Not found

**Impact**: This is a known limitation that will be addressed by migrating to OEWN 2024.

## Detailed Test Results

### Concreteness Classification

| Word | Expected | Actual | Status |
|------|----------|--------|--------|
| apple | concrete | concrete | ✓ |
| castle | concrete | **mixed** | ✗ |
| hammer | concrete | **mixed** | ✗ |
| dog | concrete | **mixed** | ✗ |
| freedom | abstract | abstract | ✓ |
| happiness | abstract | abstract | ✓ |
| justice | abstract | **mixed** | ✗ |
| love | abstract | **mixed** | ✗ |
| paper | mixed | mixed | ✓ |
| bank | mixed | mixed | ✓ |
| light | mixed | mixed | ✓ |

**Stats**: 5 correct, 6 incorrect (45.5% accuracy for expected classifications)

### POS Tagging

| Word | Expected | Actual | Status |
|------|----------|--------|--------|
| castle | noun | noun, verb | ✓ |
| dog | noun | noun, verb | ✓ |
| table | noun | noun, verb | ✓ |
| run | verb | noun, verb | ✓ |
| think | verb | noun, verb | ✓ |
| eat | verb | verb | ✓ |
| happy | adjective | adjective | ✓ |
| red | adjective | adjective, noun | ✓ |
| big | adjective | adjective, adverb | ✓ |
| quickly | adverb | adverb | ✓ |
| slowly | adverb | adverb | ✓ |
| happily | adverb | adverb | ✓ |

**Stats**: 12 correct, 0 incorrect (100% accuracy)

**Note**: Multiple POS results are acceptable and often correct (words can function as multiple parts of speech).

### Edge Cases

| Word | POS | Concreteness | Notes |
|------|-----|--------------|-------|
| nonexistentword12345 | [] | null | ✓ Correctly not found |
| a | noun | mixed | ✓ Single letter handled |
| selfie | [] | null | ✓ Modern word not in WordNet 3.1 |
| cryptocurrency | [] | null | ✓ Modern word not in WordNet 3.1 |
| café | [] | null | ⚠️ Accent handling issue |

## Recommendations for OEWN 2024 Migration

### High Priority

1. **Improve Concreteness Classification**
   - Consider using Brysbaert concreteness ratings (already in codebase) as primary source
   - Use WordNet/OEWN as fallback only
   - Adjust heuristic to be less aggressive about "mixed" classification
   - Validate against Brysbaert's empirical ratings

2. **Add Accent Normalization**
   - Implement Unicode normalization (NFKC) before WordNet lookups
   - Test with accented word list

3. **Leverage OEWN 2024 Updates**
   - Gain access to 18,500+ improvements over Princeton 3.1
   - Include modern vocabulary (selfie, cryptocurrency, etc.)
   - Benefit from community-maintained updates

### Medium Priority

4. **Add Regression Tests**
   - Use these baseline results as regression tests
   - Ensure `wn` library migration doesn't break working functionality
   - Track improvements in concreteness accuracy

5. **Document Known Limitations**
   - Multi-word phrases are skipped (by design)
   - Concreteness only applicable to nouns
   - POS tags are unions of all senses (intentional)

## Test Reproducibility

### Run Baseline Tests

```bash
# Standalone test (works without full pytest setup)
uv run python tests/test_wordnet_standalone.py

# Output: tests/wordnet_baseline_results.json
```

### Full pytest Suite (In Progress)

```bash
# Comprehensive test suite (requires import fixes)
uv run pytest tests/test_wordnet_enrichment.py -v --tb=long
```

**Note**: The full pytest suite currently has import issues that need to be resolved. The standalone test is the working baseline.

## Files for Version Control

✓ Commit these files to document baseline:
- `tests/test_wordnet_standalone.py` - Working baseline test
- `tests/wordnet_baseline_results.json` - Detailed results
- `tests/WORDNET_BASELINE_FINDINGS.md` - This summary
- `tests/test_wordnet_enrichment.py` - Comprehensive pytest suite (WIP)
- `tests/README_WORDNET_TESTS.md` - Test documentation

## Next Steps

1. ✓ Document baseline behavior (this file)
2. ⬜ Fix concreteness classification (use Brysbaert as primary)
3. ⬜ Integrate `wn` library for OEWN 2024
4. ⬜ Create parallel tests for `wn` library
5. ⬜ Run comparison tests (NLTK vs wn)
6. ⬜ Migrate wordnet_enrich.py to use `wn` library
7. ⬜ Validate no regressions in POS tagging
8. ⬜ Measure improvement in concreteness accuracy
9. ⬜ Update documentation

## References

- Current implementation: `src/openword/wordnet_enrich.py`
- Brysbaert enrichment: `src/openword/brysbaert_enrich.py`
- NLTK WordNet docs: https://www.nltk.org/howto/wordnet.html
- Open English WordNet: https://en-word.net/
- `wn` library: https://github.com/goodmami/wn
