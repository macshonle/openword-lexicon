# Validation Framework

The OpenWord Lexicon includes validation tools to help developers make informed decisions about word filtering for their specific use cases. These are **NOT part of the main build pipeline** - they're optional analysis tools.

## Overview

Validation tools help answer questions like:
- *"Does my lexicon properly label offensive words?"*
- *"How do I filter childish terms for a family game?"*
- *"What's the difference between UNION and INTERSECTION filtering?"*
- *"Are there gaps in my profanity labeling?"*

## Available Validations

### 1. ENABLE Word List Coverage

**Purpose**: Baseline check that we haven't regressed on classic word game vocabulary.

**Usage**:
```bash
make validate-enable
```

**What it does**:
- Fetches ENABLE word list (172k words, public domain)
- Compares against our lexicon
- Reports coverage statistics

**Note**: ENABLE is **not** included in the build - it's purely for validation.

---

### 2. Profanity / Offensive Term Labeling

⚠️ **WARNING: Contains analysis of explicit/offensive content** ⚠️

**Purpose**: Validate that vulgar/offensive/derogatory labels are comprehensive by comparing against external profanity lists.

**Usage**:
```bash
make validate-profanity
```

**What it does**:
- Fetches profanity lists:
  - `censor-text/profanity-list` (clean, maintained)
  - `dsojevic/profanity-list` (severity ratings + metadata JSON)
- Compares against words labeled `vulgar`, `offensive`, or `derogatory` in our lexicon
- Identifies gaps (words in external lists but NOT labeled in ours)
- Identifies our-only words (we label but external lists don't)
- Provides severity breakdown

**Output**:
```
SUMMARY
────────────────────────────────────────────────────────────────────────────────
  Words labeled vulgar/offensive/derogatory in our lexicon: 1,234
  Words in external profanity lists:                        2,567
  Coverage (words in lexicon with labels):                  85.2%

GAPS (in external lists but NOT labeled in our lexicon)
────────────────────────────────────────────────────────────────────────────────
  Total gaps: 245

  By severity:
    high               123
    medium              89
    low                 33

RECOMMENDATIONS
────────────────────────────────────────────────────────────────────────────────
  1. Review gaps to determine if Wiktionary should add labels
  2. Focus on high-severity terms first
  3. Consider that some terms may be context-dependent
  4. External lists may include regional slang not in formal dictionaries
```

**Files downloaded** (stored in `data/raw/validation/profanity/`):
- `censor-text-profanity-list.txt`
- `dsojevic-profanity-list.json`

---

### 3. Childish Terms Analysis

**Purpose**: Analyze words labeled as `childish` (baby talk, infantile terms) for age-appropriate filtering.

**Usage**:
```bash
make validate-childish
```

**What it does**:
- Finds all words labeled `childish` in Wiktionary
- Shows breakdown by part of speech
- Identifies terms that are both childish AND vulgar (bathroom humor)
- Provides filtering examples for different use cases

**Example output**:
```
SUMMARY
────────────────────────────────────────────────────────────────────────────────
  Words labeled 'childish':                 553
  Words with multiple register labels:      127
  Childish + vulgar:                         42
  Childish + informal/colloquial:           234

BREAKDOWN BY PART OF SPEECH
────────────────────────────────────────────────────────────────────────────────
  noun             312
  verb              98
  adjective         67
  interjection      54
  adverb            22

SAMPLE CHILDISH TERMS
────────────────────────────────────────────────────────────────────────────────
  NOUN:
    tushie               labels=['childish'] freq=uncommon
    poo-poo              labels=['childish', 'vulgar'] freq=rare
    ...

USE CASES FOR DEVELOPERS
────────────────────────────────────────────────────────────────────────────────

1. FAMILY-FRIENDLY WORD GAMES
   Filter: Exclude 'childish' + 'vulgar' labels
   Example: Avoid 'poo-poo', 'wee-wee', 'tushie'

2. EDUCATIONAL APPS (Age-Appropriate)
   Filter: Include OR exclude 'childish' based on target age
   - Ages 3-5: INCLUDE childish terms (familiar vocabulary)
   - Ages 8+: EXCLUDE childish terms (mature vocabulary)

3. PROFESSIONAL/FORMAL CONTEXTS
   Filter: Exclude 'childish', 'informal', 'colloquial'
   Example: Business writing tools, academic spell-checkers
```

---

### 4. Run All Validations

**Usage**:
```bash
make validate-all
```

Runs all three validations in sequence.

---

## Understanding Label-Based Filtering

### The Union vs Intersection Problem

Consider the word **"tush"**:

**Wiktionary senses**:
1. (US, childish, informal) buttocks
2. (dialectal) tusk
3. (British, informal) nonsense

**The question**: Should "tush" be in a family-friendly word game?

#### UNION Approach (Permissive)
*"Include if ANY sense is appropriate"*

✅ **INCLUDE** "tush"
- Rationale: Has valid dialectal (tusk) and British (nonsense) senses
- Risk: US players might be confused/uncomfortable

#### INTERSECTION Approach (Restrictive)
*"Exclude if ANY sense is problematic"*

❌ **EXCLUDE** "tush"
- Rationale: Has childish/informal sense for US audiences
- Benefit: Avoids potential awkwardness even if word has other meanings

### Recommendation

For **global games with US market**: Use INTERSECTION approach
- Filter: Exclude words with ANY problematic labels
- Query: `NOT (childish OR vulgar OR offensive)`

For **educational apps**: Use targeted filtering
- Ages 3-5: `childish = include, vulgar = exclude`
- Ages 8+: `childish = exclude, vulgar = exclude`
- Professional: `formal only, exclude informal/colloquial/childish`

---

## Example Filter Queries

### Using `jq` (command line)

```bash
# Exclude childish terms (ages 8+)
jq 'select(.labels.register | index("childish") | not)' \
   data/intermediate/en/entries_tiered.jsonl

# Include ONLY childish terms (ages 3-5)
jq 'select(.labels.register | index("childish"))' \
   data/intermediate/en/entries_tiered.jsonl

# Exclude childish + vulgar (family-friendly)
jq 'select(
     (.labels.register | index("childish") | not) and
     (.labels.register | index("vulgar") | not)
   )' data/intermediate/en/entries_tiered.jsonl

# INTERSECTION approach: exclude ANY problematic label
jq 'select(
     (.labels.register | index("childish") | not) and
     (.labels.register | index("vulgar") | not) and
     (.labels.register | index("offensive") | not) and
     (.labels.register | index("derogatory") | not)
   )' data/intermediate/en/entries_tiered.jsonl

# Professional vocabulary (formal only)
jq 'select(
     .labels.register | index("formal")
   )' data/intermediate/en/entries_tiered.jsonl

# Exclude ALL informal registers
jq 'select(
     (.labels.register | index("childish") | not) and
     (.labels.register | index("informal") | not) and
     (.labels.register | index("colloquial") | not) and
     (.labels.register | index("slang") | not)
   )' data/intermediate/en/entries_tiered.jsonl
```

### Using Python

```python
import orjson

# Load lexicon
with open('data/intermediate/en/entries_tiered.jsonl', 'rb') as f:
    entries = [orjson.loads(line) for line in f]

# Filter: Family-friendly (no childish, no vulgar)
family_friendly = [
    e for e in entries
    if not any(label in e.get('labels', {}).get('register', [])
               for label in ['childish', 'vulgar', 'offensive', 'derogatory'])
]

# Filter: Ages 3-5 (include childish, exclude vulgar)
ages_3_5 = [
    e for e in entries
    if 'vulgar' not in e.get('labels', {}).get('register', [])
]

# Filter: Ages 8+ (exclude childish AND vulgar)
ages_8_plus = [
    e for e in entries
    if not any(label in e.get('labels', {}).get('register', [])
               for label in ['childish', 'vulgar', 'offensive'])
]

# Filter: Professional (formal only, no slang/informal)
professional = [
    e for e in entries
    if 'formal' in e.get('labels', {}).get('register', [])
    and not any(label in e.get('labels', {}).get('register', [])
                for label in ['informal', 'colloquial', 'slang', 'childish'])
]
```

---

## Register Labels Reference

Our lexicon includes these register labels from Wiktionary:

| Label | Meaning | Example Words | Filter Strategy |
|-------|---------|---------------|-----------------|
| `vulgar` | Crude, explicit, or taboo | (explicit examples omitted) | Exclude for family/professional |
| `offensive` | Potentially hurtful or insulting | (slurs, insults) | Always exclude |
| `derogatory` | Disparaging or belittling | (pejorative terms) | Always exclude |
| `childish` | Baby talk, infantile terms | tushie, poo-poo, wee-wee | Age-dependent |
| `slang` | Informal, non-standard | ain't, gonna, wanna | Context-dependent |
| `colloquial` | Conversational, informal | kinda, sorta | Context-dependent |
| `informal` | Casual, not formal | kid (child), cop (police) | Professional: exclude |
| `formal` | Appropriate for formal writing | utilize, commence | Professional: include |
| `euphemistic` | Indirect/polite substitution | passed away, restroom | Usually acceptable |
| `humorous` | Jocular or playful | doohickey, thingamajig | Context-dependent |
| `literary` | Used in literature/poetry | whence, ere, betwixt | Educational: include |

---

## Developer Decision Matrix

| Use Case | Target Audience | Recommended Filter | Labels to Exclude |
|----------|----------------|-------------------|-------------------|
| **Family Word Game** | All ages | Intersection (strict) | childish, vulgar, offensive, derogatory |
| **Children's Game (3-5)** | Preschool | Permissive | vulgar, offensive, derogatory |
| **Children's Game (8+)** | Elementary | Moderate | childish, vulgar, offensive, derogatory |
| **Educational App (Teens)** | 13-17 | Educational | vulgar, offensive, derogatory |
| **Crossword Puzzle** | Adult | Permissive | offensive, derogatory |
| **Professional Spellcheck** | Business | Formal only | informal, colloquial, slang, childish, vulgar |
| **Academic Writing** | University | Formal + literary | informal, colloquial, slang, childish |
| **Casual Chat Bot** | General | Moderate | vulgar, offensive, derogatory |

---

## Validation Data Storage

All validation data is stored separately from the main lexicon:

```
data/
├── raw/
│   └── validation/           ← Validation data (NOT in main build)
│       ├── profanity/
│       │   ├── censor-text-profanity-list.txt
│       │   └── dsojevic-profanity-list.json
│       └── (future validation sets)
├── intermediate/
│   └── en/
│       └── entries_tiered.jsonl  ← Main lexicon (use this for filtering)
```

**Important**: Validation data is `.gitignore`d due to explicit content. Run `make validate-profanity` to download when needed.

---

## Adding Custom Validation

To add your own validation:

1. **Create fetch script** (if external data needed):
   ```bash
   scripts/fetch/fetch_my_validation.sh
   ```

2. **Create validation tool**:
   ```python
   tools/validate_my_feature.py
   ```

3. **Add Makefile target**:
   ```makefile
   validate-my-feature: deps
       @bash scripts/fetch/fetch_my_validation.sh
       @$(UV) run python tools/validate_my_feature.py
   ```

4. **Document** in this file!

---

## See Also

- [SCHEMA.md](SCHEMA.md) - Full schema documentation including labels
- [DATASETS.md](DATASETS.md) - Information about data sources
- [FILTERING.md](../examples/README.md) - Advanced filtering examples
- [MAKEFILE_REFERENCE.md](MAKEFILE_REFERENCE.md) - All make commands
