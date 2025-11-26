# Schema Reference

Data format specifications for OpenWord Lexicon files.

## File Overview

The lexicon uses a **two-file format**:

| File | Purpose | Records |
|------|---------|---------|
| `en-lexemes-enriched.jsonl` | Word-level properties | ~1.35M |
| `en-senses.jsonl` | Sense-level properties (POS, labels) | ~2.5M |

Lexeme entries link to senses via `sense_offset` and `sense_length` fields.

## Lexeme Entry

Each line in `en-lexemes-enriched.jsonl` is a JSON object:

```json
{
  "word": "castle",
  "sources": ["eowl", "wikt", "wordnet"],
  "license_sources": {
    "UKACD": ["eowl"],
    "CC-BY-SA-4.0": ["wikt"],
    "CC-BY-4.0": ["wordnet"]
  },
  "frequency_tier": "N",
  "concreteness": 4.97,
  "syllables": 2,
  "sense_offset": 12345,
  "sense_length": 3,
  "pos": ["noun", "verb"],
  "labels": {
    "register": [],
    "region": [],
    "domain": [],
    "temporal": []
  }
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `word` | string | The word (NFKC normalized, lowercase) |
| `sources` | string[] | Origin sources: `"wikt"`, `"eowl"`, `"wordnet"` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `frequency_tier` | string | A-Z frequency code (see below) |
| `concreteness` | float | Brysbaert rating 1.0-5.0 |
| `syllables` | int | Syllable count |
| `pos` | string[] | Parts of speech |
| `labels` | object | Register, region, domain, temporal labels |
| `sense_offset` | int | Byte offset into senses file |
| `sense_length` | int | Number of senses |
| `license_sources` | object | License -> sources mapping |
| `spelling_region` | string | Regional spelling variant (e.g., `"en-US"`, `"en-GB"`) |
| `has_common_usage` | bool | Has non-proper-noun usage |
| `has_proper_usage` | bool | Has proper noun usage |

## Frequency Tiers (A-Z)

Logarithmic scale based on corpus frequency rank:

| Tier | Rank Range | Description | Examples |
|------|------------|-------------|----------|
| A | 1 | Most frequent | the |
| B | 2 | | of |
| C | 3-4 | | and, to |
| D | 5-7 | Ultra-top function words | a, in, is |
| E | 8-13 | Core function words | that, it, was |
| F | 14-23 | Very frequent | for, on, are |
| G | 24-42 | High-frequency | with, as, his |
| H | 43-74 | Very common | at, be, this |
| I | 75-133 | High-frequency core | from, have, or |
| J | 134-237 | Core vocabulary | an, which, one |
| K | 238-421 | Basic everyday | about, would, make |
| L | 422-749 | Common conversational | know, take, come |
| M | 750-1,333 | Simple vocabulary | castle, river, happy |
| N | 1,334-2,371 | Everyday vocabulary | ancient, shoulder |
| O | 2,372-4,216 | Conversational fluency | meadow, triumph |
| P | 4,217-7,498 | Broad fluency | squadron, remnant |
| Q | 7,499-13,335 | Educated vocabulary | adjutant, frigate |
| R | 13,336-23,713 | Lower-mid frequency | fuselage, parapet |
| S | 23,714-42,169 | Standard educated | sextant, galley |
| T | 42,170-74,989 | Extended vocabulary | cutlass, schooner |
| U | 74,990-133,352 | Technical vocabulary | |
| V | 133,353-237,137 | Specialized | |
| W | 237,138-421,696 | Rare | |
| X | 421,697-749,894 | Very rare | |
| Y | 749,895-1,333,521 | Domain-specific | |
| Z | 1,333,522+ | Extremely rare / unranked | zugzwang |

**Rule of thumb**: Tiers A-M cover the top ~1,300 most frequent words. Tiers A-Q cover the top ~13,000.

## Part of Speech Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `noun` | Noun | castle, freedom |
| `verb` | Verb | run, think |
| `adjective` | Adjective | red, happy |
| `adverb` | Adverb | quickly, very |
| `pronoun` | Pronoun | she, they |
| `preposition` | Preposition | in, under |
| `conjunction` | Conjunction | and, but |
| `interjection` | Interjection | wow, ouch |
| `determiner` | Determiner | the, a |
| `particle` | Particle | up (in "give up") |
| `proper noun` | Proper noun | London, John |

## Labels

Labels are organized into four categories:

### Register (Formality/Style)

| Label | Description |
|-------|-------------|
| `formal` | Elevated register |
| `informal` | Casual/conversational |
| `colloquial` | Everyday spoken |
| `slang` | Non-standard, ephemeral |
| `vulgar` | Coarse or crude |
| `offensive` | Potentially insulting |
| `derogatory` | Belittling |
| `euphemistic` | Indirect/softened |
| `humorous` | Playful/jocular |
| `literary` | Poetic or archaic literary |
| `childish` | Baby talk |

### Region (Dialect)

| Label | Description |
|-------|-------------|
| `en-US` | American English |
| `en-GB` | British English |
| `en-AU` | Australian English |
| `en-CA` | Canadian English |
| `en-NZ` | New Zealand English |
| `en-IE` | Irish English |
| `en-ZA` | South African English |
| `en-IN` | Indian English |

### Temporal (Historical Status)

| Label | Description |
|-------|-------------|
| `archaic` | No longer in active use |
| `obsolete` | Completely out of use |
| `dated` | Old-fashioned but understood |
| `historical` | Refers to historical concepts |

### Domain (Subject Field)

| Label | Description |
|-------|-------------|
| `medical` | Medicine/healthcare |
| `legal` | Law and jurisprudence |
| `technical` | Engineering/technology |
| `scientific` | General science |
| `computing` | Computer science |
| `military` | Armed forces |
| `nautical` | Maritime/naval |
| `botanical` | Plant sciences |
| `zoological` | Animal sciences |
| `music` | Musical terminology |
| `sports` | Sports terminology |
| `finance` | Financial terminology |

## Sense Entry

Each line in `en-senses.jsonl` is a JSON object:

```json
{
  "pos": "noun",
  "labels": {
    "register": ["informal"],
    "domain": ["computing"]
  },
  "gloss": "A fortified building"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `pos` | string | Part of speech for this sense |
| `labels` | object | Labels specific to this sense |
| `gloss` | string | Definition (if available) |

## Modular Metadata Files

Separate JSON files for specific metadata (gzipped):

### en-frequency.json.gz

```json
{
  "the": "A",
  "castle": "N",
  "zugzwang": "Z"
}
```

### en-concreteness.json.gz

```json
{
  "apple": 4.93,
  "freedom": 1.73
}
```

Values are Brysbaert concreteness ratings (1.0 = abstract, 5.0 = concrete).

### en-syllables.json.gz

```json
{
  "castle": 2,
  "beautiful": 3
}
```

### en-sources.json.gz

```json
{
  "castle": ["eowl", "wikt", "wordnet"],
  "colour": ["wikt"]
}
```

## Unicode Normalization

All `word` fields are **NFKC normalized** (Unicode Normalization Form KC):

```python
import unicodedata
normalized = unicodedata.normalize('NFKC', word).lower()
```

This ensures consistent representation of accented characters and ligatures.

## Trie Files

MARISA trie files (`.trie`) contain only words, no metadata. Use the modular JSON files or lexemes JSONL for metadata lookup.

| File | Contents |
|------|----------|
| `en.trie` | All words (~1.35M) |
| `en-game.trie` | Pure a-z words only (~330K) |
