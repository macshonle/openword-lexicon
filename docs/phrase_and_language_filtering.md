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

## Recommendations

### Short Term (Immediate)
1. ✅ **Add phrase type detection** - extract before POS_MAP normalization
2. ✅ **Add word count** - simple split-based counting
3. ✅ **Update reports** - label phrase types in samples/enumeration

### Medium Term (Next Sprint)
4. **Enhanced filtering UI** - expose phrase_type and word_count in filters
5. **Language origin labels** - tag borrowed words, place names
6. **Documentation** - explain what counts as "English" in this lexicon

### Long Term (Future)
7. **Frequency-based filtering** - auto-exclude rare non-basic-Latin words
8. **Separate phrase lexicon** - dedicated dataset for idioms/proverbs
9. **Sense-level tracking** - distinguish borrowed vs naturalized senses

## Implementation Priority

**High Priority:**
- Phrase type metadata (fixes proverb issue)
- Word count metadata (enables better filtering)
- Report improvements (immediate visibility)

**Medium Priority:**
- Enhanced language filtering (more subjective)
- Better documentation (helps users understand)

**Low Priority:**
- Separate phrase lexicon (nice-to-have)
- Advanced sense tracking (requires major refactor)

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
