# Filtering Guide

Create custom word lists by filtering the lexicon.

## Quick Start

```bash
# Generate word list from YAML spec
owlex examples/wordlist-specs/wordle.yaml --output words.txt

# With enriched metadata sidecar
owlex wordle.yaml --output words.txt --enriched enriched.jsonl

# Extract specific fields with jq
owlex wordle.yaml --enriched data.jsonl --jq '{id, nsyll, pos}'
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
owlex wordle.yaml --enriched data.jsonl --jq '{id, nsyll}'

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

## Spec Editor (Web UI)

```bash
make spec-editor-web
# Opens http://localhost:8000
```

The spec editor lets you:
- Select filter criteria visually
- See live word count estimates
- Export YAML specifications
- Download filtered word lists

## Makefile Targets

Generate word lists using make:

```bash
# Generate all word lists from specs in examples/wordlist-specs/
make wordlists

# Add custom specs to examples/wordlist-specs/ and they'll be auto-discovered
```

Word lists are output to `data/wordlists/` with the same name as the spec file.

For enriched output (JSONL sidecar with metadata), use `owlex` directly:

```bash
# Generate word list with enriched metadata
uv run owlex my-spec.yaml --output words.txt --enriched enriched.jsonl
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
  max_tier: L     # Least common tier to include
```

**Tier ranges:** A (most common) through Z (unknown)

| Tier | Rank Range | Description |
|------|------------|-------------|
| A | 1-20 | Top 20 words |
| B | 21-100 | Top 100 |
| C | 101-200 | Top 200 |
| D | 201-300 | Top 300 |
| E | 301-400 | Top 400 |
| F | 401-500 | Top 500 |
| G | 501-1,000 | Top 1,000 |
| H | 1,001-2,000 | Top 2,000 |
| I | 2,001-3,000 | Top 3,000 |
| J | 3,001-4,000 | Top 4,000 |
| K | 4,001-5,000 | Top 5,000 |
| L | 5,001-10,000 | Top 10,000 |
| M | 10,001-20,000 | Top 20,000 |
| N | 20,001-30,000 | Top 30,000 |
| O | 30,001-40,000 | Top 40,000 |
| P | 40,001-50,000 | Top 50,000 |
| Q-U | 50,001-100,000 | Top 100,000 |
| V-X | 100,001-400,000 | Rare but ranked |
| Y | 400,001+ | Very rare but ranked |
| Z | — | Unknown/unranked |

Example ranges:
- `min_tier: A, max_tier: L` — Top ~10,000 words
- `min_tier: A, max_tier: G` — Top ~1,000 words
- `min_tier: A, max_tier: F` — Top ~500 words

**Note:** Frequency is just one signal for word commonality. For puzzle games, you may also want to consider:
- **Temporal labels** (`archaic`, `obsolete`, `dated`) — exclude old-fashioned words
- **Register labels** (`rare`, `literary`, `technical`) — exclude specialized vocabulary
- **Concreteness** — prefer concrete nouns for visual games

A word can be high-frequency but still inappropriate (e.g., archaic words in historical texts), or low-frequency but perfectly suitable (e.g., concrete nouns like "giraffe").

### POS Filters

```yaml
pos:
  include: [NOU, VRB]        # Must have one of these
  exclude: [ITJ]             # Must not have any of these
```

POS tags use 3-letter codes: `NOU`, `VRB`, `ADJ`, `ADV`, `PRN`, `ADP`, `CNJ`, `ITJ`, `DET`, `PRT`, `NAM` (proper noun), `PHR`, `PRV`, `PPP`, `IDM`, `AFX`, `NUM`, `SYM`, `MLT`, `CTN`. See `schema/pos.yaml` for full details.

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

Proper nouns use the `NAM` POS code, distinct from common nouns (`NOU`). To filter:

```yaml
# Exclude proper nouns
pos:
  exclude: [NAM]

# Include only proper nouns
pos:
  include: [NAM]
```

For words that have both common and proper usages (e.g., "bill" as a common noun and "Bill" as a name), the sense-level data in `en-senses.jsonl` distinguishes these.

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
  include: [NOU]

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
- `id` - The word
- `pos` - Part of speech tags (3-letter codes, aggregated from senses)
- `nsyll` - Syllable count
- `frequency_tier` - Frequency tier
- `concreteness` - Concreteness rating
- `sources` - Contributing sources

Use `--jq` to project specific fields:

```bash
# Extract word + syllables only
owlex wordle.yaml --enriched data.jsonl --jq '{id, nsyll}'

# Morphology lookup
owlex wordle.yaml --enriched data.jsonl --jq '{id, pos, lemmas}'
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
    word = entry['id']
    return (
        len(word) == 5 and
        word.isalpha() and
        word.islower() and
        entry.get('frequency_tier', 'Z') <= 'I'
    )

wordle_words = [e['id'] for e in load_lexemes() if is_wordle_word(e)]
```

## jq Filtering

For quick ad-hoc filtering:

```bash
# 5-letter words
jq -r 'select(.id | length == 5) | .id' \
    data/intermediate/en-lexemes-enriched.jsonl

# Common nouns
jq -r 'select(
    (.pos // [] | contains(["NOU"])) and
    (.frequency_tier // "Z") <= "F"
) | .id' data/intermediate/en-lexemes-enriched.jsonl

# Words with concreteness data
jq -r 'select(.concreteness != null) | "\(.id)\t\(.concreteness)"' \
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
| `nsyll` | ~2% (~30K words) |

When filtering by optional fields, consider using `require_*` options to exclude words without data, or accept that some words may pass filters by default.

## Two-File Pipeline

For advanced filtering that requires sense-level data (POS per sense, per-sense labels), use the two-file pipeline with `filters.py`:

```bash
python -m openword.filters INPUT OUTPUT \
    --senses data/intermediate/en-senses.jsonl \
    --pos NOU --no-profanity
```

This uses the senses file which contains per-sense data, correctly handling words like "left" that have multiple parts of speech.
