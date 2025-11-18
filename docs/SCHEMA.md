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

#### `concreteness` (string)

Concreteness classification for nouns (from WordNet).

- **Values**: `concrete`, `abstract`, `mixed`
- **Example**: `"concrete"` for "castle", `"abstract"` for "freedom", `"mixed"` for "paper"

**Notes:**
- Only present for nouns
- `concrete`: Physical, tangible objects
- `abstract`: Ideas, qualities, concepts
- `mixed`: Both concrete and abstract senses

#### `frequency_tier` (string)

Coarse frequency ranking bucket.

- **Values**: `top10`, `top100`, `top1k`, `top10k`, `top100k`, `rare`
- **Example**: `"top10k"`

**Ranking:**
| Tier | Rank Range | Description |
|------|------------|-------------|
| `top10` | 1-10 | Ultra-frequent words (the, and, be) |
| `top100` | 11-100 | Very frequent |
| `top1k` | 101-1,000 | Frequent |
| `top10k` | 1,001-10,000 | Common |
| `top100k` | 10,001-100,000 | Known |
| `rare` | >100,000 or unseen | Rare/specialized |

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

### Enriched Entry (After WordNet + Frequency)

```json
{
  "word": "castle",
  "pos": ["noun", "verb"],
  "labels": {},
  "is_phrase": false,
  "lemma": null,
  "concreteness": "mixed",
  "frequency_tier": "top10k",
  "sources": ["enable", "eowl"]
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
  "frequency_tier": "top10k",
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
  "frequency_tier": "top100k",
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
  "frequency_tier": "top100k",
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
  "frequency_tier": "top1k",
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
  "frequency_tier": "top1k",
  "sources": ["wikt"]
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

### Future Extensions

Potential additions (not yet implemented):

- `pronunciation`: IPA transcription
- `etymology`: Word origin
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
