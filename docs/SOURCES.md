# Data Sources

Where the data comes from and how licensing works.

## Primary Word Sources

| Source | Words | License | Notes |
|--------|-------|---------|-------|
| **Wiktionary** | ~1.3M | CC BY-SA 4.0 | Comprehensive, includes labels, definitions |
| **EOWL** | ~129K | UKACD (permissive) | Curated for games, max 10 letters |
| **WordNet** | ~162K | CC BY 4.0 | POS data, semantic relations |

### Wiktionary

The English Wiktionary dump provides the richest data:
- Part of speech tags
- Register labels (formal, informal, vulgar, etc.)
- Regional labels (en-US, en-GB, etc.)
- Domain labels (medical, legal, etc.)
- Temporal labels (archaic, obsolete)
- Syllable counts (from hyphenation)
- Etymology and morphology

**License**: CC BY-SA 4.0 — requires attribution and share-alike for derivatives.

**Download**: `scripts/fetch/fetch_wiktionary.sh`

### EOWL (English Open Word List)

A curated word list designed for word games:
- Single words only (no phrases)
- Maximum 10 characters
- Common, recognizable words
- British English focus

**License**: UKACD License — unrestricted use with attribution.

**Download**: `scripts/fetch/fetch_eowl.sh`

### WordNet (Open English WordNet 2024)

Semantic lexical database:
- Part of speech tags
- Synsets (word groupings by meaning)
- Semantic relations

**License**: CC BY 4.0 — requires attribution, no share-alike requirement.

**Download**: `scripts/fetch/fetch_wordnet.sh`

## Enrichment Sources

| Source | Data | License |
|--------|------|---------|
| **Brysbaert** | Concreteness ratings | Research/Educational |
| **OpenSubtitles** | Frequency data | CC BY-SA 4.0 |

### Brysbaert Concreteness Ratings

Academic study providing concreteness ratings (1.0-5.0 scale) for ~40,000 English words.

- 1.0 = highly abstract (e.g., "freedom", "justice")
- 5.0 = highly concrete (e.g., "apple", "chair")

**License**: Research and educational use. Contact authors for commercial licensing.

**Citation**: Brysbaert, M., Warriner, A.B., & Kuperman, V. (2014). Concreteness ratings for 40 thousand generally known English word lemmas.

### OpenSubtitles Frequency Data

Word frequency ranks derived from movie/TV subtitles corpus (~50,000 words).

**License**: CC BY-SA 4.0

**Download**: `scripts/fetch/fetch_frequency.sh`

## Per-Word Source Tracking

Every word in the lexicon includes source attribution:

```json
{
  "word": "castle",
  "sources": ["eowl", "wikt", "wordnet"],
  "license_sources": {
    "UKACD": ["eowl"],
    "CC-BY-SA-4.0": ["wikt"],
    "CC-BY-4.0": ["wordnet"]
  }
}
```

This enables runtime filtering by license requirements.

## License Implications

### CC BY-SA 4.0 (Wiktionary)

- **Attribution**: Must credit Wiktionary
- **Share-Alike**: Derivatives must use same license
- **Commercial**: Allowed

If you include Wiktionary-sourced words, your word list may need to be CC BY-SA 4.0.

### CC BY 4.0 (WordNet)

- **Attribution**: Must credit WordNet
- **Share-Alike**: Not required
- **Commercial**: Allowed

### UKACD (EOWL)

- **Attribution**: Must acknowledge UKACD
- **Share-Alike**: Not required
- **Commercial**: Allowed

### Permissive-Only Filtering

For maximum license flexibility, exclude Wiktionary:

```python
# Python
permissive_words = [
    entry['word'] for entry in load_lexemes()
    if 'wikt' not in entry.get('sources', [])
]
```

```json
// JSON spec
{
  "filters": {
    "sources": {
      "exclude": ["wikt"]
    }
  }
}
```

This gives you ~200K words from EOWL + WordNet under permissive licenses.

## Attribution Requirements

### Minimal Attribution

```
Word data from:
- English Wiktionary (CC BY-SA 4.0)
- English Open Word List (UKACD License)
- Open English WordNet 2024 (CC BY 4.0)
```

### Full Attribution

See the generated `ATTRIBUTION.md` file after building, which includes:
- Full license texts
- Source URLs
- Download dates
- Checksums

## Source Statistics

After build, source distribution:

| Source Combination | Words |
|--------------------|-------|
| Wiktionary only | ~1.1M |
| Wiktionary + EOWL | ~45K |
| Wiktionary + WordNet | ~80K |
| All three sources | ~40K |
| EOWL only | ~2K |
| WordNet only | ~5K |
| EOWL + WordNet | ~8K |

Most words come from Wiktionary. EOWL and WordNet add ~15K unique words not in Wiktionary and provide cross-validation for common words.

## Updating Sources

### Wiktionary Updates

Wiktionary dumps are updated monthly. To refresh:

```bash
rm data/raw/en/enwiktionary-*.xml.bz2
make fetch-en
make build-en
```

### WordNet Updates

Open English WordNet releases annually. Check for new versions at:
https://en-word.net/

### Source Quality

| Source | Coverage | Accuracy | Maintenance |
|--------|----------|----------|-------------|
| Wiktionary | Comprehensive | Community-edited | Active |
| EOWL | Game-focused | Curated | Stable |
| WordNet | Academic | Expert-verified | Annual |

## Adding New Sources

To add a new word source:

1. Create fetch script: `scripts/fetch/fetch_newsource.sh`
2. Add to `SOURCE_LICENSES` in `src/openword/source_merge.py`
3. Implement loader function in `source_merge.py`
4. Update Makefile `fetch-en` target
5. Document license in this file
