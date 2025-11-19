# Openword Lexicon — Entry Schema

This document describes the JSON schema for lexicon entries.

## Table of Contents

- [Overview](#overview)
- [Field Reference](#field-reference)
- [Examples](#examples)
- [Validation](#validation)

---

## Overview

Each entry in the Openword Lexicon follows a consistent schema defined in `docs/schema/entry.schema.json`.

**Format**: JSON (JSONL for intermediate files, JSON array for metadata)

**Normalization**: All `word` fields use **Unicode NFKC** normalization for consistency.

**Schema File**: [entry.schema.json](schema/entry.schema.json)

---

## Field Reference

### Required Fields

#### `word` (string)

The word or phrase in normalized form.

- **Normalization**: Unicode NFKC
- **Case**: Lowercase
- **Example**: `"castle"`, `"give up"`

#### `sources` (array of strings)

Provenance: which source datasets contributed this entry.

- **Format**: Array of source IDs (lowercase, underscore-separated)
- **Min length**: 1
- **Unique**: Yes
- **Example**: `["enable", "eowl", "wikt"]`

**Source IDs:**
- `enable` — ENABLE word list (Public Domain)
- `eowl` — English Open Word List (UKACD License)
- `wikt` — Wiktionary (CC BY-SA 4.0)
- `wordnet` — Princeton WordNet (WordNet License)
- `brysbaert` — Brysbaert concreteness ratings (Research Use)
- `frequency` — OpenSubtitles 2018 frequency data

#### `license_sources` (object)

Mapping of license identifiers to the sources that require them.

- **Format**: Object with license IDs as keys, arrays of source IDs as values
- **Default**: `{}` (computed from `sources`)
- **Example**: `{"CC0": ["enable"], "UKACD": ["eowl"], "CC-BY-SA-4.0": ["wikt"]}`

**License IDs:**
- `CC0` — Public Domain (ENABLE)
- `UKACD` — UK Advanced Cryptics Dictionary License (EOWL)
- `CC-BY-SA-4.0` — Creative Commons Attribution-ShareAlike 4.0 (Wiktionary)
- `CC-BY-4.0` — Creative Commons Attribution 4.0 (OpenSubtitles frequency data)
- `WordNet` — Princeton WordNet License (WordNet enrichment)
- `Brysbaert-Research` — Research/Educational Use (Brysbaert concreteness ratings)

**Notes:**
- This field enables users to filter words based on license requirements
- For example, filtering to only `CC0` and `UKACD` licenses excludes Wiktionary data
- The license information is automatically computed from the `sources` field during the merge phase

---

### Optional Fields

#### `pos` (array of strings)

Part-of-speech tags.

- **Default**: `[]` (empty if unknown)
- **Values**: `noun`, `verb`, `adjective`, `adverb`, `pronoun`, `preposition`, `conjunction`, `interjection`, `determiner`, `particle`, `auxiliary`
- **Unique**: Yes
- **Sorted**: Yes
- **Example**: `["noun", "verb"]`

**Notes:**
- May be empty for core sources without linguistic markup
- Enriched via WordNet where confident
- Multiple POS tags indicate the word can serve multiple grammatical roles

#### `labels` (object)

Controlled vocabulary labels for classification.

- **Default**: `{}` (empty object)
- **Categories**: `register`, `region`, `temporal`, `domain`

##### `labels.register` (array of strings)

Sociolinguistic register and stylistic markers.

- **Values**: `formal`, `informal`, `colloquial`, `slang`, `vulgar`, `offensive`, `derogatory`, `euphemistic`, `humorous`, `literary`
- **Example**: `["vulgar", "offensive"]`

##### `labels.region` (array of strings)

Regional/dialectal usage.

- **Format**: BCP 47 language subtags (`en-XX`)
- **Example**: `["en-GB"]` (British English), `["en-US"]` (American English)

##### `labels.temporal` (array of strings)

Historical usage status.

- **Values**: `archaic`, `obsolete`, `dated`, `historical`, `modern`
- **Example**: `["archaic"]`

##### `labels.domain` (array of strings)

Specialized subject fields.

- **Values**: `medical`, `legal`, `technical`, `scientific`, `military`, `nautical`, `botanical`, `zoological`, `computing`, `mathematics`, `music`, `art`, `religion`, `culinary`, `sports`, `business`, `finance`
- **Example**: `["medical"]`

#### `is_phrase` (boolean)

Whether the entry is a multi-word phrase.

- **Default**: `false`
- **Example**: `true` for "give up", `false` for "castle"

#### `lemma` (string or null)

Base form if this is an inflection.

- **Default**: `null`
- **Example**: `"run"` for "running", `"good"` for "better"

#### `morphology` (object)

Morphological structure and derivation information extracted from Wiktionary etymology sections.

- **Default**: Not present (only included when etymology data available)
- **Source**: Wiktionary etymology templates (`{{suffix}}`, `{{prefix}}`, `{{affix}}`, `{{compound}}`)
- **Required subfields**: `type`, `components`

**What is morphology?**
Morphology describes how words are formed from smaller meaningful units (morphemes). This field captures derivational relationships (e.g., "happiness" ← "happy" + "-ness") and compound structures (e.g., "bartender" ← "bar" + "tender").

##### `morphology.type` (string)

Type of morphological formation.

- **Required**: Yes
- **Values**: `suffixed`, `prefixed`, `compound`, `affixed`, `circumfixed`, `simple`

**Formation Types:**
- **`suffixed`**: Base word + suffix (e.g., "happiness" = "happy" + "-ness")
- **`prefixed`**: Prefix + base word (e.g., "unhappy" = "un-" + "happy")
- **`affixed`**: Prefix(es) + base + suffix(es) (e.g., "unbreakable" = "un-" + "break" + "-able")
- **`compound`**: Two or more complete words (e.g., "bartender" = "bar" + "tender")
- **`circumfixed`**: Prefix and suffix added together (e.g., "enlightenment" = "en-" + "light" + "-ment")
- **`simple`**: Base form with no affixation (rare; usually not present)

##### `morphology.base` (string)

The base word or root.

- **Required**: No (optional for compounds)
- **Example**: `"happy"` for "happiness", `"break"` for "unbreakable"
- **Notes**:
  - For suffixed/prefixed/affixed: the core word
  - For compounds: may be omitted (components tell the full story)

##### `morphology.components` (array of strings)

All morphological components in order.

- **Required**: Yes (minimum 1 item)
- **Format**: Prefixes with trailing hyphen (`un-`), suffixes with leading hyphen (`-ness`)
- **Examples**:
  - `["happy", "-ness"]` for "happiness"
  - `["un-", "break", "-able"]` for "unbreakable"
  - `["bar", "tender"]` for "bartender"

##### `morphology.prefixes` (array of strings)

Prefix morphemes only.

- **Default**: `[]` (empty array)
- **Format**: With trailing hyphen (`un-`, `re-`, `pre-`)
- **Example**: `["un-"]` for "unbreakable", `["re-", "un-"]` for complex cases

##### `morphology.suffixes` (array of strings)

Suffix morphemes only.

- **Default**: `[]` (empty array)
- **Format**: With leading hyphen (`-ness`, `-able`, `-ly`)
- **Example**: `["-able"]` for "unbreakable", `["-ness"]` for "happiness"

##### `morphology.is_compound` (boolean)

Whether the word is formed by compounding.

- **Default**: `false`
- **Example**: `true` for "bartender", `false` for "happiness"

##### `morphology.etymology_template` (string)

Raw Wiktionary template for reference.

- **Required**: No
- **Example**: `"{{suffix|en|happy|ness}}"`, `"{{compound|en|bar|tender}}"`
- **Purpose**: Debugging, verification, tracing back to source data

### Morphology Examples

**Suffixed word (happiness)**:
```json
{
  "morphology": {
    "type": "suffixed",
    "base": "happy",
    "components": ["happy", "-ness"],
    "prefixes": [],
    "suffixes": ["-ness"],
    "is_compound": false,
    "etymology_template": "{{suffix|en|happy|ness}}"
  }
}
```

**Prefixed word (unhappy)**:
```json
{
  "morphology": {
    "type": "prefixed",
    "base": "happy",
    "components": ["un-", "happy"],
    "prefixes": ["un-"],
    "suffixes": [],
    "is_compound": false,
    "etymology_template": "{{prefix|en|un|happy}}"
  }
}
```

**Affixed word with prefix and suffix (unbreakable)**:
```json
{
  "morphology": {
    "type": "affixed",
    "base": "break",
    "components": ["un-", "break", "-able"],
    "prefixes": ["un-"],
    "suffixes": ["-able"],
    "is_compound": false,
    "etymology_template": "{{affix|en|un-|break|-able}}"
  }
}
```

**Compound word (bartender)**:
```json
{
  "morphology": {
    "type": "compound",
    "components": ["bar", "tender"],
    "prefixes": [],
    "suffixes": [],
    "is_compound": true,
    "etymology_template": "{{compound|en|bar|tender}}"
  }
}
```

**Complex affixed word (ejector)**:
```json
{
  "morphology": {
    "type": "suffixed",
    "base": "eject",
    "components": ["eject", "-or"],
    "prefixes": [],
    "suffixes": ["-or"],
    "is_compound": false,
    "etymology_template": "{{suffix|en|eject|or}}"
  }
}
```

**Notes on morphology field:**
- Only present for words with explicit etymology templates in Wiktionary
- Coverage: Estimated ~500,000+ entries (derived and compound words)
- Enables powerful queries: "Find all words with suffix -ness", "Show compounds", "Words from base 'happy'"
- Useful for vocabulary learning, morphological analysis, word family grouping

#### `concreteness` (string)

Concreteness classification for nouns.

- **Values**: `concrete`, `abstract`, `mixed`
- **Source**: Primarily from Brysbaert et al. (2014), with WordNet as fallback
- **Example**: `"concrete"` for "castle", `"abstract"` for "freedom", `"mixed"` for "paper"

**What is concreteness?**
Concreteness measures how tangible or perceptible a concept is. Concrete words refer to things you can experience with your senses (see, touch, hear, smell, taste), while abstract words refer to ideas, emotions, or qualities that exist only conceptually.

**Categories:**
- `concrete`: Physical, tangible objects (rating ≥ 3.5)
  - Examples: "castle" (4.67), "apple" (4.83), "hammer" (4.92)
- `abstract`: Ideas, qualities, concepts (rating < 2.5)
  - Examples: "freedom" (1.46), "justice" (1.93), "theory" (2.07)
- `mixed`: Words with both concrete and abstract senses (rating 2.5-3.5)
  - Examples: "paper" (3.21), "bar" (3.17), "culture" (2.62)

**Notes:**
- Only present for nouns
- ~112,727 nouns have concreteness data (~8.6% of all entries)
- Brysbaert provides better coverage (~40k words) than WordNet alone (~20-30k)

#### `concreteness_rating` (number)

Raw concreteness score from Brysbaert et al. (2014) dataset.

- **Range**: 1.0 (most abstract) to 5.0 (most concrete)
- **Precision**: Rounded to 2 decimal places
- **Source**: Crowdsourced ratings from multiple participants
- **Example**: 4.67 for "castle", 1.46 for "freedom", 3.21 for "paper"

**Use cases:**
- **Fine-grained filtering**: Set custom thresholds beyond the predefined categories
- **Scoring/ranking**: Sort words by concreteness for progressive difficulty
- **Weighted selection**: Prefer more concrete/abstract words without hard cutoffs

**Notes:**
- Only present when word has Brysbaert data (~39,561 entries)
- More precise than categorical `concreteness` field
- Use with `concreteness_sd` to assess rating confidence

#### `concreteness_sd` (number)

Standard deviation of Brysbaert concreteness ratings.

- **Range**: 0.0 to ~2.0 (typical range 0.5-1.5)
- **Precision**: Rounded to 2 decimal places
- **Source**: Variability in crowdsourced ratings
- **Example**: 0.62 for "bar", 1.52 for "blip", 0.86 for "freedom"

**Interpretation:**
- **Low SD (< 0.8)**: High agreement among raters, reliable rating
  - Example: "castle" (SD=0.62) - clearly concrete
- **Medium SD (0.8-1.2)**: Moderate agreement, word may have multiple senses
  - Example: "bar" (SD=0.86) - concrete object vs abstract concept
- **High SD (> 1.2)**: Low agreement, ambiguous or polysemous word
  - Example: "blip" (SD=1.52) - meaning varies by context

**Use cases:**
- **Confidence filtering**: Exclude words with high SD (ambiguous meanings)
- **Quality control**: Prefer low-SD words for educational content
- **Weighted scoring**: Combine rating with confidence (e.g., `rating / (1 + sd)`)

**Notes:**
- Only present when word has Brysbaert data
- Lower SD indicates more reliable concreteness rating
- Useful for distinguishing polysemous words from clear-cut cases

#### `syllables` (integer)

Number of syllables in the word.

- **Source**: Wiktionary (hyphenation > rhymes > category labels)
- **Range**: 1-15 (typical range 1-6)
- **Coverage**: ~2-3% of entries (~30,000 words)
- **Default**: Not present (only included when reliably sourced)
- **Example**: 4 for "dictionary", 1 for "cat", 6 for "encyclopedia"

**What is syllable count?**
A syllable is a unit of pronunciation containing a vowel sound. Syllable count is useful for pronunciation practice, poetry meter, reading level assessment, and children's games.

**Source Priority:**
1. **Hyphenation template** (highest priority): `{{hyphenation|en|dic|tion|a|ry}}` → 4 syllables
2. **Rhymes template**: `{{rhymes|en|ɪkʃənɛəɹi|s=4}}` → 4 syllables
3. **Category labels** (lowest priority): `[[Category:English 4-syllable words]]` → 4 syllables

**Examples:**
- **1 syllable**: "cat", "dog", "run", "jump"
- **2 syllables**: "table", "button", "happy", "window"
- **3 syllables**: "elephant", "beautiful", "together"
- **4 syllables**: "dictionary", "information", "elevator"
- **6 syllables**: "encyclopedia", "telecommunications"

**Philosophy:**
- **Never guessed**: Only included when Wiktionary provides explicit syllable data
- **Missing data is acceptable**: Absence indicates no reliable data, not incorrect data
- **Quality over coverage**: 30k high-quality entries better than 1M estimated entries

**Use Cases:**
- **Children's word games**: Filter for 2-syllable concrete nouns
  - Example spec: `{"syllables": {"exact": 2, "require_syllables": true}}`
- **Poetry and meter**: Find words with specific syllable counts
  - Example: 5-syllable words for haiku composition
- **Reading level**: Shorter syllable counts correlate with easier words
  - Example: 1-3 syllables for beginning readers
- **Pronunciation practice**: Group words by syllable complexity
  - Example: Multi-syllable words (4+) for advanced learners

**Filtering Options:**
- `min`: Minimum syllable count (inclusive)
- `max`: Maximum syllable count (inclusive)
- `exact`: Exact syllable count required
- `require_syllables`: If true, exclude words without syllable data

**Notes:**
- Data extracted from Wiktionary hyphenation, rhymes, and category templates
- Human-curated by Wiktionary editors (not algorithmic estimates)
- Coverage is sparse but highly accurate
- Use `require_syllables: true` in filters to ensure all results have data
- Missing data does NOT mean the word is invalid for other use cases

#### `frequency_tier` (string)

Frequency rank code using logarithmic scale (A-Z).

- **Format**: Single letter A-Z
- **Scale**: Base B = 10^(1/4) ≈ 1.778 (fourth root of 10)
- **Range**: A (rank 1, most frequent) to Z (extremely rare/unranked)
- **Example**: `"M"` for rank ~1000, `"Q"` for rank ~10,000

**Key Tiers:**
| Code | Center Rank | Rank Range | Description |
|------|------------:|-----------|-------------|
| A | 1 | 1 | The single most frequent word ("the") |
| E | 10 | 8-13 | Core function words |
| I | 100 | 75-133 | High-frequency core vocabulary |
| M | 1,000 | 750-1,333 | Simple everyday vocabulary |
| Q | 10,000 | 7,499-13,335 | General educated vocabulary |
| T | ~56,000 | 42,170-74,989 | Extended/literary vocabulary |
| Z | - | 1,333,522+ | Extremely rare or unranked words |

**Notes:**
- Each letter represents a geometric frequency band
- Logarithmic spacing ensures even distribution across frequency spectrum
- ~96.5% of entries are tier Z (not in frequency data)
- Tiers A-T cover the top ~75,000 most frequent words
- See [frequency_tiers.py](../src/openword/frequency_tiers.py) for complete tier definitions

---

## Multi-word Entries and Phrase Types

The lexicon includes multi-word expressions with detailed classification beyond the simple `is_phrase` boolean. This section explains how different types of phrases are identified and classified.

### Word Count Classification

#### `word_count` (integer)

Number of words in the entry, determined by splitting on spaces.

- **Calculation**: `len(word.split())`
- **Example**: `"cat"` → 1, `"give up"` → 2, `"kick the bucket"` → 3

**Single-word entries** (`word_count == 1`):
- No spaces in the entry
- May have hyphens (`self-aware`) or apostrophes (`don't`)
- Examples: `cat`, `dictionary`, `run`, `beautiful`

**Multi-word entries** (`word_count > 1`):
- Multiple words separated by spaces
- Further classified by `phrase_type`
- Examples: `give up`, `Pope Julius`, `kick the bucket`

### Phrase Type Classification

#### `phrase_type` (string or null)

Detailed classification for multi-word expressions.

- **Default**: `null` (no specific type)
- **Values**: `idiom`, `proverb`, `prepositional phrase`, `adverbial phrase`, `verb phrase`, `noun phrase`

#### Phrase Type Taxonomy

##### 1. **Generic Phrases** (`phrase_type == null`)

Multi-word entries without specific classification.

- **Characteristics**: Multiple words, no special type
- **Examples**: `Pope Julius`, `red car`, `go to`
- **Detection**: Has spaces but no idiom/proverb/etc. markers

##### 2. **Idioms** (`phrase_type == 'idiom'`)

Non-literal, figurative expressions.

- **Characteristics**: Meaning not derivable from individual words
- **Examples**: `kick the bucket`, `let the cat out of the bag`, `break the ice`
- **Detection**:
  - Section header: `===Idiom===`
  - Template: `{{head|en|idiom}}`
  - Category: `[[Category:English idioms]]`

**Wiktionary markup example**:
```wikitext
===Idiom===
{{head|en|idiom}}

# {{lb|en|idiomatic}} To reveal a secret.

[[Category:English idioms]]
```

##### 3. **Proverbs** (`phrase_type == 'proverb'`)

Complete sentences expressing wisdom or advice.

- **Characteristics**: Traditional sayings, often metaphorical
- **Examples**: `a stitch in time saves nine`, `don't count your chickens before they hatch`
- **Detection**:
  - Section header: `===Proverb===`, `===Saying===`, `===Adage===`
  - Template: `{{head|en|proverb}}`
  - Category: `[[Category:English proverbs]]`, `[[Category:English sayings]]`

##### 4. **Prepositional Phrases** (`phrase_type == 'prepositional phrase'`)

Phrases starting with a preposition.

- **Characteristics**: Functions as a modifier
- **Examples**: `at least`, `on hold`, `in spite of`, `by right`
- **Detection**:
  - Section header: `===Prepositional phrase===`
  - Template: `{{en-prepphr}}`
  - Category: `[[Category:English prepositional phrases]]`

##### 5. **Adverbial Phrases** (`phrase_type == 'adverbial phrase'`)

Phrases functioning as adverbs.

- **Characteristics**: Modifies verbs, adjectives, or other adverbs
- **Examples**: `all of a sudden`, `step by step`, `little by little`
- **Detection**:
  - Section header: `===Adverbial phrase===`
  - Template: `{{head|en|adverbial phrase}}`
  - Category: `[[Category:English adverbial phrases]]`

##### 6. **Verb Phrases** (`phrase_type == 'verb phrase'`)

Multi-word verb expressions, often phrasal verbs.

- **Characteristics**: Verb with particles or multiple words
- **Examples**: `give up`, `take over`, `put up with`, `look forward to`
- **Detection**:
  - Section header: `===Verb phrase===`
  - Template: `{{head|en|verb phrase}}`
  - Category: `[[Category:English verb phrases]]`

##### 7. **Noun Phrases** (`phrase_type == 'noun phrase'`)

Multi-word expressions functioning as nouns.

- **Characteristics**: Named entities, compound nouns
- **Examples**: `red herring`, `sitting duck`, `white elephant`
- **Detection**:
  - Section header: `===Noun phrase===`
  - Template: `{{head|en|noun phrase}}`
  - Category: `[[Category:English noun phrases]]`

### Detection Priority

The phrase type extraction checks Wiktionary markup in this order:

1. **Section headers** (`===Idiom===`, `===Proverb===`, etc.)
   - Most reliable signal
   - Explicitly defined by Wiktionary editors

2. **Templates** (`{{head|en|idiom}}`, `{{en-prepphr}}`)
   - Structured metadata
   - Often present even without section headers

3. **Categories** (`[[Category:English idioms]]`)
   - Fallback signal
   - Applied automatically by templates

### Phrase Type Examples

**Entry with phrase type**:
```json
{
  "word": "kick the bucket",
  "pos": ["phrase"],
  "word_count": 3,
  "phrase_type": "idiom",
  "sources": ["wikt"]
}
```

**Multi-word without phrase type**:
```json
{
  "word": "Pope Julius",
  "pos": ["noun"],
  "word_count": 2,
  "phrase_type": null,
  "sources": ["wikt"]
}
```

### Filtering by Phrase Type

Applications can filter using phrase metadata:

**Single words only**:
```python
word_count == 1
```

**Exclude proverbs**:
```python
phrase_type != 'proverb'
```

**Only idioms**:
```python
phrase_type == 'idiom'
```

**Phrases but not proverbs or idioms**:
```python
word_count > 1 and phrase_type not in ['proverb', 'idiom']
```

### Phrase Type Summary

| Type | word_count | phrase_type | Example |
|------|-----------|-------------|---------|
| Word | 1 | - | `cat` |
| Generic Phrase | >1 | `null` | `Pope Julius` |
| Idiom | >1 | `idiom` | `kick the bucket` |
| Proverb | >1 | `proverb` | `a stitch in time saves nine` |
| Prep. Phrase | >1 | `prepositional phrase` | `by right` |
| Adv. Phrase | >1 | `adverbial phrase` | `all of a sudden` |
| Verb Phrase | >1 | `verb phrase` | `give up` |
| Noun Phrase | >1 | `noun phrase` | `red herring` |

---

## Examples

### Minimal Entry (Core)

```json
{
  "word": "castle",
  "pos": [],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "sources": ["enable", "eowl"]
}
```

### Enriched Entry (After WordNet + Brysbaert + Frequency)

```json
{
  "word": "castle",
  "pos": ["noun", "verb"],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "concreteness": "concrete",
  "concreteness_rating": 4.67,
  "concreteness_sd": 0.62,
  "frequency_tier": "P",
  "sources": ["enable", "eowl", "brysbaert"]
}
```

### Fully Labeled Entry (Plus)

```json
{
  "word": "colour",
  "pos": ["adjective", "noun", "verb"],
  "labels": {
    "region": ["en-GB"]
  },
  "is_phrase": false,
  "lemma": null,
  "concreteness": "mixed",
  "frequency_tier": "P",
  "sources": ["enable", "eowl", "wikt"]
}
```

### Vulgar/Offensive Word

```json
{
  "word": "asshole",
  "pos": ["noun"],
  "labels": {
    "register": ["offensive", "vulgar"]
  },
  "is_phrase": false,
  "lemma": null,
  "concreteness": "concrete",
  "frequency_tier": "U",
  "sources": ["wikt"]
}
```

### Archaic Word

```json
{
  "word": "thou",
  "pos": ["pronoun"],
  "labels": {
    "temporal": ["archaic"]
  },
  "is_phrase": false,
  "lemma": null,
  "frequency_tier": "U",
  "sources": ["wikt"]
}
```

### Multi-word Phrase

```json
{
  "word": "give up",
  "pos": ["verb"],
  "labels": {},
  "is_phrase": true,
  "lemma": null,
  "frequency_tier": "M",
  "sources": ["wikt"]
}
```

### Inflected Form

```json
{
  "word": "running",
  "pos": ["verb"],
  "labels": {},
  "is_phrase": false,
  "lemma": "run",
  "frequency_tier": "I",
  "sources": ["wikt"]
}
```

### Derived Word (Suffixed)

```json
{
  "word": "happiness",
  "pos": ["noun"],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "morphology": {
    "type": "suffixed",
    "base": "happy",
    "components": ["happy", "-ness"],
    "prefixes": [],
    "suffixes": ["-ness"],
    "is_compound": false,
    "etymology_template": "{{suffix|en|happy|ness}}"
  },
  "concreteness": "abstract",
  "concreteness_rating": 2.28,
  "concreteness_sd": 1.12,
  "frequency_tier": "N",
  "sources": ["enable", "wikt", "brysbaert"]
}
```

### Derived Word (Affixed)

```json
{
  "word": "unbreakable",
  "pos": ["adjective"],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "morphology": {
    "type": "affixed",
    "base": "break",
    "components": ["un-", "break", "-able"],
    "prefixes": ["un-"],
    "suffixes": ["-able"],
    "is_compound": false,
    "etymology_template": "{{affix|en|un-|break|-able}}"
  },
  "frequency_tier": "Q",
  "sources": ["enable", "wikt"]
}
```

### Compound Word

```json
{
  "word": "bartender",
  "pos": ["noun"],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "morphology": {
    "type": "compound",
    "components": ["bar", "tender"],
    "prefixes": [],
    "suffixes": [],
    "is_compound": true,
    "etymology_template": "{{compound|en|bar|tender}}"
  },
  "concreteness": "concrete",
  "frequency_tier": "Q",
  "sources": ["enable", "wikt"]
}
```

---

## Validation

### JSON Schema

The schema is defined using JSON Schema Draft 7:

```bash
# Validate syntax
jq '.' docs/schema/entry.schema.json

# Validate an entry (requires ajv-cli or similar)
echo '{"word":"test","sources":["enable"]}' | ajv validate -s docs/schema/entry.schema.json
```

### Manual Validation Checklist

✅ **Required fields present:**
- `word` (non-empty string)
- `sources` (non-empty array)

✅ **Normalization:**
- `word` in Unicode NFKC form
- `word` lowercased

✅ **Value constraints:**
- `pos` values in allowed set
- `labels.region` matches pattern `en-XX`
- `labels.*` values in allowed sets
- `frequency_tier` in allowed set
- `concreteness` in allowed set (if present)

✅ **Logical consistency:**
- `concreteness` only present for nouns
- `lemma` different from `word` (if not null)
- `is_phrase` true if `word` contains spaces

---

## Schema Evolution

### Version History

- **v1.0 (2025-11-07)**: Initial schema for Phases 4-9
- **v1.1 (2025-11-17)**: Added `morphology` field for derivation tracking and morpheme analysis

### Future Extensions

Potential additions (not yet implemented):

- `pronunciation`: IPA transcription
- `etymology_chain`: Full etymology history with language origins
- `senses`: Multiple definitions per word
- `relations`: Synonyms, antonyms, etc.
- `examples`: Usage examples

---

## Implementation Notes

### Merging Entries

When merging entries from multiple sources:

1. **Union POS tags**: Combine all unique POS values
2. **Union labels**: Combine all unique label values per category
3. **Prefer non-null**: For scalar fields (lemma, concreteness)
4. **Union sources**: Combine all source IDs
5. **Prefer better tier**: Choose more frequent tier (top10 > rare)

Example merge:

```python
def merge_entries(entry1, entry2):
    """Merge two entries for the same word."""
    return {
        'word': entry1['word'],
        'pos': sorted(set(entry1['pos'] + entry2['pos'])),
        'labels': union_labels(entry1['labels'], entry2['labels']),
        'is_phrase': entry1['is_phrase'] or entry2['is_phrase'],
        'lemma': entry1['lemma'] or entry2['lemma'],
        'concreteness': entry1.get('concreteness') or entry2.get('concreteness'),
        'frequency_tier': min_tier(entry1['frequency_tier'], entry2['frequency_tier']),
        'sources': sorted(set(entry1['sources'] + entry2['sources']))
    }
```

---

## See Also

- [labels.md](../docs/labels.md) — Full label taxonomy
- [DATASETS.md](DATASETS.md) — Source dataset details
- [DESIGN.md](DESIGN.md) — Architecture decisions
