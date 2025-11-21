# Openword Lexicon — Usage Guide

This guide covers how to use the Openword Lexicon in your projects.

## Table of Contents

- [Installation](#installation)
- [Python API](#python-api)
- [Common Use Cases](#common-use-cases)
- [Performance Notes](#performance-notes)

---

## Installation

### Using Pre-built Releases

Download from [GitHub Releases](https://github.com/macshonle/openword-lexicon/releases):

```bash
# Core distribution (CC BY 4.0)
wget https://github.com/macshonle/openword-lexicon/releases/latest/download/openword-lexicon-core-0.1.0.tar.gz
tar xzf openword-lexicon-core-0.1.0.tar.gz

# Plus distribution (CC BY-SA 4.0)
wget https://github.com/macshonle/openword-lexicon/releases/latest/download/openword-lexicon-plus-0.1.0.tar.gz
tar xzf openword-lexicon-plus-0.1.0.tar.gz
```

### Building from Source

See [README.md](../README.md#building-from-source-uv) for build instructions.

---

## Python API

### Basic Word Lookup

```python
import marisa_trie
import json

# Load trie
trie = marisa_trie.Trie()
trie.load('core.trie')

# Check if word exists
if 'castle' in trie:
    print("Word exists!")

# Get all words starting with prefix
prefix_words = trie.keys('cas')
print(list(prefix_words))
# ['casaba', 'casabas', 'cascade', 'cascaded', 'cascades', 'cascading', ...]
```

### Access Full Metadata

```python
import marisa_trie
import json

# Load trie and metadata
trie = marisa_trie.Trie()
trie.load('core.trie')

with open('core.meta.json', 'r') as f:
    metadata = json.load(f)

# Get word index from trie
word = 'castle'
if word in trie:
    # Trie returns list of IDs (usually just one)
    word_id = trie[word][0]

    # Get full entry from metadata
    entry = metadata[word_id]
    print(json.dumps(entry, indent=2))

# Output:
# {
#   "word": "castle",
#   "pos": ["noun", "verb"],
#   "labels": {},
#   "is_phrase": false,
#   "lemma": null,
#   "concreteness": "mixed",
#   "frequency_tier": "top10k",
#   "sources": ["enable", "eowl", "wikt"]
# }
```

### Filter by Attributes

```python
import marisa_trie
import json

# Load data
trie = marisa_trie.Trie()
trie.load('plus.trie')

with open('plus.meta.json', 'r') as f:
    metadata = json.load(f)

# Find all concrete nouns in top 10k frequency (tiers A-Q)
concrete_nouns = []
for entry in metadata:
    if (
        'noun' in entry.get('pos', []) and
        entry.get('concreteness') == 'concrete' and
        entry.get('frequency_tier', 'Z') <= 'Q'  # A-Q covers ranks 1-13,335
    ):
        concrete_nouns.append(entry['word'])

print(f"Found {len(concrete_nouns)} concrete nouns in top ~13k")
print("Examples:", concrete_nouns[:10])
```

### Family-Friendly Filter

```python
import marisa_trie
import json

# Load data
trie = marisa_trie.Trie()
trie.load('plus.trie')

with open('plus.meta.json', 'r') as f:
    metadata = json.load(f)

# Filter out vulgar/offensive words
EXCLUDE_LABELS = {'vulgar', 'offensive', 'derogatory'}

family_friendly_words = []
for entry in metadata:
    register = set(entry.get('labels', {}).get('register', []))

    # Exclude if any problematic labels
    if not (register & EXCLUDE_LABELS):
        family_friendly_words.append(entry['word'])

print(f"Family-friendly words: {len(family_friendly_words)}")
```

### Using Concreteness Scores

The lexicon includes concreteness ratings from Brysbaert et al. (2014), providing both categorical classifications and precise numeric scores for filtering and ranking words by how concrete or abstract they are.

#### Basic Categorical Filtering

```python
import marisa_trie
import json

# Load data
trie = marisa_trie.Trie()
trie.load('plus.trie')

with open('plus.meta.json', 'r') as f:
    metadata = json.load(f)

# Get only concrete nouns (tangible objects)
concrete_nouns = [
    entry['word'] for entry in metadata
    if entry.get('concreteness') == 'concrete' and 'noun' in entry.get('pos', [])
]

print(f"Concrete nouns: {len(concrete_nouns)}")
print("Examples:", concrete_nouns[:10])
# Examples: ['castle', 'apple', 'hammer', 'door', 'chair', ...]

# Get abstract nouns (ideas, concepts)
abstract_nouns = [
    entry['word'] for entry in metadata
    if entry.get('concreteness') == 'abstract' and 'noun' in entry.get('pos', [])
]

print(f"Abstract nouns: {len(abstract_nouns)}")
print("Examples:", abstract_nouns[:10])
# Examples: ['freedom', 'justice', 'theory', 'wisdom', 'love', ...]
```

#### Fine-Grained Filtering with Numeric Ratings

```python
# Get highly concrete words (rating >= 4.0) for children's apps
highly_concrete = [
    entry['word'] for entry in metadata
    if entry.get('concreteness_rating', 0) >= 4.0
]

print(f"Highly concrete words: {len(highly_concrete)}")
# Use custom thresholds beyond the predefined categories

# Get words in the "somewhat concrete" range (3.0-4.0)
somewhat_concrete = [
    entry['word'] for entry in metadata
    if 3.0 <= entry.get('concreteness_rating', 0) < 4.0
]

# Exclude highly abstract words for language learning
not_too_abstract = [
    entry['word'] for entry in metadata
    if entry.get('concreteness_rating', 0) >= 2.5
]
```

#### Ranking and Scoring by Concreteness

```python
# Sort words by concreteness for progressive difficulty
words_by_concreteness = sorted(
    [e for e in metadata if 'concreteness_rating' in e],
    key=lambda e: e['concreteness_rating'],
    reverse=True  # Most concrete first
)

print("Most concrete words:")
for entry in words_by_concreteness[:5]:
    print(f"  {entry['word']}: {entry['concreteness_rating']}")
# Output:
#   castle: 4.92
#   apple: 4.83
#   hammer: 4.79
#   ...

print("\nMost abstract words:")
for entry in words_by_concreteness[-5:]:
    print(f"  {entry['word']}: {entry['concreteness_rating']}")
# Output:
#   freedom: 1.46
#   justice: 1.52
#   theory: 1.93
#   ...
```

#### Confidence-Based Filtering (Using Standard Deviation)

```python
# Get words with high-confidence ratings (low SD)
high_confidence_concrete = [
    entry['word'] for entry in metadata
    if (
        entry.get('concreteness_rating', 0) >= 4.0 and
        entry.get('concreteness_sd', 2.0) < 0.8  # Low variability = high agreement
    )
]

print(f"High-confidence concrete words: {len(high_confidence_concrete)}")

# Exclude ambiguous words (high SD) for educational content
unambiguous_words = [
    entry for entry in metadata
    if entry.get('concreteness_sd', 2.0) < 1.0
]

print(f"Unambiguous words: {len(unambiguous_words)}")
```

#### Advanced: Confidence-Weighted Scoring

```python
# Combine rating with confidence for weighted selection
def concreteness_score(entry):
    """Calculate confidence-weighted concreteness score."""
    rating = entry.get('concreteness_rating', 0)
    sd = entry.get('concreteness_sd', 2.0)

    # Lower SD = higher confidence
    confidence = 1.0 / (1.0 + sd)

    # Weight rating by confidence
    return rating * confidence

# Sort words by weighted score
scored_words = sorted(
    [e for e in metadata if 'concreteness_rating' in e],
    key=concreteness_score,
    reverse=True
)

print("Top 10 words by confidence-weighted concreteness:")
for entry in scored_words[:10]:
    score = concreteness_score(entry)
    print(f"  {entry['word']}: rating={entry['concreteness_rating']}, "
          f"sd={entry['concreteness_sd']}, weighted_score={score:.2f}")
```

#### Children's Educational Content

```python
# Build vocabulary list for kids: concrete, common, high-confidence
kids_vocabulary = [
    entry['word'] for entry in metadata
    if (
        entry.get('concreteness_rating', 0) >= 4.0 and  # Very concrete
        entry.get('concreteness_sd', 2.0) < 0.8 and     # High confidence
        entry.get('frequency_tier', 'Z') <= 'Q' and     # Common words (ranks 1-13,335)
        'noun' in entry.get('pos', []) and
        len(entry['word']) <= 8  # Not too long
    )
]

print(f"Kids vocabulary: {len(kids_vocabulary)} words")
print("Examples:", kids_vocabulary[:20])
```

#### Language Learning: Progressive Difficulty

```python
# Create tiered vocabulary lists by concreteness
def create_learning_tiers(metadata):
    """Create progressive difficulty tiers starting with concrete words."""
    tiers = {
        'beginner': [],      # Highly concrete (4.0+)
        'intermediate': [],  # Somewhat concrete (3.0-4.0)
        'advanced': []       # Abstract and mixed (< 3.0)
    }

    for entry in metadata:
        rating = entry.get('concreteness_rating')
        if rating is None:
            continue

        if rating >= 4.0:
            tiers['beginner'].append(entry['word'])
        elif rating >= 3.0:
            tiers['intermediate'].append(entry['word'])
        else:
            tiers['advanced'].append(entry['word'])

    return tiers

learning_tiers = create_learning_tiers(metadata)
print("Beginner words:", len(learning_tiers['beginner']))
print("Intermediate words:", len(learning_tiers['intermediate']))
print("Advanced words:", len(learning_tiers['advanced']))
```

### Morphology and Word Families

The lexicon includes morphology data for ~240,000 words extracted from Wiktionary etymology templates, enabling word family exploration and affix-based queries.

#### Word Family Exploration

```python
import json

# Load metadata and affix index
with open('plus.meta.json', 'r') as f:
    metadata = json.load(f)

with open('wikt_affix_index.json', 'r') as f:
    affix_index = json.load(f)

# Find all words derived from "happy"
base = "happy"
family = [
    entry['word'] for entry in metadata
    if entry.get('morphology', {}).get('base') == base
]

print(f"Words derived from '{base}':")
for word in sorted(family):
    morph = next(e['morphology'] for e in metadata if e['word'] == word)
    print(f"  {word}: {morph['type']} - {' + '.join(morph['components'])}")

# Output:
#   happily: suffixed - happy + -ly
#   happiness: suffixed - happy + -ness
#   unhappily: affixed - un- + happy + -ly
#   unhappiness: affixed - un- + happy + -ness
#   unhappy: prefixed - un- + happy
```

#### Affix-Based Filtering

```python
# Find all words with suffix "-ness"
suffix = "-ness"
ness_words = affix_index['suffixes'][suffix]['sample_words']
print(f"Sample words with suffix '{suffix}':")
print(ness_words[:10])
# ['darkness', 'happiness', 'kindness', 'sadness', 'weakness', ...]

# Get count and POS distribution
suffix_info = affix_index['suffixes'][suffix]
print(f"\nTotal words: {suffix_info['word_count']}")
print(f"POS distribution: {suffix_info['pos_distribution']}")
# POS distribution: {'noun': 9727}

# Find all words with prefix "un-"
prefix = "un-"
un_words = affix_index['prefixes'][prefix]['sample_words']
print(f"\nSample words with prefix '{prefix}':")
print(un_words[:10])
# ['unable', 'unclear', 'uncomfortable', 'unhappy', 'unknown', ...]

prefix_info = affix_index['prefixes'][prefix]
print(f"Total words: {prefix_info['word_count']}")
print(f"POS distribution: {prefix_info['pos_distribution']}")
# POS distribution: {'adjective': 5234, 'verb': 3891, 'noun': 1543}
```

#### Formation Type Filtering

```python
# Find all compound words
compounds = [
    entry['word'] for entry in metadata
    if entry.get('morphology', {}).get('type') == 'compound'
]

print(f"Compound words: {len(compounds)}")
print("Examples:", compounds[:10])
# Examples: ['bartender', 'firefighter', 'notebook', 'sunflower', ...]

# Find words with both prefix and suffix (affixed)
affixed = [
    entry['word'] for entry in metadata
    if entry.get('morphology', {}).get('type') == 'affixed'
]

print(f"\nAffixed words (prefix + suffix): {len(affixed)}")
print("Examples:", affixed[:10])
# Examples: ['unbreakable', 'uncomfortable', 'unfortunately', ...]

# Analyze their structure
for word in affixed[:3]:
    morph = next(e['morphology'] for e in metadata if e['word'] == word)
    print(f"  {word}: {' + '.join(morph['components'])}")
# unbreakable: un- + break + -able
# uncomfortable: un- + comfort + -able
# unfortunately: un- + fortun + -ate + -ly
```

#### Most Productive Affixes

```python
# Find most productive prefixes
top_prefixes = sorted(
    affix_index['prefixes'].items(),
    key=lambda x: x[1]['word_count'],
    reverse=True
)[:10]

print("Most productive prefixes:")
for prefix, info in top_prefixes:
    print(f"  {prefix}: {info['word_count']} words")
# un-: 11,218 words
# non-: 10,003 words
# anti-: 3,293 words
# ...

# Find most productive suffixes
top_suffixes = sorted(
    affix_index['suffixes'].items(),
    key=lambda x: x[1]['word_count'],
    reverse=True
)[:10]

print("\nMost productive suffixes:")
for suffix, info in top_suffixes:
    print(f"  {suffix}: {info['word_count']} words")
# -ly: 12,686 words
# -ness: 9,727 words
# -er: 6,516 words
# ...
```

#### Educational Use Case: Vocabulary Building

```python
# Build progressive vocabulary list by morphological complexity
def create_morphology_tiers(metadata):
    """Create learning tiers by morphological complexity."""
    tiers = {
        'simple': [],        # Base words, no affixes
        'derived': [],       # Single prefix or suffix
        'complex': []        # Multiple affixes or compounds
    }

    for entry in metadata:
        morph = entry.get('morphology')
        if not morph:
            tiers['simple'].append(entry['word'])
            continue

        morph_type = morph.get('type')
        if morph_type in ['suffixed', 'prefixed']:
            tiers['derived'].append(entry['word'])
        elif morph_type in ['affixed', 'compound', 'circumfixed']:
            tiers['complex'].append(entry['word'])
        else:
            tiers['simple'].append(entry['word'])

    return tiers

morph_tiers = create_morphology_tiers(metadata)
print("Simple words:", len(morph_tiers['simple']))
print("Derived words:", len(morph_tiers['derived']))
print("Complex words:", len(morph_tiers['complex']))
```

#### Linguistic Research: Affix Combinations

```python
# Find common prefix-suffix combinations
from collections import Counter

combinations = Counter()
for entry in metadata:
    morph = entry.get('morphology', {})
    if morph.get('type') == 'affixed':
        prefixes = tuple(morph.get('prefixes', []))
        suffixes = tuple(morph.get('suffixes', []))
        if prefixes and suffixes:
            combinations[(prefixes, suffixes)] += 1

print("Most common prefix-suffix combinations:")
for (prefixes, suffixes), count in combinations.most_common(10):
    prefix_str = ' + '.join(prefixes)
    suffix_str = ' + '.join(suffixes)
    print(f"  {prefix_str} + base + {suffix_str}: {count} words")
# un- + base + -able: 234 words
# un- + base + -ly: 189 words
# re- + base + -ed: 156 words
# ...
```

#### Compound Word Analysis

```python
# Find compounds with interfixes (linking morphemes)
compounds_with_interfixes = [
    entry for entry in metadata
    if entry.get('morphology', {}).get('interfixes')
]

print(f"Compounds with interfixes: {len(compounds_with_interfixes)}")
for entry in compounds_with_interfixes[:5]:
    morph = entry['morphology']
    print(f"  {entry['word']}: {' + '.join(morph['components'])}")
# beeswax: bee + -s- + wax
# craftsman: craft + -s- + man
# kinsman: kin + -s- + man
# ...

# Analyze interfix inventory
interfixes = affix_index['interfixes']
print(f"\nTotal interfixes: {len(interfixes)}")
for interfix, info in sorted(interfixes.items(), key=lambda x: x[1]['word_count'], reverse=True)[:5]:
    print(f"  {interfix}: {info['word_count']} words")
    print(f"    Examples: {', '.join(info['sample_words'][:3])}")
```

---

## CLI Usage with owlex

The `owlex` CLI tool filters word lists using JSON specification files. See [Interactive Word List Builder](../README.md#interactive-word-list-builder) for creating specifications.

### Basic Usage

```bash
# Filter using a specification file
owlex wordlist-spec.json

# Output to file
owlex wordlist-spec.json > filtered_words.txt

# Use verbose mode to see filtering details
owlex wordlist-spec.json --verbose
```

### Specification File Format

Create a JSON specification file defining your filters:

```json
{
  "version": "1.0",
  "distribution": "core",
  "filters": {
    "character": {
      "exact_length": 5
    },
    "frequency": {
      "min_tier": "A",
      "max_tier": "Q"
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

See `docs/schema/wordlist_spec.schema.json` for complete specification format and `examples/wordlist-specs/` for examples.

---

## Common Use Cases

### Word Game Development

```python
import marisa_trie
import random

# Load trie
trie = marisa_trie.Trie()
trie.load('core.trie')

# Get all 5-letter words
five_letter_words = [w for w in trie if len(w) == 5]
print(f"5-letter words: {len(five_letter_words)}")

# Random word selection
random_word = random.choice(five_letter_words)
print(f"Random 5-letter word: {random_word}")

# Check if player's word is valid
player_word = input("Enter a 5-letter word: ").strip().lower()
if player_word in trie and len(player_word) == 5:
    print("Valid word!")
else:
    print("Invalid word.")
```

### Autocomplete

```python
import marisa_trie

trie = marisa_trie.Trie()
trie.load('core.trie')

def autocomplete(prefix, limit=10):
    """Return up to `limit` words starting with `prefix`."""
    results = trie.keys(prefix)
    return list(results)[:limit]

# Example
suggestions = autocomplete('cas', limit=5)
print(suggestions)
# ['casaba', 'casabas', 'cascade', 'cascaded', 'cascades']
```

### NLP Pre-filtering

```python
import marisa_trie
import json

# Load plus distribution with rich labels
trie = marisa_trie.Trie()
trie.load('plus.trie')

with open('plus.meta.json', 'r') as f:
    metadata = json.load(f)

# Build lookup dict for fast access
word_to_entry = {entry['word']: entry for entry in metadata}

def is_valid_english(token):
    """Check if token is a valid English word."""
    return token.lower() in trie

def get_pos(token):
    """Get part-of-speech tags for token."""
    entry = word_to_entry.get(token.lower())
    return entry.get('pos', []) if entry else []

# Example
tokens = ['The', 'quick', 'brown', 'fox', 'jumps']
for token in tokens:
    print(f"{token}: valid={is_valid_english(token)}, pos={get_pos(token)}")
```

---

## Performance Notes

### Memory Usage

- **Trie**: ~510 KB (very compact)
- **Metadata**: ~28 MB per distribution (JSON)
- **Total**: ~28.5 MB loaded in memory

### Lookup Speed

- **Membership test** (`word in trie`): O(|word|) — extremely fast
- **Prefix search** (`trie.keys(prefix)`): O(|prefix| + results) — fast
- **Metadata access**: O(1) array indexing

### Optimization Tips

1. **Keep trie in memory**: Load once, reuse across requests
2. **Index metadata**: Build `word -> entry` dict for O(1) lookups
3. **Filter at query time**: Don't pre-filter unless memory-constrained
4. **Use binary formats**: Consider msgpack for metadata if size matters

Example indexed lookup:

```python
import marisa_trie
import json

# Load and index (do once at startup)
trie = marisa_trie.Trie()
trie.load('core.trie')

with open('core.meta.json', 'r') as f:
    metadata = json.load(f)

# Build index
word_index = {}
for entry in metadata:
    word = entry['word']
    if word in trie:
        word_id = trie[word][0]
        word_index[word] = entry

# Fast O(1) lookups
entry = word_index.get('castle')
print(entry)
```

---

## Distributions

### Core (CC BY 4.0)

- **Sources**: ENABLE (PD), EOWL (permissive)
- **Words**: 208,201
- **Labels**: Minimal (only from enrichment)
- **Use case**: Maximum permissiveness, no copyleft

### Plus (CC BY-SA 4.0)

- **Sources**: Core + Wiktionary + WordNet + Frequency
- **Words**: 208,204
- **Labels**: Rich (region, register, temporal, domain)
- **Use case**: Maximum coverage and metadata

Choose Core for commercial/proprietary use; choose Plus for open-source projects or when you need rich metadata.

---

## License Compliance

### Using Core Distribution

Provide attribution:

> "Openword Lexicon Core Distribution" by [contributors]
> Licensed under CC BY 4.0
> https://creativecommons.org/licenses/by/4.0/

### Using Plus Distribution

Provide attribution AND share-alike:

> "Openword Lexicon Plus Distribution" by [contributors]
> Licensed under CC BY-SA 4.0
> https://creativecommons.org/licenses/by-sa/4.0/

Derivative works must also be licensed under CC BY-SA 4.0 or compatible license.

See [ATTRIBUTION.md](../ATTRIBUTION.md) for full source attributions.

---

## Troubleshooting

### "Module not found: marisa_trie"

Install the dependency:

```bash
pip install marisa-trie
```

### "File not found: core.trie"

Ensure you're in the directory containing the extracted release files, or provide the full path:

```python
trie.load('/path/to/openword-lexicon-core-0.1.0/core.trie')
```

### Memory issues with large metadata

Load metadata on-demand instead of all at once:

```python
import json

def get_entry(word_id, meta_file='core.meta.json'):
    """Load single entry from JSON array (slower, but memory-efficient)."""
    with open(meta_file, 'r') as f:
        metadata = json.load(f)
    return metadata[word_id]
```

For production, consider converting to a database (SQLite, etc.) for indexed access.

---

## Further Reading

- [SCHEMA.md](SCHEMA.md) — Entry schema specification
- [DATASETS.md](DATASETS.md) — Source dataset details
- [DESIGN.md](DESIGN.md) — Architecture overview
- [ATTRIBUTION.md](../ATTRIBUTION.md) — Full source credits
