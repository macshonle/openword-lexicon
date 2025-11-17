# Phrase and Language Filtering Issues

## Problems Identified

### Issue 1: Non-English Words Passing Through

**Example:** `łódź` (Polish city name) appears in 1-syllable English words

**Root Cause:**
- Wiktionary has an English section for this word (as a borrowed word/place name)
- The `is_englishlike()` function accepts all Latin script characters, including Latin Extended (ł, ź, ó, etc.)
- Unicode check: `"LATIN" in unicodedata.name(ch)` returns True for Latin Extended characters

**Why this happens:**
```python
# Current logic in is_englishlike()
if "LATIN" not in ud.name(ch, ""):
    return False
```

Characters like `ł` (LATIN SMALL LETTER L WITH STROKE) pass this test because they ARE Latin script, just not basic Latin.

**Legitimate use cases:**
- Borrowed words: café, naïve, résumé
- Place names: Łódź, Zürich
- Proper nouns: François, José

**Problem cases:**
- Words primarily used in other languages but have minimal English usage
- Transliterations that retain diacritics

### Issue 2: Lack of Phrase Type Granularity

**Example:** `zeal without knowledge is a runaway horse` (11-syllable proverb)

**Root Cause:**
- `POS_MAP` normalizes all phrase types to generic "phrase":
  ```python
  'idiom': 'phrase',
  'proverb': 'phrase',
  'prepositional phrase': 'phrase',
  # etc.
  ```
- Metadata only has `is_phrase: True` without preserving the specific type
- No distinction between:
  - Short phrases: "by right" (2 words)
  - Idioms: "kick the bucket" (3-4 words)
  - Proverbs: "zeal without knowledge is a runaway horse" (8 words)
  - Sentence-length expressions

**Current metadata:**
```json
{
  "word": "zeal without knowledge is a runaway horse",
  "pos": ["phrase"],
  "is_phrase": true,
  "syllables": 11
}
```

**What's missing:**
- `phrase_type`: "proverb" vs "idiom" vs "prepositional phrase"
- `word_count`: Number of words in the phrase
- Better filtering in reports

## Proposed Solutions

### Solution 1: Add Phrase Type Metadata

**Implementation:**
1. Extract original phrase type before POS_MAP normalization
2. Store in new field: `phrase_type`
3. Keep existing `is_phrase` for backward compatibility

**New metadata structure:**
```json
{
  "word": "zeal without knowledge is a runaway horse",
  "pos": ["phrase"],
  "is_phrase": true,
  "phrase_type": "proverb",  // NEW
  "word_count": 8,           // NEW
  "syllables": 11
}
```

**Benefits:**
- Downstream filtering can distinguish proverbs from idioms
- Reports can separate/label different phrase types
- Games can exclude long proverbs but keep short idioms

### Solution 2: Improve Report Filtering

**For syllable samples:**
- Mark phrases/idioms explicitly: `kick the bucket (idiom, 4 words)`
- Separate section for proverbs/long phrases
- Filter out proverbs from general samples

**For complete enumeration:**
- Show phrase type: `**11 syllables:** zeal without knowledge is a runaway horse (proverb, 8 words)`

### Solution 3: Enhanced Language Filtering

**Options:**

**A. Stricter diacritic filtering:**
- Only allow common diacritics in English: é, è, ê, ü, ä, ö, ñ, ç
- Reject Polish (ł, ź), Czech (ř, č), etc.
- Risk: Might reject legitimate borrowings

**B. Label-based filtering:**
- Add `language_origin` or `borrowing` labels
- Let downstream decide inclusion/exclusion
- More flexible but requires more metadata

**C. Usage-based filtering:**
- Only include if frequency tier indicates actual English usage
- Exclude Z-tier (extremely rare) words with non-basic Latin
- Balance between coverage and purity

### Solution 4: Word Count Tracking

**Simple implementation:**
```python
word_count = len(word.split())
if word_count > 1:
    entry['word_count'] = word_count
```

**Use cases:**
- Filter by phrase length
- Distinguish "by right" (2 words) from "zeal without knowledge..." (8 words)
- Statistics on phrase length distribution

## Implementation Status

### ✅ Completed (2025-11-17)

1. **✅ Solution 1: Add Phrase Type Metadata**
   - Removed `is_phrase` field entirely
   - Added `word_count` field (always present, default 1)
   - Added `phrase_type` field (present for multi-word entries)
   - Updated all downstream tools: merge_all.py, merge_dedupe.py, owlex.py, wordnet_enrich.py, core_ingest.py, filters.py, wikt_ingest.py

2. **✅ Solution 2: Improve Report Filtering**
   - Regular syllable samples now exclude proverbs and >5 word phrases
   - All samples annotate phrase type and word count
   - Rare syllable enumeration includes full metadata annotations
   - Better visibility of phrase types in reports

3. **✅ Solution 3B: Label-based Language Filtering**
   - Added `has_english_categories()` function
   - Validates English POS categories before accepting entry
   - Filters out foreign words like 'łódź' that have English sections but no English categories
   - Checks for common English categories: nouns, verbs, adjectives, idioms, phrases, etc.

### Pending Investigation

4. **⏳ Find other instances of false labeling**
   - Need to rebuild data and analyze results
   - Compare before/after filtering effectiveness
   - May need to tune category list

### Future Enhancements

5. **📋 Enhanced filtering UI** - expose phrase_type and word_count in filters
6. **📋 Language origin labels** - tag borrowed words, place names
7. **📋 Documentation** - explain what counts as "English" in this lexicon
8. **📋 Frequency-based filtering** - auto-exclude rare non-basic-Latin words
9. **📋 Separate phrase lexicon** - dedicated dataset for idioms/proverbs
10. **📋 Sense-level tracking** - distinguish borrowed vs naturalized senses

## Examples

### Good English Words (Keep)
- café ✓ (common borrowing, basic + acute)
- naïve ✓ (common borrowing, basic + diaeresis)
- résumé ✓ (common borrowing, basic + acute)

### Questionable Cases (Consider Filtering)
- łódź ⚠️ (Polish place name, Latin Extended, Tier Z)
- ångström ⚠️ (scientific unit, ring above, Tier Z)
- čeština ⚠️ (Czech language name, caron, Tier Z)

### Phrases to Label/Filter
- "by right" ✓ (2 words, prepositional phrase, useful)
- "kick the bucket" ✓ (4 words, idiom, useful)
- "zeal without knowledge is a runaway horse" ⚠️ (8 words, proverb, filter from general samples)
