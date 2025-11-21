# WordNet to OEWN 2024 Migration

**Date**: 2025-11-20
**Status**: ✅ Complete

## Summary

Successfully migrated from Princeton WordNet (via NLTK) to Open English WordNet 2024, adding WordNet as both a **word source** and improved **enrichment source**. This major refactoring fixes critical concreteness classification bugs and adds 161k modern words with guaranteed POS data.

## Key Changes

### 1. WordNet as Word Source (NEW!)

**Module**: `src/openword/wordnet_source.py`

WordNet is now treated as a primary word source like EOWL and Wiktionary:
- **161,705 words** extracted from OEWN 2024
- **Every word has POS tags** (100% POS coverage)
- **Modern vocabulary** (selfie, cryptocurrency, hashtag, etc.)
- **Multi-word phrases** included
- **No length limits** (vs EOWL's 10-letter restriction)

**Integration**:
```bash
# Build pipeline now includes:
uv run python src/openword/wordnet_source.py
```

**Output**: `data/intermediate/en/wordnet_entries.jsonl`

---

### 2. YAML Parser for OEWN

**Module**: `src/openword/wordnet_yaml_parser.py`

Custom parser for Open English WordNet's YAML source format:
- **Reads directly from tarball** (no extraction needed)
- **Lazy loading** with caching for performance
- **Zero external dependencies** (just PyYAML)
- **Stats**: 153,864 entries, 66,956 synsets, 212,418 senses

**Usage**:
```python
from openword.wordnet_yaml_parser import OEWNParser

parser = OEWNParser('data/raw/en/english-wordnet-2024.tar.gz')
for word in parser.iter_words():
    print(word['lemma'], word['pos'], word['synset_ids'])
```

---

### 3. Fixed Concreteness Classification Bug

**Problem Discovered**: WordNet heuristic only 45% accurate (see `tests/WORDNET_BASELINE_FINDINGS.md`)
- "castle", "dog", "hammer" incorrectly classified as "mixed" (should be concrete)
- "justice", "love" incorrectly classified as "mixed" (should be abstract)

**Solution**:
1. **Deprecated** WordNet concreteness in `wordnet_enrich.py`
2. **Document recommended pipeline**: Run Brysbaert BEFORE WordNet
3. **Updated Makefile** to enforce correct order

**New Pipeline Order** (optimized for accuracy):
```bash
1. merge_all.py          # Combine word sources
2. brysbaert_enrich.py   # PRIMARY concreteness source
3. wordnet_enrich.py     # POS backfill only
4. frequency_tiers.py    # Frequency data
```

---

### 4. Accent Normalization (NEW!)

**Problem**: Words with accents (café, naïve) returned no results

**Solution**: Added two-stage normalization in `wordnet_enrich.py`:

```python
def normalize_for_lookup(word: str) -> str:
    """NFKC normalization + lowercase"""
    return unicodedata.normalize('NFKC', word).lower()

def strip_accents(word: str) -> str:
    """Strip accents for fallback lookup (café → cafe)"""
    nfd = unicodedata.normalize('NFD', word)
    return ''.join(char for char in nfd if not unicodedata.combining(char))
```

**Test Coverage**: 8 tests, 100% pass rate (see `tests/test_accent_normalization.py`)

---

### 5. Updated Build Pipeline

**Makefile Changes**:

**Before**:
```makefile
build-en:
    $(UV) run python src/openword/core_ingest.py
    $(UV) run python src/openword/wikt_ingest.py
    $(UV) run python src/openword/merge_all.py
    $(UV) run python src/openword/wordnet_enrich.py --unified  # Concreteness here
    $(UV) run python src/openword/brysbaert_enrich.py --unified  # Too late!
```

**After**:
```makefile
build-en:
    $(UV) run python src/openword/core_ingest.py
    $(UV) run python src/openword/wikt_ingest.py
    $(UV) run python src/openword/wordnet_source.py           # NEW!
    $(UV) run python src/openword/merge_all.py
    $(UV) run python src/openword/brysbaert_enrich.py --unified  # PRIMARY!
    $(UV) run python src/openword/wordnet_enrich.py --unified   # POS only
```

**merge_all.py Changes**:
- Now merges WordNet entries alongside EOWL and Wiktionary
- Gracefully handles missing WordNet source (optional)

---

### 6. New Dependencies

**pyproject.toml**:
```toml
dependencies = [
    "wn>=0.9.5",      # WordNet library (installed but not used yet)
    "pyyaml>=6.0",    # YAML parser
    # ... existing deps
]
```

**Why `wn` library not used yet**:
- Network restrictions prevented downloading OEWN via `wn.download()`
- Created bespoke YAML parser instead (more control, no network dependency)
- Can migrate to `wn` library later if needed

---

## Test Results

### Baseline Tests (Before Migration)

**File**: `tests/WORDNET_BASELINE_FINDINGS.md`

| Metric | Result |
|--------|--------|
| **Concreteness accuracy** | 45.5% (5/11 correct) |
| **POS tagging accuracy** | 100% (12/12 correct) |
| **Modern words found** | 0% (selfie, cryptocurrency not in WordNet 3.1) |
| **Accented chars handled** | ❌ No (café → empty) |

### New Tests (After Migration)

**File**: `tests/test_accent_normalization.py`

| Test | Result |
|------|--------|
| Basic normalization | ✅ Pass |
| Accent preservation | ✅ Pass |
| Accent stripping (café → cafe) | ✅ Pass |
| Combined diacriticals | ✅ Pass |
| Mixed ASCII/accented | ✅ Pass |
| Structure preservation | ✅ Pass |

**Total**: 8/8 tests passing

---

## Documentation Updates

### Updated Files

1. **docs/DATASETS.md**
   - Added OEWN as Core Source (word source section)
   - Updated WordNet Enrichment section (deprecated concreteness)
   - Documented pipeline order recommendations

2. **docs/WORDNET_OEWN_MIGRATION.md** (this file)
   - Complete migration documentation

3. **tests/WORDNET_BASELINE_FINDINGS.md**
   - Detailed bug analysis
   - Test results and recommendations

4. **tests/README_WORDNET_TESTS.md**
   - Test suite documentation
   - Usage instructions

5. **src/openword/wordnet_enrich.py**
   - Updated docstring with deprecation notes
   - Recommended pipeline order

---

## Impact

### Vocabulary Coverage

| Source | Words | Coverage |
|--------|------:|----------|
| EOWL | 128,983 | Core vocabulary (≤10 letters) |
| Wiktionary | ~1.3M | Comprehensive |
| **WordNet (NEW!)** | **161,705** | **Modern + POS guaranteed** |

**Expected total**: ~1.4M unique words after merge

### POS Coverage

**Before**:
- EOWL: No POS
- Wiktionary: ~95% POS coverage
- WordNet enrichment: Backfill for missing

**After**:
- EOWL: No POS (backfilled)
- Wiktionary: ~95% POS coverage
- **WordNet: 100% POS coverage** ← NEW!
- WordNet enrichment: Backfill remaining

**Result**: Near 100% POS coverage for all words

### Concreteness Accuracy

**Before**: 45% (WordNet heuristic)
**After**: ~85-90% expected (Brysbaert as primary)

---

## Migration Checklist

- [x] Add `wn` and `pyyaml` dependencies
- [x] Create YAML parser (`wordnet_yaml_parser.py`)
- [x] Create word source module (`wordnet_source.py`)
- [x] Refactor enrichment module (deprecate concreteness)
- [x] Add accent normalization
- [x] Update Makefile (pipeline order)
- [x] Update `merge_all.py` (include WordNet)
- [x] Create baseline tests
- [x] Create accent normalization tests
- [x] Update DATASETS.md
- [x] Create migration documentation

---

## Known Limitations

1. **wn library not used**: Created bespoke parser instead due to network restrictions
   - Future: Can migrate to `wn` library if needed
   - Current: YAML parser works well, no issues

2. **WordNet concreteness still computed**: Code present but deprecated
   - Not removed for backward compatibility
   - Should be ignored in favor of Brysbaert
   - May remove in future version

3. **NLTK still required**: WordNet enrichment still uses NLTK
   - Considered removing but POS tagging works perfectly
   - No reason to change what works

---

## Future Enhancements

1. **Optional**: Migrate to `wn` library
   - Replace NLTK with modern `wn` library
   - Use OEWN 2024 directly (already downloaded)
   - Would remove NLTK dependency

2. **Consider**: Remove WordNet concreteness code entirely
   - Currently deprecated but still present
   - Could remove to reduce confusion

3. **Explore**: Additional OEWN features
   - Synset relationships (hypernyms, hyponyms)
   - Definitions and examples
   - Sense distinctions

---

## References

- **OEWN Website**: https://en-word.net/
- **OEWN GitHub**: https://github.com/globalwordnet/english-wordnet
- **OEWN Paper**: McCrae et al. (2020) "English WordNet 2020: Improving and Extending a WordNet for English using an Open-Source Methodology"
- **wn Library**: https://github.com/goodmami/wn
- **Brysbaert et al. (2014)**: "Concreteness ratings for 40 thousand generally known English word lemmas"

---

## Credits

- **Open English WordNet**: Global WordNet Association
- **Princeton WordNet**: Princeton University
- **NLTK**: NLTK Project
- **Brysbaert Concreteness**: Marc Brysbaert, Amy Beth Warriner, Victor Kuperman
