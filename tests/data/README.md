# Test Data

This directory contains test specifications for the owlex word list generator.

## Test Specs

- `test-mini-wordle.yaml` - Very small 5-letter word list (tier A-B only)
- `test-animals.yaml` - Generic 3-8 letter common words

## Known Limitations

The owlex filter reads from `data/intermediate/en-lexemes-enriched.jsonl` which has **limited fields**:

### Fields Always Present
- `word` - The word
- `frequency_tier` - A-Z tier (A = most common)
- `sources` - Data sources (wikt, eowl, wordnet)
- `word_count` - Number of words (1 = single word, 2+ = phrase)
- `sense_count`, `sense_offset`, `sense_length` - Links to senses file
- `license_sources` - License information per source

### Fields Sometimes Present
- `syllables` - ~20% coverage
- `morphology` - ~5% coverage
- `concreteness` - ~3% coverage (from Brysbaert dataset)
- `lexnames` - Rare (WordNet semantic categories)
- `spelling_region` - Rare (en-US vs en-GB)
- `is_phrase` - ~5% (multi-word entries)

### Fields NOT Present (in senses file only)
- `pos` - Part of speech tags
- `labels` / `register_tags` - Register labels (vulgar, slang, etc.)
- `temporal_tags` - Temporal labels (archaic, obsolete)
- `domain_tags` - Domain labels (medical, legal)
- `region_tags` - Regional labels

## Bug: Label/POS Filters Don't Work

The following filter types will return 0 or incorrect results:

```yaml
# BROKEN - labels not in lexemes file
labels:
  register:
    exclude: [vulgar, offensive]

# BROKEN - POS not in lexemes file
pos:
  include: [noun]

# BROKEN - temporal labels not in lexemes file
temporal:
  exclude: [archaic, obsolete]
```

### Workaround

For POS and label filtering, use the two-file pipeline with `filters.py`:

```bash
python -m openword.filters INPUT OUTPUT \
    --senses data/intermediate/en-senses.jsonl \
    --pos noun --no-profanity
```

## Filters That Work

These filters work correctly with the lexemes file:

```yaml
# Character filters
character:
  exact_length: 5
  pattern: "^[a-z]+$"

# Phrase filters
phrase:
  max_words: 1

# Frequency filters
frequency:
  min_tier: A
  max_tier: I

# Source filters
sources:
  include: [wordnet]

# Syllable filters (requires syllable data - ~20% coverage)
syllables:
  min: 1
  max: 3
```
