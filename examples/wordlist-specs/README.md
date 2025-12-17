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

### Wordle Word Lists

Three variants for Wordle-style games:

**`wordle-accepted.yaml`** — Broad dictionary for validating guesses
- All valid 5-letter words (includes slang, swears)
- Only excludes obsolete/archaic terms
- **Expected**: ~5,000+ words

**`wordle-solutions.yaml`** — Curated list for puzzle solutions
- Family-friendly (no vulgar, offensive, slang)
- US English or international (excludes UK-only terms)
- Common vocabulary only (top frequency tiers)
- **Expected**: ~2,000-3,000 words

**`wordle.yaml`** — Balanced middle-ground
- Excludes vulgar/offensive but allows slang
- Broader than solutions, narrower than accepted
- **Expected**: ~3,000 words

---

### Base Datasets

**`word-only.yaml`** — All words (no phrases)
- Excludes proper nouns (NAM), phrases (PHR), idioms (IDM)
- Includes multi-word entries like "petri dish" if they're regular nouns
- Base dataset for game word lists

**`full.yaml`** — Complete Wiktionary
- All entries, no filtering
- Includes phrases, proper nouns, everything
- Used for benchmarking and full-text search

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
- Single words only (a-z characters)
- Allows archaic/obsolete (valid in Scrabble dictionaries)
- TODO: Add lexnames filter to exclude pure proper nouns

**Expected**: ~700,000+ words (before proper noun filtering)

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

exclude:
  register: [RVLG, ROFF]      # vulgar, offensive
  temporal: [TARC, TOBS]      # archaic, obsolete
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
  max_tier: L           # Least common tier to include
  # Tiers: A (top 20) → L (top 10k) → Z (unknown)
  # See docs/FILTERING.md for full tier table
```

**Note:** Frequency is just one signal. Consider also using:
- `temporal: exclude: [archaic, obsolete]` for modern vocabulary
- `labels: register: exclude: [rare, literary]` for common words
- `concreteness: values: [concrete]` for tangible nouns

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

Labels use 4-letter codes from `schema/core/tag_sets.yaml`:

```yaml
# Exclude vulgar/offensive content
exclude:
  register: [RVLG, ROFF]     # vulgar, offensive

# Or include specific registers
include:
  register: [RSLG]           # slang only
```

**Register codes (REGS):**
- `RINF` informal, `RSLG` slang, `RVLG` vulgar
- `ROFF` offensive, `RFRM` formal, `RLIT` literary
- `RHUM` humorous, `RCHD` childish, `RNST` nonstandard

**Temporal codes (TEMP):**
- `TARC` archaic, `TOBS` obsolete, `TDAT` dated
- `THIS` historical, `TRAR` rare

**Region codes (REGN):**
- `ENUS` US, `ENGB` UK, `ENCA` Canada
- `ENAU` Australia, `ENNZ` New Zealand
- `ENIE` Ireland, `ENZA` South Africa, `ENIN` India

### Temporal Filters
```yaml
exclude:
  temporal: [TARC, TOBS, TDAT]  # archaic, obsolete, dated
```

### Source Filters (for licensing)
```yaml
sources:
  include: [wordnet]     # Only words from these sources
  enrichment: [frequency]  # Allow data from these for filtering
```

### Proper Noun Filters

> **Not yet implemented** — The `has_common_usage` field is not populated in the data pipeline. See docs/FILTERING.md for alternatives using WordNet `lexnames`.

```yaml
# proper_noun:
#   require_common_usage: true  # "bill" OK, "Aaron" excluded
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
