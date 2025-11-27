# Filtering Guide

Create custom word lists by filtering the lexicon.

## Methods

1. **Web Builder** — Interactive visual interface
2. **JSON Specs** — Reusable filter configurations
3. **Python** — Direct filtering in code
4. **jq** — Command-line JSON processing

## Web Builder

```bash
make wordlist-builder-web
# Opens http://localhost:8000
```

The web builder lets you:
- Select filter criteria visually
- See live word count estimates
- Export JSON specifications
- Download filtered word lists

## JSON Specifications

Create a JSON file describing your filters:

```json
{
  "version": "1.0",
  "distribution": "en",
  "filters": {
    "character": {
      "exact_length": 5,
      "char_preset": "standard"
    },
    "frequency": {
      "max_tier": "M"
    },
    "policy": {
      "family_friendly": true
    }
  },
  "output": {
    "format": "text",
    "sort_by": "alphabetical"
  }
}
```

Run with:

```bash
uv run python -m openword.owlex my-spec.json > words.txt
uv run python -m openword.owlex my-spec.json --verbose --output words.txt
```

## Filter Reference

### Character Filters

| Option | Type | Description |
|--------|------|-------------|
| `exact_length` | int | Exact character count |
| `min_length` | int | Minimum characters |
| `max_length` | int | Maximum characters |
| `char_preset` | string | Character set (see below) |
| `pattern` | string | Regex pattern to match |
| `starts_with` | string/list | Required prefix(es) |
| `ends_with` | string/list | Required suffix(es) |
| `contains` | string/list | Required substring(s) |
| `exclude_starts_with` | string/list | Excluded prefix(es) |
| `exclude_ends_with` | string/list | Excluded suffix(es) |
| `exclude_contains` | string | Excluded characters |

**Character Presets**:

| Preset | Allowed Characters |
|--------|-------------------|
| `standard` | a-z only |
| `contractions` | a-z and apostrophe |
| `hyphenated` | a-z and hyphen |
| `common-punct` | a-z, apostrophe, hyphen |
| `alphanumeric` | a-z and digits |
| `any` | All characters |

### Phrase Filters

| Option | Type | Description |
|--------|------|-------------|
| `min_words` | int | Minimum word count |
| `max_words` | int | Maximum word count |
| `is_phrase` | bool | true = multi-word only, false = single words |

### Frequency Filters

| Option | Type | Description |
|--------|------|-------------|
| `tiers` | list | Specific tiers to include (e.g., `["A", "B", "C"]`) |
| `min_tier` | string | Most frequent tier (closer to A) |
| `max_tier` | string | Least frequent tier (closer to Z) |

Example tier ranges:
- `"max_tier": "M"` — Top ~1,300 words
- `"max_tier": "Q"` — Top ~13,000 words
- `"max_tier": "T"` — Top ~75,000 words

### POS Filters

| Option | Type | Description |
|--------|------|-------------|
| `include` | list | Required POS tags (any match) |
| `exclude` | list | Excluded POS tags (all excluded) |
| `require_pos` | bool | Require POS data to exist |

POS tags: `noun`, `verb`, `adjective`, `adverb`, `pronoun`, `preposition`, `conjunction`, `interjection`, `determiner`, `particle`, `proper noun`

### Concreteness Filters

| Option | Type | Description |
|--------|------|-------------|
| `values` | list | Allowed classifications |
| `require_concreteness` | bool | Require concreteness data |

Values: `"concrete"` (4.0+), `"abstract"` (<2.5), `"mixed"` (2.5-4.0)

### Label Filters

Filter by register, region, domain, or temporal labels:

```json
{
  "labels": {
    "register": {
      "exclude": ["vulgar", "offensive", "derogatory"]
    },
    "temporal": {
      "exclude": ["archaic", "obsolete"]
    },
    "region": {
      "include": ["en-US"]
    }
  }
}
```

### Policy Filters

Shorthand for common label combinations:

| Option | Effect |
|--------|--------|
| `family_friendly` | Exclude vulgar, offensive, derogatory |
| `modern_only` | Exclude archaic, obsolete, dated |
| `no_jargon` | Exclude medical, legal, technical, scientific |

### Source Filters

```json
{
  "sources": {
    "include": ["eowl", "wordnet"],
    "exclude": ["wikt"]
  }
}
```

### Spelling Region Filters

For regional spelling variants (color/colour):

```json
{
  "spelling_region": {
    "region": "en-US",
    "include_universal": true
  }
}
```

### Syllable Filters

| Option | Type | Description |
|--------|------|-------------|
| `min` | int | Minimum syllables |
| `max` | int | Maximum syllables |
| `exact` | int | Exact syllable count |
| `require_syllables` | bool | Require syllable data |

### Lemma Filters

Filter based on word forms and their base (dictionary) forms:

| Option | Type | Description |
|--------|------|-------------|
| `base_forms_only` | bool | Exclude inflected forms (plurals, conjugations) |
| `exclude_inflected` | bool | Same as `base_forms_only` |

**Examples:**

Get only base forms (dictionary entries, no "cats", "running", "went"):
```json
{
  "lemma": {
    "base_forms_only": true
  }
}
```

**Advanced: Two-File Filtering**

For precise lemma-based filtering using sense-level data:

```bash
python -m openword.filters INPUT OUTPUT \
    --senses data/intermediate/en-senses.jsonl \
    --base-forms-only
```

This uses the senses file which contains per-sense lemma data, correctly handling words like "left" that have multiple lemmas depending on meaning.

### Lexname Filters (Semantic Categories)

Filter by WordNet semantic category using the `lexnames` field:

| Option | Type | Description |
|--------|------|-------------|
| `include` | string[] | Include words with any of these lexnames |
| `exclude` | string[] | Exclude words with any of these lexnames |
| `require_lexnames` | bool | Only include words with lexname data |

**Examples:**

Get only animal words:
```json
{
  "lexnames": {
    "include": ["noun.animal"]
  }
}
```

Get concrete nouns (good for children's games):
```json
{
  "lexnames": {
    "include": [
      "noun.animal",
      "noun.artifact",
      "noun.body",
      "noun.food",
      "noun.plant",
      "noun.object"
    ]
  }
}
```

Get all words except abstract concepts:
```json
{
  "lexnames": {
    "exclude": [
      "noun.cognition",
      "noun.feeling",
      "noun.state",
      "noun.attribute"
    ]
  }
}
```

**Command-line filtering:**

```bash
# Get all animal words
jq -r 'select(.lexnames // [] | any(. == "noun.animal")) | .word' \
    data/intermediate/en-lexemes-enriched.jsonl

# Get all food and plant words
jq -r 'select(.lexnames // [] | any(. == "noun.food" or . == "noun.plant")) | .word' \
    data/intermediate/en-lexemes-enriched.jsonl
```

See [SCHEMA.md](SCHEMA.md#lexnames-wordnet-semantic-categories) for the complete list of 45 lexname categories.

## Output Options

```json
{
  "output": {
    "format": "text",
    "sort_by": "alphabetical",
    "limit": 1000,
    "include_metadata": false,
    "metadata_fields": ["word", "frequency_tier", "pos"]
  }
}
```

| Option | Values |
|--------|--------|
| `format` | `text`, `json`, `jsonl`, `csv`, `tsv` |
| `sort_by` | `alphabetical`, `frequency`, `score`, `length` |
| `limit` | Maximum words to output |
| `include_metadata` | Include metadata in output |
| `metadata_fields` | Which fields to include |

## Example Specifications

### Wordle (5-letter common words)

```json
{
  "version": "1.0",
  "distribution": "en",
  "filters": {
    "character": {
      "exact_length": 5,
      "char_preset": "standard"
    },
    "frequency": {
      "max_tier": "Q"
    },
    "phrase": {
      "max_words": 1
    },
    "policy": {
      "family_friendly": true
    }
  },
  "output": {
    "format": "text",
    "sort_by": "frequency"
  }
}
```

### Kids Vocabulary

```json
{
  "version": "1.0",
  "distribution": "en",
  "filters": {
    "character": {
      "min_length": 3,
      "max_length": 8,
      "char_preset": "standard"
    },
    "pos": {
      "include": ["noun"]
    },
    "concreteness": {
      "values": ["concrete"]
    },
    "frequency": {
      "max_tier": "N"
    },
    "policy": {
      "family_friendly": true,
      "modern_only": true
    }
  }
}
```

### Scrabble Dictionary

```json
{
  "version": "1.0",
  "distribution": "en",
  "filters": {
    "character": {
      "min_length": 2,
      "max_length": 15,
      "char_preset": "standard"
    },
    "phrase": {
      "max_words": 1
    },
    "proper_noun": {
      "require_common_usage": true
    }
  },
  "output": {
    "format": "text",
    "sort_by": "alphabetical"
  }
}
```

### Profanity Blocklist

```json
{
  "version": "1.0",
  "distribution": "en",
  "filters": {
    "labels": {
      "register": {
        "include": ["vulgar", "offensive", "derogatory"]
      }
    }
  },
  "output": {
    "format": "text"
  }
}
```

## Python Filtering

For more control, filter directly in Python:

```python
import json

def load_lexemes(path='data/intermediate/en-lexemes-enriched.jsonl'):
    with open(path) as f:
        for line in f:
            yield json.loads(line)

# Custom filter function
def is_wordle_word(entry):
    word = entry['word']
    return (
        len(word) == 5 and
        word.isalpha() and
        word.islower() and
        entry.get('frequency_tier', 'Z') <= 'Q'
    )

wordle_words = [e['word'] for e in load_lexemes() if is_wordle_word(e)]
```

## jq Filtering

For quick ad-hoc filtering:

```bash
# 5-letter words
jq -r 'select(.word | length == 5) | .word' \
    data/intermediate/en-lexemes-enriched.jsonl

# Common nouns
jq -r 'select(
    (.pos // [] | contains(["noun"])) and
    (.frequency_tier // "Z") <= "M"
) | .word' data/intermediate/en-lexemes-enriched.jsonl

# Words with concreteness data
jq -r 'select(.concreteness != null) | "\(.word)\t\(.concreteness)"' \
    data/intermediate/en-lexemes-enriched.jsonl
```

## Pre-built Specifications

Example specs in `examples/wordlist-specs/`:

| File | Description |
|------|-------------|
| `wordle.json` | 5-letter common words |
| `kids-nouns.json` | Concrete nouns for children |
| `scrabble.json` | Single words for Scrabble |
| `profanity-blocklist.json` | Flagged inappropriate words |

## Coverage Notes

Not all words have all metadata:

| Field | Coverage |
|-------|----------|
| `frequency_tier` | 100% (unranked = Z) |
| `sources` | 100% |
| `pos` | ~52% |
| `concreteness` | ~3% (~39K words) |
| `syllables` | ~2% (~30K words) |
| `labels` | ~11% |

When filtering by optional fields, consider using `require_*` options to exclude words without data, or accept that some words may pass filters by default.
