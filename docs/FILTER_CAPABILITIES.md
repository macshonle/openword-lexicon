# OpenWord Lexicon - Filter Capabilities Reference

This document describes which filtering capabilities are available on each distribution and their coverage/limitations.

---

## Distribution Overview

### Core Distribution
**License**: Ultra-permissive (Public Domain, UKACD)
**Sources**: ENABLE, EOWL, WordNet, OpenSubtitles frequency
**Total entries**: ~208,201 words
**Best for**: Commercial projects requiring permissive licensing

### Plus Distribution
**License**: Includes CC BY-SA 4.0
**Sources**: Core + Wiktionary
**Total entries**: ~1,039,950 words
**Best for**: Maximum vocabulary coverage, label-based filtering

---

## Filter Capability Matrix

| Filter Type | Core | Plus | Coverage | Notes |
|-------------|------|------|----------|-------|
| **Character filters** | ✅ | ✅ | 100% | Length, patterns, regex - always available |
| **Phrase filters** | ✅ | ✅ | 100% | Word count, multi-word detection |
| **Frequency tiers** | ✅ | ✅ | 100% | 6 tiers from OpenSubtitles corpus |
| **POS tags** | ✅ | ✅ | ~52.5% | Via WordNet enrichment |
| **Concreteness** | ✅ | ✅ | ~34.5% (Core), ~8.8% (Plus) | Concrete/abstract/mixed for nouns |
| **Register labels** | ❌ | ✅ | ~3.2% | Vulgar, offensive, slang, formal, etc. |
| **Temporal labels** | ❌ | ✅ | ~5.0% | Archaic, obsolete, dated, modern |
| **Domain labels** | ❌ | ✅ | ~3.3% | Medical, legal, technical, etc. |
| **Region labels** | ❌ | ✅ | ~1.9% | en-US, en-GB, etc. |
| **Syllable counts** | ❌ | ❌ | N/A | Not yet implemented |

---

## Detailed Capability Descriptions

### Character-Level Filters
**Available on**: Core, Plus
**Coverage**: 100%
**Requires**: Nothing (always available)

**Capabilities**:
- Minimum/maximum length
- Exact length (e.g., 5-letter words)
- Pattern matching (regex)
- Starts with / ends with / contains
- Exclude patterns

**Use cases**:
- Wordle lists (5-letter words)
- Scrabble constraints
- Mobile UI length limits
- Pattern-based games

**Example spec**:
```json
{
  "filters": {
    "character": {
      "exact_length": 5,
      "pattern": "^[a-z]+$",
      "exclude_pattern": "[qxz]"
    }
  }
}
```

---

### Phrase Filters
**Available on**: Core, Plus
**Coverage**: 100%
**Requires**: Nothing (always available)

**Capabilities**:
- Filter by word count (space-separated)
- Single words only (max_words: 1)
- Include short idioms (max_words: 3)
- Multi-word phrases only (is_phrase: true)

**Use cases**:
- Exclude long proverbs
- Extract idioms
- Single-word games (Wordle, Scrabble)

**Note**: Current dataset has very few multi-word phrases (~17 in Core).

**Example spec**:
```json
{
  "filters": {
    "phrase": {
      "max_words": 1
    }
  }
}
```

---

### Frequency Tier Filters
**Available on**: Core, Plus
**Coverage**: 100% (all entries assigned a tier)
**Requires**: Nothing (always available)

**Tiers**:
| Tier | Rank | Description | Typical Use |
|------|------|-------------|-------------|
| `top10` | 1-10 | Function words (the, and, be) | Ultra-common |
| `top100` | 11-100 | Core communication | Essential words |
| `top1k` | 101-1,000 | Everyday vocabulary | Beginner learners |
| `top10k` | 1,001-10,000 | Common words | General literacy |
| `top100k` | 10,001-100,000 | Extended vocabulary | Advanced learners |
| `rare` | >100,000 or unseen | Rare/specialized | Crosswords, technical |

**Data source**: OpenSubtitles 2018 corpus (50,000 ranked words)

**Use cases**:
- Kids' word lists (top1k-top10k)
- Language learning (progressive difficulty)
- Exclude rare words players won't know

**Example spec**:
```json
{
  "filters": {
    "frequency": {
      "tiers": ["top1k", "top10k"],
      "min_score": 70
    }
  }
}
```

---

### Part-of-Speech (POS) Filters
**Available on**: Core, Plus
**Coverage**: ~52.5% of entries
**Requires**: WordNet enrichment (automatic)

**Available POS tags**:
- `noun`, `verb`, `adjective`, `adverb`
- `pronoun`, `preposition`, `conjunction`
- `interjection`, `determiner`, `particle`, `auxiliary`

**Limitations**:
- ~47.5% of entries have no POS data
- Words with multiple POS roles have multiple tags
- Coverage better for common words

**Use cases**:
- Noun-only lists (20 Questions, Pictionary)
- Verb lists (charades, action games)
- Filter by grammatical role

**Example spec**:
```json
{
  "filters": {
    "pos": {
      "include": ["noun"],
      "require_pos": true
    }
  }
}
```

---

### Concreteness Filters
**Available on**: Core, Plus
**Coverage**: ~34.5% of Core, ~8.8% of Plus
**Requires**: WordNet enrichment (automatic), noun POS

**Values**:
- `concrete`: Physical, tangible objects (cat, table, rock)
- `abstract`: Ideas, qualities, concepts (freedom, love, theory)
- `mixed`: Both concrete and abstract senses (paper, face, bank)

**Limitations**:
- Only applies to nouns
- Core has better coverage than Plus
- Remaining nouns have no concreteness data

**Use cases**:
- Kids' games (concrete nouns only)
- Abstract concept lists
- Educational categorization

**Example spec**:
```json
{
  "filters": {
    "pos": {
      "include": ["noun"]
    },
    "concreteness": {
      "values": ["concrete"],
      "require_concreteness": true
    }
  }
}
```

---

### Register Labels (Wiktionary Only)
**Available on**: Plus only
**Coverage**: ~3.2% of Plus entries
**Requires**: Wiktionary source

**Values**:
- `vulgar`: Profanity, curse words
- `offensive`: Offensive language
- `derogatory`: Slurs, derogatory terms
- `slang`: Informal slang
- `colloquial`: Informal speech
- `formal`: Formal register
- `literary`: Literary language
- `euphemistic`: Euphemisms
- `humorous`: Humorous usage

**Flagged words**:
- Vulgar: ~3,286 words
- Offensive: ~1,476 words
- Derogatory: ~5,423 words
- **Total problematic**: ~10,185 words

**Limitations**:
- Only 11.2% of entries have ANY labels
- Some inappropriate words may not be labeled
- Manual review recommended for high-sensitivity apps

**Use cases**:
- Profanity blocklists
- Family-friendly filtering
- Content rating systems
- Exclude slang for formal contexts

**Example spec (family-friendly)**:
```json
{
  "filters": {
    "labels": {
      "register": {
        "exclude": ["vulgar", "offensive", "derogatory"]
      }
    }
  }
}
```

**Example spec (profanity blocklist)**:
```json
{
  "filters": {
    "labels": {
      "register": {
        "include": ["vulgar", "offensive", "derogatory"]
      }
    }
  }
}
```

---

### Temporal Labels (Wiktionary Only)
**Available on**: Plus only
**Coverage**: ~5.0% of Plus entries
**Requires**: Wiktionary source

**Values**:
- `archaic`: No longer in common use
- `obsolete`: No longer used
- `dated`: Somewhat old-fashioned
- `historical`: Historical contexts only
- `modern`: Recently coined

**Use cases**:
- Exclude archaic words for modern games
- Historical word lists
- Modern vocabulary filtering

**Example spec**:
```json
{
  "filters": {
    "labels": {
      "temporal": {
        "exclude": ["archaic", "obsolete", "dated"]
      }
    }
  }
}
```

---

### Domain Labels (Wiktionary Only)
**Available on**: Plus only
**Coverage**: ~3.3% of Plus entries
**Requires**: Wiktionary source

**Values**:
- `medical`, `legal`, `technical`, `scientific`
- `military`, `nautical`, `botanical`, `zoological`
- `computing`, `mathematics`, `music`, `art`
- `religion`, `culinary`, `sports`, `business`, `finance`

**Use cases**:
- Exclude jargon for general audiences
- Domain-specific word lists
- Educational vocabulary by subject

**Example spec (no jargon)**:
```json
{
  "filters": {
    "labels": {
      "domain": {
        "exclude": ["medical", "legal", "technical", "scientific"]
      }
    }
  }
}
```

---

### Region Labels (Wiktionary Only)
**Available on**: Plus only
**Coverage**: ~1.9% of Plus entries
**Requires**: Wiktionary source

**Format**: BCP 47 language subtags (e.g., `en-US`, `en-GB`)

**Common values**:
- `en-US`: American English
- `en-GB`: British English
- Other variants as available in Wiktionary

**Use cases**:
- American English spelling only
- British English spelling only
- Regional dialect filtering

**Example spec (American only)**:
```json
{
  "filters": {
    "labels": {
      "region": {
        "exclude": ["en-GB"]
      }
    }
  }
}
```

---

### Source Filters
**Available on**: Core, Plus
**Coverage**: 100% (all entries have sources)
**Requires**: Nothing (always available)

**Sources**:

**Core sources**:
- `enable`: ENABLE word list (Public Domain, 172,823 words)
- `eowl`: English Open Word List (UKACD License, 128,983 words)
- `wordnet`: Princeton WordNet (WordNet License)
- `frequency`: OpenSubtitles frequency data

**Plus-only sources**:
- `wikt`: Wiktionary (CC BY-SA 4.0, 1,028,344 words)

**Use cases**:
- License-specific filtering
- Source provenance tracking
- Combine/exclude specific datasets

**Example spec (Wiktionary only)**:
```json
{
  "filters": {
    "sources": {
      "include": ["wikt"]
    }
  }
}
```

---

### Syllable Count Filters (Future Feature)
**Available on**: Neither (not yet implemented)
**Coverage**: Would be ~18.79% of Plus
**Requires**: Implementation pending

**Potential capabilities**:
- Minimum/maximum syllable count
- Exact syllable count
- Filter to words with known syllable data

**Note**: Analysis complete, extraction strategy documented, but not integrated into pipeline.

---

## Policy-Level Filters

These are convenience filters that combine multiple criteria:

### `family_friendly: true`
**Expands to**:
```json
{
  "labels": {
    "register": {
      "exclude": ["vulgar", "offensive", "derogatory"]
    }
  }
}
```

### `modern_only: true`
**Expands to**:
```json
{
  "labels": {
    "temporal": {
      "exclude": ["archaic", "obsolete", "dated"]
    }
  }
}
```

### `no_jargon: true`
**Expands to**:
```json
{
  "labels": {
    "domain": {
      "exclude": ["medical", "legal", "technical", "scientific"]
    }
  }
}
```

---

## Combining Filters

Filters can be combined for precise word list generation:

### Example: Kids' Game Words
```json
{
  "version": "1.0",
  "name": "Kids Game Words",
  "distribution": "core",
  "filters": {
    "character": {
      "min_length": 3,
      "max_length": 10
    },
    "phrase": {
      "max_words": 1
    },
    "frequency": {
      "tiers": ["top1k", "top10k"]
    },
    "pos": {
      "include": ["noun"]
    },
    "concreteness": {
      "values": ["concrete"]
    },
    "policy": {
      "family_friendly": true,
      "modern_only": true
    }
  }
}
```

### Example: Wordle Word List
```json
{
  "version": "1.0",
  "name": "Wordle Words",
  "distribution": "core",
  "filters": {
    "character": {
      "exact_length": 5,
      "pattern": "^[a-z]+$"
    },
    "phrase": {
      "max_words": 1
    },
    "frequency": {
      "min_tier": "top10k"
    },
    "policy": {
      "modern_only": true
    }
  }
}
```

### Example: Profanity Blocklist
```json
{
  "version": "1.0",
  "name": "Profanity Blocklist",
  "distribution": "plus",
  "filters": {
    "labels": {
      "register": {
        "include": ["vulgar", "offensive", "derogatory"]
      }
    }
  }
}
```

---

## Coverage Summary

**Core Distribution (208,201 words)**:
- Character filters: 100%
- Frequency tiers: 100%
- POS tags: ~52.5%
- Concreteness: ~34.5%
- Labels: 0% (no Wiktionary)

**Plus Distribution (1,039,950 words)**:
- Character filters: 100%
- Frequency tiers: 100%
- POS tags: ~52.5%
- Concreteness: ~8.8% (lower due to larger dataset)
- Register labels: ~3.2%
- Temporal labels: ~5.0%
- Domain labels: ~3.3%
- Region labels: ~1.9%

---

## License Considerations

### Core Distribution
**All sources are ultra-permissive**:
- No attribution required
- Commercial use allowed
- Redistribution allowed
- Modification allowed

**Sources**:
- ENABLE: Public Domain
- EOWL: UKACD License (permissive)
- WordNet: WordNet License (permissive)

**Use Core when**: You need maximum license flexibility

### Plus Distribution
**Includes CC BY-SA sources**:
- Attribution required (Wiktionary contributors)
- Share-alike clause applies
- Commercial use allowed with restrictions

**Sources**:
- All Core sources
- Wiktionary: CC BY-SA 4.0

**Use Plus when**: You need maximum vocabulary coverage and can comply with CC BY-SA

---

## Best Practices

### 1. Start with Distribution Selection
- Need permissive licensing? → Use Core
- Need label filtering (profanity, domain, etc.)? → Must use Plus
- Need maximum vocabulary? → Use Plus

### 2. Layer Filters Appropriately
1. **Character filters**: Always reliable (100% coverage)
2. **Frequency filters**: Always reliable (100% coverage)
3. **POS/concreteness**: Moderate coverage (~50%, ~35%)
4. **Labels**: Low coverage (~3-5%, Plus only)

### 3. Handle Missing Metadata
When filtering by metadata fields (POS, concreteness, labels):
- Use `require_*` flags to enforce presence
- Or accept gaps in coverage
- More restrictive = fewer results but higher quality

### 4. Test Your Specifications
```bash
# Generate and review output
owlex filter spec.json --limit 100 > sample.txt
cat sample.txt

# Check result count
owlex filter spec.json | wc -l

# Review with metadata
owlex filter spec.json --format json | jq '.[0:10]'
```

---

## See Also

- [Word List Specification Schema](schema/wordlist_spec.schema.json)
- [CAPABILITY_AUDIT.md](../CAPABILITY_AUDIT.md) - Full capability audit
- [FILTERING.md](FILTERING.md) - Phrase and character filtering guide
- [SCHEMA.md](SCHEMA.md) - Entry schema reference
