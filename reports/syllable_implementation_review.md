# Syllable Information Implementation Review

**Analysis Date:** 2025-11-19

## Diagnostic Slice Analysis

Found 2 syllable-tagged slices and 9 baseline slices
Analyzing 11 total slices for syllable extraction...

**Found syllable data in 5/11 slices**

### dictionary (`0000acdc_3933_baseline_dictionary.xml`)

**Syllable Sources:**

- **Hyphenation:** 4 syllables
  - `{{hyphenation|en|dic|tion|a|ry||dic|tion|ary}}`

- **Rhymes:** 4 syllables
  - Found s=4

- **Category:** Not found

✅ **No conflicts** between sources

---

### free (`00011b5f_3951_baseline_free.xml`)

**Syllable Sources:**

- **Hyphenation:** Not found or unreliable

- **Rhymes:** 1 syllables
  - Found s=1

- **Category:** Not found

✅ **No conflicts** between sources

---

### thesaurus (`0001d422_4047_baseline_thesaurus.xml`)

**Syllable Sources:**

- **Hyphenation:** 3 syllables
  - `{{hyphenation|en|the|saur|us}}`

- **Rhymes:** 3 syllables
  - Found s=3

- **Category:** Not found

✅ **No conflicts** between sources

---

### encyclopedia (`0001feec_3970_baseline_encyclopedia.xml`)

**Syllable Sources:**

- **Hyphenation:** 5 syllables
  - `{{hyphenation|en|en|cy|clo|pe|di|a}}`

- **Rhymes:** 6 syllables
  - Found s=6

- **Category:** Not found

⚠️  **CONFLICT DETECTED:**
  - Hyphenation: 5
  - Rhymes: 6
  - Category: None

---

### cat (`000289c0_4112_syllable_cat.xml`)

**Syllable Sources:**

- **Hyphenation:** Not found or unreliable

- **Rhymes:** 1 syllables
  - Found s=1

- **Category:** Not found

✅ **No conflicts** between sources

---

## Source Coverage Summary

**Total slices analyzed:** 11
**Slices with syllable data:** 5

| Source | Coverage | Percentage |
|--------|----------|------------|
| Hyphenation | 3/5 | 60% |
| Rhymes | 5/5 | 100% |
| Category | 0/5 | 0% |

**Conflicts detected:** 1/5

## Implementation Status

### ✅ COMPLETED

1. **Extraction Pipeline**
   - Three source extractors implemented:
     - Hyphenation template (priority 1)
     - Rhymes template (priority 2)
     - Category labels (priority 3)
   - Smart filtering to avoid false positives
   - Language code whitelist for accuracy

2. **Data Flow**
   - Syllable counts stored as integer field
   - Preserved through ingestion (`wikt_ingest.py`)
   - Preserved through merging (`merge_all.py`)
   - Only set when reliable (never guessed)

3. **Analysis & Reporting**
   - Comprehensive syllable statistics in `analyze_metadata.py`
   - Distribution tables, averages, samples
   - Coverage percentage tracking

### ❌ NOT YET IMPLEMENTED

1. **Wordlist Filtering**
   - Schema defines filters but not implemented:
     - `min_syllables`: Include words with ≥ N syllables
     - `max_syllables`: Include words with ≤ N syllables
     - `exact_syllables`: Include words with exactly N syllables
     - `require_syllables`: Exclude words without syllable data
   - Location: `docs/schema/wordlist_spec.schema.json` (lines 296-320)
   - Needs implementation in: `src/openword/export_wordlist.py`

2. **Filter Application**
   - No code in `src/openword/filters.py` for syllable filtering
   - No integration in wordlist export pipeline

## Priority Handling & Conflict Resolution

The implementation uses a **waterfall priority system** with no conflict checking:

```python
# Priority 1: Hyphenation template
if hyphenation_count is not None:
    syllable_count = hyphenation_count
# Priority 2: Rhymes template
elif rhymes_count is not None:
    syllable_count = rhymes_count
# Priority 3: Category labels
elif category_count is not None:
    syllable_count = category_count
```

**Implication:** If hyphenation exists, other sources are never checked or compared.

This means:
- ✅ **No conflicts in output** (only one source used per word)
- ✅ **Prioritizes most reliable source** (hyphenation)
- ⚠️  **Cannot detect Wiktionary data inconsistencies** (if sources disagree)

## Recommendations

### 1. **Implementation Priority: Enable Filtering** 🔴 HIGH

**What:** Implement syllable filtering in wordlist export

**Why:** The extraction and storage are complete. Filtering is the only missing piece for the use case described (children's word game with 2-syllable concrete nouns).

**How:**
```python
# In src/openword/filters.py
def filter_by_syllables(entries, spec):
    syllable_spec = spec.get('syllables', {})
    if not syllable_spec:
        return entries
    
    min_syl = syllable_spec.get('min')
    max_syl = syllable_spec.get('max')
    exact_syl = syllable_spec.get('exact')
    require = syllable_spec.get('require_syllables', False)
    
    filtered = []
    for entry in entries:
        syl = entry.get('syllables')
        
        # Require syllable data if specified
        if require and syl is None:
            continue
        
        # Skip if no data and filters specified
        if syl is None and (min_syl or max_syl or exact_syl):
            continue
        
        # Apply filters
        if exact_syl and syl != exact_syl:
            continue
        if min_syl and syl < min_syl:
            continue
        if max_syl and syl > max_syl:
            continue
        
        filtered.append(entry)
    
    return filtered
```

**Impact:**
- Enables the children's word game use case immediately
- Allows filtering like: 'exact: 2, require_syllables: true' → only 2-syllable words with data
- Works with existing ~30k words with syllable data (2% coverage from report)

### 2. **Data Quality: Add Conflict Detection** 🟡 MEDIUM

**What:** Optionally log when sources disagree (hyphenation vs rhymes vs category)

**Why:** Helps identify Wiktionary data quality issues for potential upstream fixes

**How:**
```python
# In wiktionary_scanner_parser.py, around line 1202
# Check all sources and log conflicts
if hyph_count and rhyme_count and hyph_count != rhyme_count:
    logger.warning(f'Syllable conflict in {word}: hyph={hyph_count} rhyme={rhyme_count}')
```

**Impact:**
- No change to output (still uses priority system)
- Visibility into data quality issues
- Potential for contributing fixes back to Wiktionary

### 3. **Coverage Improvement: Consider IPA Parsing** 🟢 LOW

**What:** Extract syllable counts from IPA pronunciation (e.g., `/ˈdɪk.ʃə.nɛ.ɹi/` → 4 syllables)

**Why:** Could increase coverage from 2% to potentially 40-60%

**Caution:** IPA syllable counting is complex:
- Syllabic consonants (e.g., /l̩/, /n̩/)
- Diphthongs vs two vowels
- Language-specific rules
- Would violate current 'never guess' principle

**Recommendation:** NOT recommended unless:
1. Manual validation on 1000+ entries shows >95% accuracy
2. Flagged separately from Wiktionary-sourced counts
3. Users can filter by 'reliable_syllables_only'

### 4. **Source Priority Validation** 🟢 LOW

**What:** Verify hyphenation is indeed more reliable than rhymes/categories

**Why:** Current priority assumes hyphenation is best, but no empirical validation

**How:**
1. Process full Wiktionary dump
2. Track all three sources for words that have multiple
3. Manually validate sample of 100 conflicts
4. Adjust priority if needed

## Answer to User Questions

### Q1: Can syllable info be used at list generation time to filter words?

**Current Status:** ❌ NO - Schema defined but not implemented

**After Implementation:** ✅ YES - Would take ~30 minutes to implement filtering

**Coverage:** ~30k words (2% of entries) have syllable data from Wiktionary

**Example Use Case:**
```json
{
  "pos": ["noun"],
  "syllables": {"exact": 2, "require_syllables": true},
  "register": {"exclude": ["slang", "vulgar"]},
  "concrete": true,
  "frequency_tier": {"max": "N"}
}
```

This would produce hundreds of words like: 'table', 'window', 'pencil', 'rabbit'

### Q2: Do hyphenation vs rhyme (or other sources) conflict or disagree?

**Based on diagnostic slices:** 1/11 conflicts detected

**Current Implementation:** Conflicts are invisible due to priority waterfall

- Hyphenation always wins if present
- Other sources only used as fallback
- No logging or tracking of disagreements

**Recommendation:**
- Keep priority system (don't break ties)
- Add optional conflict logging for data quality monitoring
- This helps identify issues to potentially fix upstream in Wiktionary

### Q3: What is the most utility we can get from what source of truth?

**Source of Truth: Wiktionary hyphenation templates**

**Strengths:**
- Human-curated and reviewed
- Explicit syllable boundaries (not just counts)
- High accuracy when present
- Already extracted and stored

**Limitations:**
- Only 2% coverage (30k/1.3M entries)
- Wiktionary editors prioritize common words
- Rare/technical words often lack data

**Maximum Utility Strategy:**

1. **Accept sparse coverage** ✅
   - For use cases like children's games, 30k words is MORE than enough
   - Quality over quantity for syllable-filtered lists

2. **Implement filtering NOW** 🔴
   - Unlock the value of existing 30k syllable-tagged words
   - Enable 'require_syllables: true' for quality-controlled lists

3. **Never guess syllables in extraction** ✅ (already done)
   - Maintain 'reliable data only' principle
   - Let downstream applications add heuristics if needed

4. **Consider multiple fallbacks** 🟡
   - Current: hyphenation → rhymes → categories (good!)
   - Potential future: Add IPA parsing with 'confidence_level' field

## Summary

**Status:** 🟡 80% Complete

- ✅ Extraction: Excellent (3 sources, smart filtering)
- ✅ Storage: Complete (preserved through pipeline)
- ✅ Analysis: Complete (comprehensive reporting)
- ❌ Filtering: Not implemented (blocking use case)

**Critical Path:** Implement syllable filtering in `export_wordlist.py`

**Time Estimate:** ~30-60 minutes for filtering implementation + tests

**Value:** Unlocks immediate use for word games, educational apps, poetry tools, etc.

