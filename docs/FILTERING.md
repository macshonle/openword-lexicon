# Filtering Guide

Create custom word lists by filtering the lexicon.

## Quick Start

```bash
# Generate word list from YAML spec
owlex examples/wordlist-specs/wordle.yaml --output words.txt

# With enriched metadata sidecar
owlex wordle.yaml --output words.txt --enriched enriched.jsonl

# Extract specific fields with jq
owlex wordle.yaml --enriched data.jsonl --jq '{word, syllables, pos}'
```

## Methods

1. **owlex CLI** — Generate word lists from YAML specifications
2. **Web Builder** — Interactive visual interface
3. **Makefile** — Pre-configured targets
4. **Python** — Direct filtering in code

## owlex CLI

The `owlex` command is the primary tool for generating filtered word lists.

```bash
# Basic usage - outputs to stdout
owlex examples/wordlist-specs/wordle.yaml

# Save to file
owlex wordle.yaml --output words.txt

# With enriched metadata sidecar (JSONL)
owlex wordle.yaml --output words.txt --enriched enriched.jsonl

# Extract specific fields with jq projection
owlex wordle.yaml --enriched data.jsonl --jq '{word, syllables}'

# Verbose mode (shows filter statistics)
owlex wordle.yaml --output words.txt --verbose
```

## YAML Specifications

Create a YAML file with your filters. The spec body IS the filters - no wrapper needed:

```yaml
# wordle.yaml - 5-letter common words

character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I
```

This simplified format:
- No `version`, `distribution`, or `output` sections needed
- Output format controlled via CLI flags (`--output`, `--enriched`, `--jq`)
- Filters are the entire spec body

## Web Builder

```bash
make wordlist-builder-web
# Opens http://localhost:8000
```

The web builder lets you:
- Select filter criteria visually
- See live word count estimates
- Export YAML specifications
- Download filtered word lists

## Makefile Targets

Generate word lists using make:

```bash
# Generate all example word lists
make wordlists

# Individual targets
make wordlist-wordle      # 5-letter common words
make wordlist-kids-nouns  # Concrete nouns for children
make wordlist-scrabble    # Scrabble dictionary
make wordlist-profanity   # Profanity blocklist

# Custom spec with enriched output
make wordlist-enriched SPEC=my-spec.yaml NAME=my-words
```

## Filter Reference

### Character Filters

```yaml
character:
  exact_length: 5       # Exactly N characters
  min_length: 3         # At least N characters
  max_length: 10        # At most N characters
  pattern: "^[a-z]+$"   # Regex pattern to match
  starts_with: [un, re] # Prefix(es) - matches any
  ends_with: [ing, ed]  # Suffix(es) - matches any
  contains: [tion]      # Substring(s) - must have all
```

| Option | Type | Description |
|--------|------|-------------|
| `exact_length` | int | Exact character count |
| `min_length` | int | Minimum characters |
| `max_length` | int | Maximum characters |
| `pattern` | string | Regex pattern to match |
| `starts_with` | list | Required prefix(es) - matches any |
| `ends_with` | list | Required suffix(es) - matches any |
| `contains` | list | Required substring(s) - must have all |

### Phrase Filters

```yaml
phrase:
  max_words: 1    # Single words only
  min_words: 2    # Multi-word phrases only
```

### Frequency Filters

```yaml
frequency:
  min_tier: A     # Most common tier to include
  max_tier: I     # Least common tier to include
```

**Tier ranges:** A (most common) through Z (unknown)
- A: rank 1 (the, be, to, of, and, a, in, that, have, I)
- B: rank 2-3
- C: rank 4-5
- D: rank 6-10
- E: rank 11-17
- F: rank 18-31
- G: rank 32-56
- H: rank 57-100
- I: rank 101-175
- J: rank 176-316
- K: rank 317-562
- L: rank 563-1000
- M: rank 1001-1778
- N-W: progressively less common
- Z: unknown/unranked

Example ranges:
- `min_tier: A, max_tier: I` — Top ~30,000 words
- `min_tier: A, max_tier: F` — Top ~3,000 words
- `min_tier: A, max_tier: C` — Top ~500 words

### POS Filters

```yaml
pos:
  include: [noun, verb]        # Must have one of these
  exclude: [interjection]      # Must not have any of these
```

POS tags: `noun`, `verb`, `adjective`, `adverb`, `pronoun`, `preposition`, `conjunction`, `interjection`, `determiner`, `particle`, `proper noun`

### Concreteness Filters

```yaml
concreteness:
  values: [concrete]    # concrete, mixed, or abstract
```

Values: `concrete` (4.0+), `abstract` (<2.5), `mixed` (2.5-4.0)

### Label Filters

```yaml
labels:
  register:
    include: [slang]
    exclude: [vulgar, offensive, derogatory]
  domain:
    exclude: [medical, legal, technical]
  region:
    include: [en-US]
```

**Register labels:** vulgar, offensive, slang, informal, formal, colloquial, dialectal, technical, literary, humorous, derogatory, euphemistic

### Temporal Filters

```yaml
temporal:
  exclude: [archaic, obsolete, dated]
```

**Temporal labels:** archaic, obsolete, dated, rare

### Syllable Filters

```yaml
syllables:
  exact: 2              # Exactly N syllables
  min: 1                # At least N syllables
  max: 3                # At most N syllables
  require_syllables: true  # Only words with syllable data
```

### Source Filters (for licensing)

Control which data sources are used:

```yaml
sources:
  include: [wordnet]     # Only words from these sources
  enrichment: [frequency]  # Allow these sources for filtering only
```

This is useful for license compliance - e.g., creating a WordNet-only word list:

```yaml
# wordnet-only.yaml - CC-BY-4.0 compliant
sources:
  include: [wordnet]
  enrichment: [frequency]

character:
  min_length: 3
  max_length: 10

frequency:
  min_tier: A
  max_tier: H
```

### Proper Noun Filters

```yaml
proper_noun:
  require_common_usage: true  # "bill" OK, "Aaron" excluded
```

## Example Specifications

### Wordle (5-letter common words)

```yaml
# wordle.yaml
character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I
```

**Expected:** ~3,000 words

### Kids Vocabulary (Concrete Nouns)

```yaml
# kids-nouns.yaml
character:
  min_length: 3
  max_length: 10

phrase:
  max_words: 1

pos:
  include: [noun]

concreteness:
  values: [concrete]

frequency:
  min_tier: A
  max_tier: G

labels:
  register:
    exclude: [vulgar, offensive, derogatory, slang]

temporal:
  exclude: [archaic, obsolete, dated]
```

### Poetry (5-syllable words)

```yaml
# poetry-5syllable.yaml
syllables:
  exact: 5

temporal:
  exclude: [archaic, obsolete]

labels:
  register:
    exclude: [vulgar, offensive]
```

### Profanity Blocklist

```yaml
# profanity-blocklist.yaml
labels:
  register:
    include: [vulgar, offensive, derogatory]
```

## Enriched Output

The `--enriched` flag creates a JSONL sidecar file with full metadata:

```bash
owlex wordle.yaml --output words.txt --enriched enriched.jsonl
```

Each line in `enriched.jsonl` contains:
- `word` - The word
- `pos` - Part of speech tags (aggregated from senses)
- `syllables` - Syllable data
- `frequency_tier` - Frequency tier
- `concreteness` - Concreteness rating
- `sources` - Contributing sources

Use `--jq` to project specific fields:

```bash
# Extract word + syllables only
owlex wordle.yaml --enriched data.jsonl --jq '{word, syllables}'

# Morphology lookup
owlex wordle.yaml --enriched data.jsonl --jq '{word, pos, lemmas}'
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
        entry.get('frequency_tier', 'Z') <= 'I'
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
    (.frequency_tier // "Z") <= "F"
) | .word' data/intermediate/en-lexemes-enriched.jsonl

# Words with concreteness data
jq -r 'select(.concreteness != null) | "\(.word)\t\(.concreteness)"' \
    data/intermediate/en-lexemes-enriched.jsonl
```

## Pre-built Specifications

Example specs in `examples/wordlist-specs/`:

| File | Description | Expected Words |
|------|-------------|----------------|
| `wordle.yaml` | 5-letter common words | ~3,000 |
| `kids-nouns.yaml` | Concrete nouns for children | ~500-1,000 |
| `children-2syllable.yaml` | Two-syllable concrete nouns | ~200-500 |
| `poetry-5syllable.yaml` | Five-syllable words | ~50-200 |
| `simple-words.yaml` | Simple words for beginners | ~1,000-3,000 |
| `scrabble.yaml` | Single words for Scrabble | ~100,000+ |
| `profanity-blocklist.yaml` | Vulgar/offensive words | ~10,000 |
| `wordnet-only.yaml` | CC-BY-4.0 compliant | ~50,000+ |

## Coverage Notes

Not all words have all metadata:

| Field | Coverage |
|-------|----------|
| `frequency_tier` | 100% (unranked = Z) |
| `sources` | 100% |
| `pos` | ~98% |
| `labels` | ~11% |
| `concreteness` | ~3% (~39K words) |
| `syllables` | ~2% (~30K words) |

When filtering by optional fields, consider using `require_*` options to exclude words without data, or accept that some words may pass filters by default.

## Two-File Pipeline

For advanced filtering that requires sense-level data (POS per sense, per-sense labels), use the two-file pipeline with `filters.py`:

```bash
python -m openword.filters INPUT OUTPUT \
    --senses data/intermediate/en-senses.jsonl \
    --pos noun --no-profanity
```

This uses the senses file which contains per-sense data, correctly handling words like "left" that have multiple parts of speech.
