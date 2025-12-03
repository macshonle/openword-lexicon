# Example Word List Specifications

This directory contains example YAML specifications for common word list filtering scenarios.

## Usage

Generate a word list from any specification:

```bash
# Basic usage - outputs to stdout
owlex examples/wordlist-specs/wordle.yaml

# Save to file
owlex examples/wordlist-specs/wordle.yaml --output wordle-words.txt

# With enriched sidecar JSONL (includes POS, syllables, etc.)
owlex wordle.yaml --output words.txt --enriched enriched.jsonl

# With jq projection
owlex wordle.yaml --enriched syllables.jsonl --jq '{word, syllables, pos}'

# Verbose mode
owlex examples/wordlist-specs/wordle.yaml --verbose
```

## Available Examples

### `wordle.yaml`
5-letter common words for Wordle-style games.
- Exactly 5 letters, lowercase alphabetic
- Single words only
- Top ~30k frequency (tiers A-I)

**Expected**: ~3,000 words

---

### `kids-nouns.yaml`
Concrete nouns for children's games.
- 3-10 characters
- Concrete nouns (requires concreteness data)
- Family-friendly (excludes vulgar/offensive)
- Modern language (excludes archaic)

**Expected**: ~500-1,000 words with concreteness data

---

### `children-2syllable.yaml`
Two-syllable concrete nouns for children's word games.
- Exactly 2 syllables (requires syllable data)
- Concrete nouns
- Family-friendly, modern

**Expected**: ~200-500 words with syllable data

---

### `poetry-5syllable.yaml`
Five-syllable words for poetry (haiku, meter work).
- Exactly 5 syllables (requires syllable data)
- Modern, non-offensive

**Expected**: ~50-200 words with syllable data

---

### `simple-words.yaml`
Simple words for beginning readers and ESL learners.
- 1-3 syllables
- High frequency
- 3-10 characters
- No jargon or technical terms

**Expected**: ~1,000-3,000 words with syllable data

---

### `scrabble.yaml`
Words suitable for Scrabble.
- Single words only
- Requires common usage (excludes pure proper nouns)
- Allows archaic/obsolete (valid in Scrabble)

**Expected**: ~100,000+ words

---

### `profanity-blocklist.yaml`
Words for content filtering blocklists.
- Words labeled vulgar, offensive, or derogatory

**Expected**: ~10,000 words with labels

---

### `wordnet-only.yaml`
License-compliant example using only WordNet (CC-BY-4.0).
- Words that exist in WordNet source
- 3-10 characters, common frequency

**Expected**: ~50,000+ words from WordNet

---

## Simplified Spec Format

Specs use a filters-only YAML format - the spec body IS the filters:

```yaml
# Comment: what this spec does

character:
  exact_length: 5
  pattern: "^[a-z]+$"

phrase:
  max_words: 1

frequency:
  min_tier: A
  max_tier: I

labels:
  register:
    exclude: [vulgar, offensive, derogatory]

temporal:
  exclude: [archaic, obsolete]
```

No `version`, `distribution`, or `output` sections needed. Output format is controlled via CLI flags.

---

## Filter Reference

### Character Filters
```yaml
character:
  exact_length: 5       # Exactly N characters
  min_length: 3         # At least N characters
  max_length: 10        # At most N characters
  pattern: "^[a-z]+$"   # Regex pattern to match
```

### Phrase Filters
```yaml
phrase:
  max_words: 1          # Single words only
  min_words: 2          # Multi-word phrases only
```

### Frequency Filters
```yaml
frequency:
  min_tier: A           # Most common tier to include
  max_tier: I           # Least common tier to include
  # Tiers: A (most common) → J → Z (rarest/unknown)
```

### Syllable Filters
```yaml
syllables:
  exact: 2              # Exactly N syllables
  min: 1                # At least N syllables
  max: 3                # At most N syllables
  require_syllables: true  # Only words with syllable data
```

### POS Filters
```yaml
pos:
  include: [noun, verb]  # Must have one of these POS
  exclude: [interjection]
```

### Concreteness Filters
```yaml
concreteness:
  values: [concrete]     # concrete, mixed, or abstract
```

### Label Filters
```yaml
labels:
  register:
    include: [slang]     # Must have these labels
    exclude: [vulgar, offensive, derogatory]
  domain:
    exclude: [medical, legal, technical]
  region:
    include: [en-US]     # Only US regional words
```

### Temporal Filters
```yaml
temporal:
  exclude: [archaic, obsolete, dated]
```

### Source Filters (for licensing)
```yaml
sources:
  include: [wordnet]     # Only words from these sources
  enrichment: [frequency]  # Allow data from these for filtering
```

### Proper Noun Filters
```yaml
proper_noun:
  require_common_usage: true  # "bill" OK, "Aaron" excluded
```

---

## Limitations

Some filters require data from the senses file:
- **POS filtering**: POS tags are in senses, not lexemes
- **Label filtering**: Labels are in senses file
- **Concreteness**: Only ~3% of words have concreteness data

For full sense-level filtering, use the two-file pipeline in `filters.py`:
```bash
python -m openword.filters INPUT OUTPUT --senses SENSES --pos noun --no-profanity
```

---

## Creating Your Own

### Method 1: Copy and Modify
```bash
cp examples/wordlist-specs/wordle.yaml my-spec.yaml
# Edit my-spec.yaml
owlex my-spec.yaml --output my-words.txt
```

### Method 2: Web Interface
```bash
make spec-editor-web
```

Use the visual form to configure filters and download the specification.

---

## Tips

### Combining Specifications
```bash
owlex wordle.yaml --output wordle.txt
owlex hard-words.yaml --output hard.txt
cat wordle.txt hard.txt | sort -u > combined.txt
```

### Excluding Profanity
```bash
owlex my-spec.yaml --output words.txt
owlex profanity-blocklist.yaml --output blocked.txt
grep -vFxf blocked.txt words.txt > clean-words.txt
```

### Enriched Output with jq Projection
```bash
# Extract word + syllables only
owlex wordle.yaml --enriched data.jsonl --jq '{word, syllables}'

# Morphology lookup
owlex wordle.yaml --enriched data.jsonl --jq '{word, pos, lemmas}'
```
