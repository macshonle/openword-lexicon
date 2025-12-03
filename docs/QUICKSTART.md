# Quick Start

Get words into your application in 5 minutes.

## Option 1: Use Pre-built Files

Download a release or build locally, then use the output files directly.

### Check if a Word Exists (Python)

```python
import marisa_trie

# Load trie (memory-mapped for efficiency)
trie = marisa_trie.Trie().mmap('data/build/en.trie')

# Check membership
print('castle' in trie)      # True
print('xyzzy' in trie)       # False
print(len(trie))             # ~1,350,000

# Prefix search
print(list(trie.keys('cast'))[:5])  # ['cast', 'caste', 'casted', 'caster', ...]
```

### Check if a Word Exists (JavaScript)

For browser use, see the [viewer/](../viewer/) directory which includes a binary trie loader.

```javascript
// Using the binary trie loader
import { BinaryTrie } from './binary-trie.js';

const trie = await BinaryTrie.load('en.trie.bin');
console.log(trie.has('castle'));  // true
console.log(trie.keysWithPrefix('cast'));  // ['cast', 'castle', ...]
```

### Load Word Metadata

```python
import gzip
import json

# Load frequency tiers
with gzip.open('data/build/en-frequency.json.gz', 'rt') as f:
    frequency = json.load(f)

print(frequency.get('the'))     # 'A' (most frequent)
print(frequency.get('castle'))  # 'N' (common)
print(frequency.get('zugzwang')) # 'Z' (rare)

# Load concreteness ratings
with gzip.open('data/build/en-concreteness.json.gz', 'rt') as f:
    concreteness = json.load(f)

print(concreteness.get('apple'))   # 4.93 (very concrete)
print(concreteness.get('freedom')) # 1.73 (abstract)
```

## Option 2: Use the Lexemes File

For filtering and detailed metadata, use the JSONL lexemes file:

```python
import json

def load_lexemes(path='data/intermediate/en-lexemes-enriched.jsonl'):
    with open(path) as f:
        for line in f:
            yield json.loads(line)

# Find 5-letter nouns
five_letter_nouns = [
    entry['word'] for entry in load_lexemes()
    if len(entry['word']) == 5
    and 'noun' in entry.get('pos', [])
    and entry['word'].isalpha()
]

print(five_letter_nouns[:10])
# ['about', 'above', 'abuse', 'actor', 'adult', ...]
```

## Option 3: Use the Filter Tool

Create a JSON specification and run the filter:

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
      "rarest_allowed": "F"
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

Save as `my-filter.json` and run:

```bash
uv run python -m openword.owlex my-filter.json > words.txt
```

## Option 4: Interactive Spec Editor

Build filter specs visually:

```bash
make spec-editor-web
# Opens http://localhost:8000
```

## Common Recipes

### Wordle Words

5-letter common words, game-safe:

```python
wordle_words = [
    entry['word'] for entry in load_lexemes()
    if len(entry['word']) == 5
    and entry['word'].isalpha()
    and entry['word'].islower()
    and entry.get('frequency_tier', 'Z') <= 'F'  # Common words
]
```

### Kids Vocabulary

Concrete nouns that children know:

```python
kids_words = [
    entry['word'] for entry in load_lexemes()
    if 'noun' in entry.get('pos', [])
    and entry.get('concreteness', 0) >= 4.0  # Very concrete
    and entry.get('frequency_tier', 'Z') <= 'G'  # Common
    and len(entry['word']) <= 8
]
```

### Profanity Blocklist

Words marked as vulgar, offensive, or derogatory:

```python
blocklist = [
    entry['word'] for entry in load_lexemes()
    if any(label in entry.get('labels', {}).get('register', [])
           for label in ['vulgar', 'offensive', 'derogatory'])
]
```

### Permissive License Only

Words from EOWL or WordNet (no CC-BY-SA requirement):

```python
permissive_words = [
    entry['word'] for entry in load_lexemes()
    if 'wikt' not in entry.get('sources', [])
]
```

## Next Steps

- [SCHEMA.md](SCHEMA.md) — Full field reference
- [FILTERING.md](FILTERING.md) — All filter options
- [SOURCES.md](SOURCES.md) — Licensing details
