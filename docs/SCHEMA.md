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
  "frequency_tier": "H",
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
| `frequency_tier` | string | A-L/Y/Z frequency code (see below) |
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
| `lexnames` | string[] | WordNet semantic categories (e.g., `["noun.animal"]`) |

## Frequency Tiers (A-L, Y, Z)

12-level explicit boundary system based on corpus frequency rank:

| Tier | Rank Range | Description |
|------|------------|-------------|
| A | 1-20 | Universal Anchor |
| B | 21-100 | Grammatical Skeleton |
| C | 101-300 | Semantic Core |
| D | 301-500 | Basic Literacy |
| E | 501-1,000 | Elementary Vocabulary |
| F | 1,001-3,000 | Everyday Lexicon |
| G | 3,001-5,000 | Conversational Mastery |
| H | 5,001-10,000 | Educated Standard |
| I | 10,001-30,000 | Full Adult Repertoire |
| J | 30,001-50,000 | Sophisticated/Erudite |
| K | 50,001-75,000 | Technical/Domain-specific |
| L | 75,001-100,000 | Archaic/Hyperspecialized |
| Y | 100,001+ | Known but very rare |
| Z | unranked | Unknown/unranked |

**Rule of thumb**: Tiers A-F cover the top ~3,000 most frequent words. Tiers A-I cover the top ~30,000.

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

## Lexnames (WordNet Semantic Categories)

Words sourced from WordNet include `lexnames` indicating their semantic categories.
A word can have multiple lexnames if it has multiple senses.

### Noun Categories (26)

| Lexname | Description | Examples |
|---------|-------------|----------|
| `noun.Tops` | Top-level concepts | entity, thing |
| `noun.act` | Acts/actions | movement, creation |
| `noun.animal` | Animals | cat, dog, elephant |
| `noun.artifact` | Man-made objects | table, car, hammer |
| `noun.attribute` | Properties | size, color, speed |
| `noun.body` | Body parts | hand, eye, heart |
| `noun.cognition` | Mental concepts | idea, thought, theory |
| `noun.communication` | Communication | word, message, speech |
| `noun.event` | Events | happening, occasion |
| `noun.feeling` | Emotions | love, anger, joy |
| `noun.food` | Food and drink | apple, bread, milk |
| `noun.group` | Groups | team, family, crowd |
| `noun.location` | Places | city, room, area |
| `noun.motive` | Motives | reason, goal, purpose |
| `noun.object` | Natural objects | rock, star, cloud |
| `noun.person` | People | teacher, friend, hero |
| `noun.phenomenon` | Phenomena | weather, gravity, light |
| `noun.plant` | Plants | tree, flower, grass |
| `noun.possession` | Possessions | property, money, asset |
| `noun.process` | Processes | change, growth, decay |
| `noun.quantity` | Quantities | amount, number, portion |
| `noun.relation` | Relations | connection, link, tie |
| `noun.shape` | Shapes | circle, square, line |
| `noun.state` | States | condition, status, mode |
| `noun.substance` | Substances | water, wood, metal |
| `noun.time` | Time concepts | hour, year, moment |

### Verb Categories (15)

| Lexname | Description |
|---------|-------------|
| `verb.body` | Body functions |
| `verb.change` | Change of state |
| `verb.cognition` | Thinking |
| `verb.communication` | Speaking/writing |
| `verb.competition` | Competition |
| `verb.consumption` | Eating/drinking |
| `verb.contact` | Physical contact |
| `verb.creation` | Creating |
| `verb.emotion` | Feeling |
| `verb.motion` | Movement |
| `verb.perception` | Sensing |
| `verb.possession` | Owning/having |
| `verb.social` | Social interaction |
| `verb.stative` | Being/existing |
| `verb.weather` | Weather |

### Adjective Categories (3)

| Lexname | Description |
|---------|-------------|
| `adj.all` | General adjectives |
| `adj.pert` | Relational adjectives |
| `adj.ppl` | Participial adjectives |

### Adverb Categories (1)

| Lexname | Description |
|---------|-------------|
| `adv.all` | All adverbs |

### Filtering by Lexname

Use lexnames to extract words by semantic category:

```bash
# Get all animal words
jq -r 'select(.lexnames // [] | any(. == "noun.animal")) | .word' \
    data/intermediate/en-lexemes-enriched.jsonl

# Get all food words
jq -r 'select(.lexnames // [] | any(. == "noun.food")) | .word' \
    data/intermediate/en-lexemes-enriched.jsonl
```

## Sense Entry

Each line in `en-senses.jsonl` is a JSON object:

```json
{
  "word": "cats",
  "pos": "noun",
  "is_inflected": true,
  "lemma": "cat"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `word` | string | The word this sense belongs to |
| `pos` | string | Part of speech for this sense |
| `is_inflected` | bool | True if this is an inflected form |
| `is_abbreviation` | bool | True if this is an abbreviation |
| `is_proper_noun` | bool | True if this is a proper noun |
| `lemma` | string? | Base form for inflected words (null for base forms) |
| `register_tags` | string[] | Register labels for this sense |
| `region_tags` | string[] | Region labels for this sense |
| `domain_tags` | string[] | Domain labels for this sense |
| `temporal_tags` | string[] | Temporal labels for this sense |

### Lemma Field

The `lemma` field indicates the base/dictionary form of an inflected word:

```json
{"word": "cats", "pos": "noun", "is_inflected": true, "lemma": "cat"}
{"word": "running", "pos": "verb", "is_inflected": true, "lemma": "run"}
{"word": "went", "pos": "verb", "is_inflected": true, "lemma": "go"}
{"word": "mice", "pos": "noun", "is_inflected": true, "lemma": "mouse"}
```

**Key points:**
- Only present for inflected forms (not base words)
- Stored at sense level because a word can have different lemmas for different senses
- Example: "left" → "leave" (verb past tense) vs "left" as standalone adjective

## Modular Metadata Files

Separate JSON files for specific metadata (gzipped):

### en-frequency.json.gz

```json
{
  "the": "A",
  "castle": "H",
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

### en-lemmas.json.gz

Maps inflected words to their base forms:

```json
{
  "cats": "cat",
  "running": "run",
  "went": "go",
  "mice": "mouse"
}
```

Only includes words where lemma ≠ word (inflected forms only).

### en-lemma-groups.json.gz

Groups words by their base form:

```json
{
  "cat": ["cat", "cats"],
  "run": ["run", "runs", "ran", "running"],
  "go": ["go", "goes", "went", "going", "gone"]
}
```

Base form is always first in the array. Words can appear under multiple lemmas if they have different senses (e.g., "left" appears under both "leave" and "left").

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
