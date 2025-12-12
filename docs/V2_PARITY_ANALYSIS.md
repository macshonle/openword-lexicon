# V2 Scanner Parity Analysis

Analysis date: December 2024
Test data: hotspotwords.xml.bz2 (81 words, 94 pages)

## Summary

| Metric | V1 | V2 (before fix) | V2 (after fix) |
|--------|----|-----------------| ---------------|
| Total entries | 800 | 356 | 407 |
| Unique words | 81 | 81 | 81 |
| Domain codes captured | Yes | **No** | Yes |

## Bug Fixed: Missing Domain Codes

**Problem**: V2 had infrastructure for domain code mapping (`label_to_domain` in `cdaload.py`) but `rules.py` never called it.

**Fix**: Added `compute_domain_codes()` function to `rules.py` that:
1. Maps labels from `{{lb|en|...}}` to domain codes using `config.label_to_domain`
2. Maps category substrings to domain codes using `config.category_substring_to_domain`

**Result**: V2 now captures domain codes:
- DSPRT: 11 (sports)
- DCOMP: 9 (computing)
- DMUSC: 7 (music)
- DMEDI: 6 (medicine)
- DPHYS: 6 (physics)
- DLING: 6 (linguistics)
- DNAUT: 6 (nautical)
- And more...

## Key Differences (Remaining)

### 1. Entry Count (V2 Deduplication)

V2 performs page-level deduplication (800 → 407 entries). This is intentional.

### 2. ALTH (Alternative Form) Flag

V2 adds `ALTH` code for entries from templates like `{{alt form}}`, `{{alternative form of}}`, etc. V1 doesn't capture this.

Examples:
- `B. O. A. T.` → V2: `["ALTH"]`, V1: `[]`
- `Abderian` → V2: `["ALTH", "SUFF"]`, V1: `["SUFF"]`

**Assessment**: V2 improvement.

### 3. ABRV vs ALTH Semantics (Resolved)

V2's classification is semantically correct. The distinction:

- **ABRV**: Entry IS an abbreviation/acronym (defined via `{{acronym of}}`, `{{abbreviation of}}`)
- **ALTH**: Entry IS an alternative form (defined via `{{alternative form of}}`)

**BOAT family example**:

| Page | Template | V2 Codes | Analysis |
|------|----------|----------|----------|
| `BOAT` | `{{acronym of|en|best of all time}}` | `ABRV` | Primary acronym |
| `B. O. A. T.` | `{{alternative form of|en|BOAT}}` | `ALTH` | Alt form of acronym, wc=4 |
| `B.O.A.T.` | `{{alternative form of|en|BOAT}}` | `ALTH` | Alt form of acronym, wc=1 |
| `BoAT` | `{{alternative form of|en|BOAT}}` | `ALTH` | Alt form of acronym |
| `boat` (sense 12) | `{{alternative form of|en|BOAT}}` | `ALTH` | One sense refers to acronym |

**Assessment**: V2 is correct. ALTH tracks the entry's relationship (it's an alternative form), not what it's an alternative form OF.

#### "words" Sub-format Filtering Strategy

For applications needing plain words only (e.g., word games), filter with:

```yaml
# Exclude abbreviation variants
character:
  pattern: "^[a-zA-Z]+$"  # Letters only - excludes "B.O.A.T."

phrase:
  max_words: 1  # Single words - excludes "B. O. A. T." (wc=4)

exclude:
  codes: [ABRV]  # Excludes actual abbreviations like "BOAT" acronym sense
```

The `ALTH` code alone is insufficient for filtering because legitimate words like "colour" (ALTH of "color") would be excluded.

### 4. Additional Domain Codes in V2

V2 captures some domain codes V1 misses:
- `DMUSC` (music)
- `DPHIL` (philosophy)
- `DASTL` (astronomy)

### 5. Region Codes (ENXX)

V2 captures region codes better:
- `ENGB` (British)
- `ENUS` (American)
- `ENAU` (Australian)

### 6. POS Coverage

V2 sometimes finds additional POS that V1 misses:
- `A`: V2 has `NUM`
- `Saturday`: V2 has `SYM`

## Remaining Issues

### Low Priority

1. **Entry count differences** - V2 deduplication is more aggressive (intentional)

## Resolved Issues

1. **Missing domain codes** - Fixed by adding `compute_domain_codes()` to rules.py
2. **ABRV vs ALTH classification** - V2 is semantically correct (see section 3 above)
3. **Morphology SIMP/COMP classification** - Fixed in `compute_morphology()`:
   - Bug: `{{af|en|Isle|of|Man}}` (free bases, no hyphens) was classified as SIMP
   - Fix: Multiple free bases (no affixes) now correctly classified as COMP
   - `Isle of Man`: V2 now correctly shows COMP

## Files Modified

- `tools/wiktionary_scanner_v2/rules.py`:
  - Added `compute_domain_codes()` function
  - Fixed `compute_morphology()` to classify multi-base entries as COMP

## Next Steps

1. Run comparison on full corpus
2. Validate "words" sub-format filtering with test cases

## Future Enrichment: ABRV Inheritance

Alternative forms of abbreviations (e.g., `BoAT` → `BOAT`) currently get `ALTH` but not `ABRV`. A post-scan enrichment could:

1. For entries with `ALTH`, look up the lemma target in the JSONL
2. If target has `ABRV`, add `ABRV` to the current entry

This keeps the scanner focused on direct extraction while handling transitive relationships in the enrichment pipeline.
