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

# Find all concrete nouns in top 10k frequency
concrete_nouns = []
for entry in metadata:
    if (
        'noun' in entry.get('pos', []) and
        entry.get('concreteness') == 'concrete' and
        entry.get('frequency_tier') in ['top10', 'top100', 'top1k', 'top10k']
    ):
        concrete_nouns.append(entry['word'])

print(f"Found {len(concrete_nouns)} concrete nouns in top 10k")
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

---

## CLI Usage with owlex

The `owlex` CLI tool filters word lists using JSON specification files. See [Interactive Word List Builder](../README.md#interactive-word-list-builder) for creating specifications.

### Basic Usage

```bash
# Filter using a specification file
owlex filter wordlist-spec.json

# Output to file
owlex filter wordlist-spec.json > filtered_words.txt

# Use verbose mode to see filtering details
owlex filter wordlist-spec.json --verbose
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
      "tiers": ["top1k", "top3k", "top10k"]
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
