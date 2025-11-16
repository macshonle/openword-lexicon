# Risks and Opportunities Analysis

**Date:** 2025-11-16
**Context:** Post-unified build integration

---

## Executive Summary

Following the implementation of the unified build with WordNet-Wiktionary integration, we have identified key risks to mitigate and opportunities to exploit. This document provides actionable insights for the next development phase.

---

## 🚨 CRITICAL RISKS

### 1. Missing `auxiliary` POS Tag (DATA QUALITY)

**Status:** Confirmed issue
**Severity:** Medium
**Impact:** Schema defines `auxiliary` but zero occurrences in data

**Root Cause Analysis:**
- Schema includes `auxiliary` as valid POS tag
- `wikt_ingest.py` has mapping: `'aux': 'auxiliary', 'auxiliary': 'auxiliary'`
- **BUT**: Reports show 0 count for auxiliary across all distributions
- Likely causes:
  1. Wiktionary scanner parser not extracting `aux` tags
  2. Wiktextract data doesn't have this POS category
  3. Merge process dropping this rare POS tag

**Evidence:**
```
# From metadata_analysis_plus.md - POS Tags section
| noun | 928,186 |
| verb | 226,957 |
| adjective | 188,311 |
...
| particle | 484 |
# auxiliary: MISSING (should be here if present)
```

**Auxiliary verbs in English:** *be*, *have*, *do*, *will*, *would*, *shall*, *should*, *can*, *could*, *may*, *might*, *must*

**Impact:**
- Cannot filter specifically for auxiliary verbs
- POS-based game filtering less precise
- Schema-data mismatch causes confusion

**Mitigation:**
1. **Immediate:** Add warning to reports when expected POS tags are missing ✅ (completed)
2. **Short-term:** Investigate scanner parser to confirm aux tag extraction
3. **Medium-term:** Add manual auxiliary verb list as fallback
4. **Long-term:** Enhance Wiktionary extraction to capture all POS categories

**Workaround:** Use verb filtering and manual exclusion list for now

---

### 2. Syllable Data Not Propagating (PIPELINE BUG)

**Status:** Fixed
**Severity:** High
**Impact:** Syllable data extracted but lost during ingestion

**Root Cause:**
- `wiktionary_scanner_parser.py` extracts syllables from hyphenation templates ✅
- `wikt_ingest.py` was NOT including syllables in entry dict ❌
- Result: 0% syllable coverage despite extraction working

**Fix Applied:**
```python
# wikt_ingest.py - now includes syllables
if 'syllables' in wikt_entry:
    entry['syllables'] = wikt_entry['syllables']

# Also updated merge logic to preserve syllables
```

**Expected Impact:**
- Syllable coverage should jump from 0% to ~30-50% after rebuild
- Enables new game filtering (e.g., "1-2 syllable words for kids")
- Supports reading level classification

**Action Required:**
- Rebuild data with updated `wikt_ingest.py`
- Regenerate reports to confirm coverage improvement

---

### 3. Core Concreteness Over-Reliance (FALSE CONFIDENCE)

**Status:** Risk identified
**Severity:** Medium
**Impact:** Core shows 99.997% concreteness coverage but masks future issues

**The Problem:**
```
Core:  99.997% concreteness (71,860/71,862 nouns) - "Perfect!"
Plus:   9.9% concreteness (91,721/928,186 nouns) - "Terrible!"
Unified: ~40% expected (with WordNet enrichment on all entries)
```

**Why This Is Risky:**
1. Core's "perfect" coverage is misleading - it's only because Core has few nouns
2. Users see 99.997% and assume the system works great
3. When scaling to Wiktionary (10x more nouns), coverage plummets
4. Creates false expectation that concreteness is "solved"

**Real Issue:**
- WordNet only has ~155K entries
- Wiktionary has 928K nouns
- Gap of ~773K nouns with no concreteness data
- Safe defaults help, but metadata is still missing

**Opportunities:** (see below)

---

### 4. License Complexity Confusion (UX RISK)

**Status:** New concern
**Severity:** Low-Medium
**Impact:** Per-word licensing may confuse developers

**The Issue:**
- Old model: Choose Core (permissive) OR Plus (restrictive) upfront
- New model: Every word tracks its own licenses via `license_sources`
- Developer must now understand: "This word requires CC-BY-SA"

**Example:**
```json
{
  "word": "castle",
  "license_sources": {
    "CC0": ["enable"],
    "UKACD": ["eowl"],
    "CC-BY-SA-4.0": ["wikt"]
  }
}
```

**Developer questions:**
- "What does this mean for my app?"
- "Can I use this word if I'm MIT-licensed?"
- "How do I filter to only permissive licenses?"

**Mitigation:**
1. **Documentation:** Clear licensing guide with decision tree
2. **Helper functions:** `matches_license(entry, max_restrictiveness='CC-BY-4.0')`  ✅
3. **Preset filters:** "permissive-only", "commercial-friendly", etc.
4. **Examples:** Show common scenarios in docs

**Status:** Partially mitigated via `filters.py` license filtering

---

## 💡 MAJOR OPPORTUNITIES

### 1. Syllable-Based Game Filtering (NEW CAPABILITY)

**Status:** Ready to exploit (after rebuild)
**Value:** High
**Effort:** Low (infrastructure exists)

**Opportunity:**
With syllable data now flowing through pipeline, enable new use cases:

**Reading Level Classification:**
```
Beginner:  1-2 syllables, top1k frequency
Elementary: 1-3 syllables, top10k frequency
Advanced: 3+ syllables, top100k frequency
```

**Game-Specific Filtering:**
```
Charades (kids): 1-2 syllables, concrete nouns
Poetry/Rhyming: Filter by syllable count for meter
Pronunciation games: Group by syllable complexity
```

**Implementation:**
- Add syllable filters to `filters.py` ✅ (schema already supports it)
- Document in `FILTERING.md`
- Add preset: `kids-simple-words` (1-2 syllables, concrete, top10k)

**Expected Coverage:**
- 30-50% of Wiktionary entries (conservative estimate)
- Higher for common words (top10k likely >70%)
- Safe default: missing syllables = exclude (complex/technical words)

**Next Steps:**
1. Rebuild with syllable-aware `wikt_ingest.py`
2. Generate coverage report
3. Add syllable presets to filter system
4. Document in game word guide

---

### 2. External Concreteness Database Integration

**Status:** Research opportunity
**Value:** Very High
**Effort:** Medium

**The Gap:**
- Current: WordNet coverage for 155K words
- Need: Concreteness for 1.3M words
- Missing: ~775K nouns without data

**Solution:** Integrate research datasets

**Available Resources:**
1. **Brysbaert et al. (2014)** - 40K words with concreteness ratings
   - License: CC-BY-4.0 (compatible!)
   - Format: word, concreteness_score (1-5 scale)
   - Coverage: ~40K words

2. **Glasgow Norms (2019)** - 5K words with detailed ratings
   - Includes: concreteness, imageability, familiarity
   - License: Open access
   - High quality, manually validated

3. **MRC Psycholinguistic Database** - 150K words
   - Includes: concreteness, imageability, age-of-acquisition
   - Widely used in research
   - License: Academic use

**Integration Approach:**
```python
# New file: src/openword/concreteness_enrich.py

def enrich_from_brysbaert(entries):
    """Enrich with Brysbaert et al. concreteness ratings."""
    # Load Brysbaert data
    ratings = load_concreteness_ratings('data/external/brysbaert_2014.csv')

    for word, entry in entries.items():
        if 'noun' in entry.get('pos', []) and not entry.get('concreteness'):
            rating = ratings.get(word)
            if rating:
                # Map 1-5 scale to concrete/abstract/mixed
                if rating > 3.5:
                    entry['concreteness'] = 'concrete'
                elif rating < 2.5:
                    entry['concreteness'] = 'abstract'
                else:
                    entry['concreteness'] = 'mixed'

                # Track source
                entry['sources'].append('brysbaert')
                entry['license_sources']['CC-BY-4.0'] = entry['license_sources'].get('CC-BY-4.0', []) + ['brysbaert']

    return entries
```

**Expected Impact:**
```
Current:  9.9% coverage (91K/928K nouns)
+ WordNet enrichment on Wiktionary: ~15% (140K nouns)
+ Brysbaert integration: ~18% (170K nouns)
+ MRC integration: ~25% (230K nouns)
```

**ROI Analysis:**
- **Effort:** 2-3 days implementation + testing
- **Value:** 2-3x improvement in concreteness coverage
- **Enables:** Reliable game word filtering for 230K+ nouns
- **Risk:** Low (external data well-validated)

**Recommendation:** **HIGH PRIORITY** - Implement Brysbaert integration first

---

### 3. Sense-Based Format (ARCHITECTURAL OPPORTUNITY)

**Status:** Design phase
**Value:** Very High
**Effort:** High (3-4 weeks)

**Current Limitation:**
- One entry per word (all senses merged)
- Cannot distinguish: "bank" (financial) vs "bank" (river)
- Loses sense-specific labels: "crow" (bird) vs "crow" (racial slur - offensive)

**Proposed:**
```
word     sense_id    pos    labels                 concreteness  freq
crow     crow.n.1    noun   domain:zoology        concrete      top3k
crow     crow.n.2    noun   register:offensive    N/A           rare
crow     crow.v.1    verb   -                     N/A           top10k
bank     bank.n.1    noun   domain:finance        abstract      top1k
bank     bank.n.2    noun   domain:geography      concrete      top3k
```

**Benefits:**
1. **Precision filtering:** Exclude offensive senses, keep neutral ones
2. **Semantic tagging:** Add tags like `animal`, `person`, `sound`
3. **Frequency per sense:** Different senses have different usage
4. **Regional handling:** Link US/UK variants properly
5. **Game optimization:** Include common senses, exclude rare technical ones

**Implementation Phases:**
1. **Phase 1:** Modify Wiktionary scanner to extract sense-level data (2 weeks)
2. **Phase 2:** Generate sense IDs and update schema (3 days)
3. **Phase 3:** Add semantic tagging via glosses + WordNet hypernyms (1 week)
4. **Phase 4:** Update filtering and querying logic (3 days)
5. **Phase 5:** Backwards compatibility layer (word-level collapse) (2 days)

**Risks:**
- Complexity: 3-4x more entries to manage
- Storage: Larger trie/metadata files
- Breaking change: Existing filters need updates

**Mitigations:**
- Start with experimental branch
- Provide migration guide
- Keep word-level queries working (collapse senses)

**Recommendation:** Plan for Q1 2026 major release

---

### 4. Gloss Extraction for Semantic Tagging

**Status:** Not started
**Value:** High
**Effort:** Medium (1-2 weeks)

**Current State:**
- 0% gloss coverage (definitions not extracted)
- Cannot do semantic filtering ("show me animals", "show me actions")

**Opportunity:**
Wiktionary provides rich definitions we're not using:

```
# Current (no glosses)
{
  "word": "cat",
  "pos": ["noun"],
  "concreteness": "concrete"
}

# With glosses + semantic tags
{
  "word": "cat",
  "pos": ["noun"],
  "gloss": "A small domesticated carnivorous mammal",
  "semantic_tags": ["animal", "mammal", "pet"],
  "concreteness": "concrete"
}
```

**Extraction Approach:**
1. **Scanner parser:** Extract first definition from Wiktionary
2. **Semantic tagging:** Use WordNet hypernyms + keyword matching
3. **Validation:** Manual review of top 1000 words

**Semantic Categories:**
```
Living:    animal, plant, person, body_part
Objects:   tool, vehicle, building, container, food
Abstract:  emotion, quality, time, quantity
Actions:   motion, communication, change, creation
```

**Use Cases:**
- **Kids' games:** "Show me animals" (cat, dog, elephant...)
- **Pictionary:** "Show me things you can draw" (concrete objects)
- **Vocabulary learning:** "Show me emotion words" (happy, sad, angry...)
- **Themed games:** "Science words", "Nature words", etc.

**Implementation:**
```python
# New file: src/openword/semantic_tagger.py

SEMANTIC_PATTERNS = {
    'animal': ['animal', 'mammal', 'bird', 'fish', 'insect'],
    'person': ['person', 'human', 'people', 'individual'],
    'food': ['food', 'dish', 'meal', 'edible'],
    # ... etc
}

def tag_from_gloss(gloss, wordnet_hypernyms):
    """Extract semantic tags from definition."""
    tags = []

    # Check WordNet hypernym path
    for hypernym in wordnet_hypernyms:
        if 'animal' in hypernym:
            tags.append('animal')
        if 'person' in hypernym:
            tags.append('person')
        # ...

    # Check gloss keywords
    gloss_lower = gloss.lower()
    for tag, patterns in SEMANTIC_PATTERNS.items():
        if any(p in gloss_lower for p in patterns):
            tags.append(tag)

    return sorted(set(tags))
```

**Expected Coverage:**
- Glosses: ~80% of Wiktionary entries
- Semantic tags: ~40% (conservative, high-quality only)

**Recommendation:** **MEDIUM PRIORITY** - Implement after syllables stabilize

---

## 🎯 STRATEGIC RECOMMENDATIONS

### Immediate (Next Sprint)

1. ✅ **Fix syllable propagation** - DONE
2. ✅ **Add missing POS warning to reports** - DONE
3. **Rebuild data** - Verify syllable coverage improvement
4. **Document license filtering** - Add guide with examples
5. **Test auxiliary verb extraction** - Confirm if truly missing or extraction issue

### Short-term (Next Month)

1. **Integrate Brysbaert concreteness data** - 2-3x coverage improvement
2. **Add syllable-based filters** - Enable reading level classification
3. **Create preset filter library** - kids-simple, wordle-hard, scrabble-tournament, etc.
4. **Manual auxiliary verb list** - Fallback for missing POS tag

### Medium-term (Q1 2026)

1. **Gloss extraction + semantic tagging** - Enable "show me animals" filtering
2. **External concreteness sources** - MRC database integration
3. **Enhanced regional handling** - US/UK variant linking
4. **Performance optimization** - Profile and optimize unified build

### Long-term (Q2-Q3 2026)

1. **Sense-based format** - Major architectural improvement
2. **Machine learning classifiers** - Auto-tag concreteness, semantic categories
3. **Crowdsourced validation** - Community review of game word lists
4. **API service** - Hosted filtering API for developers

---

## 📊 METRICS TO TRACK

### Data Quality
- ✅ Syllable coverage (target: 30-50% after rebuild)
- ✅ Missing POS tags (auxiliary currently 0%)
- Concreteness coverage progression (currently 9.9% Plus, target 25%)
- Label preservation rate (currently 10.6% Plus)

### Build Pipeline
- Build time (unified vs legacy)
- Memory usage peaks
- Data loss detection (labels, syllables, etc.)

### User Experience
- Filter precision (how many results match intent?)
- License filter usage (are users confused?)
- Common filter combinations (guide future presets)

---

## 🔍 RESEARCH QUESTIONS

1. **Auxiliary verbs:** Why are they missing? Extraction bug or data gap?
2. **Syllable accuracy:** How accurate is hyphenation-based counting?
3. **Concreteness correlation:** Do different sources agree? (WordNet vs Brysbaert)
4. **Sense frequency:** Can we estimate per-sense frequency from usage data?
5. **Semantic tagging quality:** Manual validation - what's our precision/recall?

---

## ✅ COMPLETED ITEMS (This Session)

1. ✅ Enhanced `analyze_metadata.py` with syllable analysis
2. ✅ Added missing POS tag detection to reports
3. ✅ Fixed `wikt_ingest.py` to preserve syllables field
4. ✅ Updated `merge_all.py` to merge syllables
5. ✅ Added source-specific sampling to reports
6. ✅ Created comprehensive licensing filters

---

## CONCLUSION

The unified build provides a strong foundation, but the real value comes from:
1. **Exploiting new capabilities** (syllables, license filtering)
2. **Closing data gaps** (concreteness, glosses, semantic tags)
3. **Improving precision** (sense-based format, better POS coverage)

**Recommendation:** Focus on **high-value, low-effort** wins first:
- Syllable filters (infrastructure exists)
- Brysbaert integration (2-3 days work, 2x coverage improvement)
- Preset filter library (user-facing value immediately visible)

Then tackle medium-effort items (glosses, semantic tags) before committing to the large architectural change (sense-based format).
