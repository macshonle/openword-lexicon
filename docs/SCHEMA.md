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
