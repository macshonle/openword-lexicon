# Report Analysis - Comprehensive Review

**Date:** 2025-01-16
**Reports Reviewed:** metadata_analysis_core.md, metadata_analysis_plus.md, distribution_comparison.md, raw_data_inspection.md

---

## Executive Summary

The consolidated reporting system is working well and successfully identified several critical data quality issues. The label preservation fix increased coverage from 0.0% to 10.6% in Plus distribution. However, Core distribution has fundamental limitations due to lack of label metadata.

---

## ✅ Successes

### 1. Label Preservation Fix Validated
- **Plus distribution**: 137,917 entries with labels (10.6% coverage) ✓
  - Register labels: 36,348 (2.8%)
  - Domain labels: 46,578 (3.6%)
  - Region labels: 27,239 (2.1%)
  - Temporal labels: 71,349 (5.5%)
- **Impact**: Increased from 13 entries (0.0%) to 137,917 entries (10.6%)
- **Status**: ✅ Fix successful and validated

### 2. Consolidated Reports Working Well
- Reports generated successfully for both distributions
- Sense-based format analysis providing valuable insights
- Rich entry samples effectively demonstrate multi-POS issues
- Statistics accurate and comprehensive

### 3. POS Tag Counting Bug Fixed
- **Bug**: Was reading from `labels.get('pos')` instead of `meta.get('pos')`
- **Fix**: Updated to read from correct location
- **Status**: ✅ Fixed in commit 2687097

---

## ⚠️ Critical Issues

### 1. Core Distribution Has Zero Labels

**Finding:** Core distribution has 0.0% label coverage across all categories.

**Root Cause:** Core only uses ENABLE + EOWL sources, which don't provide label metadata. Wiktionary is not included in Core.

**Impact:**
- Core cannot be used for label-based filtering (register, domain, region, temporal)
- Family-friendly filtering is ineffective on Core (no labels to check)
- Core distribution may contain offensive words that would be filtered in Plus

**Evidence from reports:**
```
Core - Label Coverage:
- Any labels: 0 (0.0%)
- Register labels: 0 (0.0%)
- Domain labels: 0 (0.0%)
- Region labels: 0 (0.0%)
- Temporal labels: 0 (0.0%)
```

**Recommendation:**
- Document this limitation prominently in Core distribution docs
- Consider if Core should include Wiktionary for label coverage
- OR create explicit offensive word blocklist for ENABLE/EOWL sources

---

### 2. Core Contains Offensive Words

**Finding:** Distribution comparison shows Core-only words include: "cocksucker", "fucking", "shagging", and other offensive terms.

**Root Cause:**
1. These words exist in ENABLE/EOWL source data
2. Wiktionary has these words with offensive/vulgar labels
3. Family-friendly filter checks `register` labels for vulgar/offensive/derogatory
4. Core has NO labels, so filter passes everything through
5. Plus has labels from Wiktionary, so these words get filtered out
6. Result: Offensive words appear in Core but not Plus

**Code Evidence:**
```python
# policy.py line 95-99
labels = entry.get('labels', {})
register = set(labels.get('register', []))

# Exclude if any problematic register labels
if register & FAMILY_FRIENDLY_EXCLUDE_REGISTER:
    return False
```

For Core entries with no labels, `register` is an empty set, so the filter never triggers.

**Impact:**
- Core distribution is NOT actually family-friendly despite using family_friendly.jsonl
- Users expecting "Core = safe for kids" will be surprised
- Brand risk if Core is used in children's applications

**Recommendation:**
- Create explicit offensive word blocklist for ENABLE/EOWL
- Apply blocklist to Core distribution regardless of labels
- Document that Core is not label-filtered
- Consider renaming "Core" to avoid implying it's family-friendly

---

### 3. Concreteness Coverage Disparity

**Finding:**
- **Core**: 99.997% coverage (only 2 nouns missing concreteness data) ✅
- **Plus**: 9.9% coverage (836,465 nouns without concreteness) ⚠️

**Root Cause:** WordNet enrichment works excellently on ENABLE/EOWL (which have ~72K nouns) but doesn't cover most Wiktionary entries (~928K nouns total in Plus).

**Impact:**
- Game filtering by concreteness only works well on Core
- Plus users cannot effectively filter by concrete/abstract despite larger word list
- Limits usefulness of Plus for games like "20 Questions"

**Recommendation:**
- Extend WordNet enrichment to Wiktionary entries
- OR document this limitation and recommend Core for concreteness filtering
- OR integrate external concreteness database (e.g., Brysbaert et al. concreteness ratings)

---

### 4. Missing Gloss Data

**Finding:** Both Core and Plus show 0.0% gloss coverage.

**Root Cause:** Glosses are not being extracted from any source.

**Impact:**
- Cannot use semantic filtering based on word definitions
- Limits ability to add semantic tags (animal, person, sound, etc.)
- Reduces richness of metadata for game-specific filtering

**Opportunity:** Extract glosses from Wiktionary for semantic tagging and filtering.

---

## 📊 Data Quality Insights

### 1. Multi-POS Conflation (Validates Sense-Based Format Need)

**Finding:** 89,098 words in Plus have multiple POS tags.

**Examples:**
- "aa": 10 different POS tags + 6 domains + both US/UK regions
- "er": 10 different POS tags + 6 domains
- "point": 3 POS + 4 temporal labels (archaic, dated, historical, obsolete all conflated)

**Impact:** Cannot distinguish between senses of the same word.

**Validation:** Perfectly demonstrates why sense-based format is needed (as proposed in reports).

---

### 2. Frequency Tier Granularity

**Finding:** 10 tiers instead of expected 5:
- top10, top100, top300, top500, top1k, top3k, top10k, top25k, top50k, rare

**Note:** This is fine but should be documented. More granular tiers provide better filtering control.

---

### 3. Source Distribution Oddities

**Finding:**
- ENABLE: Core has 172,823 but Plus has 171,628 (-1,195)
- EOWL: Core has 128,983 but Plus has 127,816 (-1,167)

**Question:** Why are some ENABLE/EOWL words filtered out in Plus?

**Hypothesis:**
- Plus applies family-friendly filter
- Some ENABLE/EOWL words get Wiktionary labels marking them as offensive
- These get filtered out of Plus but stay in Core (which has no labels)

**Validation Needed:** Check if the -1,195 ENABLE words and -1,167 EOWL words are the offensive words being filtered.

---

### 4. POS Tag Coverage

**Finding:**
- **Plus**: 98.6% (1,276,376 entries have POS tags)
- **Core**: 52.5% (109,383 entries have POS tags)

**Root Cause:** Wiktionary extracts POS from page structure, ENABLE/EOWL are just word lists.

**Impact:**
- Core has limited POS filtering capability
- Plus has excellent POS coverage

---

## 🎯 Recommendations

### Immediate (Documentation)

1. **Document Core limitations prominently:**
   ```
   Core Distribution Limitations:
   - No label metadata (no filtering by register, domain, region, temporal)
   - May contain offensive words (ENABLE/EOWL sources unfiltered)
   - Limited POS tag coverage (52.5%)
   - Use Plus distribution if you need label-based filtering
   ```

2. **Update README to clarify Core vs Plus:**
   ```
   Core: 208K words from ENABLE + EOWL
   - Excellent concreteness coverage (99.997%)
   - No labels (cannot filter offensive content effectively)
   - Smaller, faster, but less metadata

   Plus: 1.3M words from ENABLE + EOWL + Wiktionary
   - Rich label coverage (10.6% of entries have labels)
   - Can filter offensive content via register labels
   - Poor concreteness coverage (9.9%)
   - Larger, comprehensive, metadata-rich
   ```

3. **Add warning to policy.py:**
   ```python
   # NOTE: Core distribution has no labels, so family-friendly
   # filtering is ineffective. Core may contain offensive words
   # from ENABLE/EOWL sources.
   ```

### Short-term (Bug Fixes)

4. **Create offensive word blocklist for Core:**
   - Extract offensive words from Wiktionary labels
   - Create `docs/core_blocklist.txt` with known offensive terms
   - Apply blocklist to Core in policy.py regardless of labels
   - Document blocklist source and update process

5. **Validate source filtering hypothesis:**
   - Check if -1,195 ENABLE and -1,167 EOWL words are offensive
   - Document why Plus has fewer ENABLE/EOWL words than Core

### Medium-term (Enhancements)

6. **Extend WordNet enrichment to Wiktionary:**
   - Improve concreteness coverage in Plus from 9.9% to ~40%+
   - Use WordNet lemmatization to match Wiktionary words
   - Document coverage improvements

7. **Add gloss extraction:**
   - Extract first definition/gloss from Wiktionary
   - Enable semantic filtering (e.g., filter by gloss contains "animal")
   - Foundation for future semantic tagging

8. **Implement sense-based format:**
   - Parse Wiktionary by sense instead of merging all senses
   - Generate sense IDs (crow.n.1, crow.v.1)
   - Enable sense-specific filtering

### Long-term (Architecture)

9. **Add semantic tagging:**
   - Use glosses + WordNet hypernyms to tag semantic categories
   - Categories: animal, person, object, action, attribute, etc.
   - Enable rich semantic filtering for games

10. **Build variant linking:**
    - Link US/UK spelling variants (colour ↔ color)
    - Enable "prefer US spelling" or "include both variants" options
    - Track other variants (canceled/cancelled, etc.)

---

## 📈 Metrics Summary

| Metric | Core | Plus | Notes |
|--------|------|------|-------|
| **Total entries** | 208,201 | 1,295,010 | Plus is 6.2x larger |
| **Label coverage** | 0.0% | 10.6% | Core has zero labels |
| **POS tag coverage** | 52.5% | 98.6% | Plus much better |
| **Concreteness coverage** | 99.997% | 9.9% | Core much better |
| **Register labels** | 0 | 36,348 | Only Plus can filter by register |
| **Domain labels** | 0 | 46,578 | Only Plus can filter by domain |
| **Region labels** | 0 | 27,239 | Only Plus can filter by region |
| **Temporal labels** | 0 | 71,349 | Only Plus can filter archaic words |
| **Multi-POS words** | 14,647 | 89,098 | Both need sense splitting |

---

## 🔍 Next Steps

**For User:**
1. Review this analysis document
2. Decide on Core offensive word handling strategy
3. Prioritize which enhancements to implement
4. Consider rebranding "Core" if it's not actually family-friendly

**For Pipeline:**
1. Regenerate reports after POS bug fix (commit 2687097)
2. Create Core offensive word blocklist
3. Document Core/Plus tradeoffs in main README
4. Validate source filtering hypothesis

---

## 📝 Notes

- All findings are based on reports generated from built distributions
- The label preservation fix is confirmed working (10.6% coverage in Plus)
- POS counting bug has been fixed but reports need regeneration
- Core distribution's lack of labels is a fundamental architectural limitation, not a bug

---

## References

- `reports/metadata_analysis_core.md` - Core distribution analysis
- `reports/metadata_analysis_plus.md` - Plus distribution analysis
- `reports/distribution_comparison.md` - Core vs Plus comparison
- `src/openword/policy.py` - Family-friendly filtering logic
- `src/openword/wikt_ingest.py` - Label extraction fix (line 158-168)
- Commit 2687097 - POS counting bug fix
