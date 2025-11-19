# Openword Lexicon — Source Datasets

This document describes the source datasets used in the Openword Lexicon.

## Table of Contents

- [Overview](#overview)
- [Core Sources](#core-sources)
- [Plus Sources](#plus-sources)
- [License Summary](#license-summary)

---

## Overview

The Openword Lexicon is built from multiple open-source word lists and linguistic resources. Sources are carefully selected for:

1. **Open licensing** (Public Domain, CC0, CC BY, or CC BY-SA)
2. **Quality** (well-maintained, widely used)
3. **Coverage** (comprehensive English vocabulary)
4. **Provenance** (clear authorship and attribution)

**Two distributions:**
- **Core**: Ultra-permissive sources only (PD, CC0, CC BY)
- **Plus**: Core + additional CC BY-SA sources

---

## Core Sources

### ENABLE (Enhanced North American Benchmark LExicon) — **OPTIONAL**

**Author**: Alan Beale et al.

**License**: Public Domain (CC0 1.0)

**URL**: https://github.com/dolph/dictionary

**Word Count**: 172,823

**Status**: **Optional - Validation Only**

**Description**:
ENABLE is a Public Domain word list originally created for word games. It contains common English words up to moderate length, with no proper nouns, hyphenated compounds, or diacritics.

**Why Optional?**
- Wiktionary provides far more comprehensive coverage (1.29M vs 172k words)
- ENABLE contributes no metadata (POS tags, morphology, labels, etc.)
- EOWL provides adequate permissive-licensed core vocabulary
- Frequency data provides better filtering than ENABLE's scope
- GitHub CDN reliability issues

**Current Use**: Periodic validation baseline to verify we haven't regressed on classic word game vocabulary. Not required for builds.

**Characteristics:**
- Simple word list (one word per line)
- No linguistic markup (POS, definitions, etc.)
- American English bias
- Widely used in Scrabble-like games

**Attribution**: Not required (Public Domain), but we credit Alan Beale for his work.

**Integration**:
- **Optional fetch**: `make validate-enable` (not part of `make fetch-en`)
- When present: Ingested alongside EOWL with NFKC normalization
- When absent: Build proceeds successfully with EOWL + Wiktionary
- Source ID: `enable` (when present)

---

### EOWL (English Open Word List)

**Author**: Ken Loge (derived from UK Advanced Cryptics Dictionary by J. Ross Beresford)

**License**: UKACD License (permissive, attribution required)

**URL**: https://github.com/kloge/The-English-Open-Word-List

**Word Count**: 128,983

**Description**:
EOWL is derived from the UK Advanced Cryptics Dictionary, a crossword-puzzle dictionary. It contains British English words up to 10 letters.

**Characteristics:**
- Words up to 10 letters only
- No proper nouns
- No hyphenated words
- Diacritics removed
- British English bias

**License Text**:
> The UK Advanced Cryptics Dictionary (UKACD) is © J Ross Beresford 1993–1999. Permission is granted to use this list for any purpose provided this notice is retained. No warranty is given.

**Integration**:
- Ingested as-is with NFKC normalization
- POS tags backfilled via WordNet
- Source ID: `eowl`

---

## Plus Sources

### Wiktionary (English)

**Contributors**: Wiktionary community

**License**: CC BY-SA 4.0

**URL**: https://en.wiktionary.org/

**Extraction Tool**: Custom scanner parser ([wiktionary_scanner_parser.py](../tools/wiktionary_scanner_parser.py))
- Note: [wiktextract](https://github.com/tatuylonen/wiktextract) was initially considered but replaced with a custom solution for 10-100x better performance and greater control

**Word Count**: ~1.3M entries (full Wiktionary English extraction)

**Description**:
Wiktionary is a collaborative, multilingual dictionary with rich linguistic data including POS tags, definitions, etymology, pronunciation, usage labels, and regional variants.

**Characteristics:**
- Multi-word phrases included
- Rich metadata: POS, labels, inflections
- Regional variants (en-GB, en-US, etc.)
- Usage labels (vulgar, archaic, slang, etc.)
- Etymology data with morphological structure
- Syllable counts from hyphenation templates
- Continuously updated

**Attribution Required**: Yes

**Integration**:
- Extracted via custom scanner parser (wiktionary_scanner_parser.py) to JSONL
- Lightweight regex-based parser: 10-100x faster than wiktextract
- Mapped to schema with label taxonomy
- Provides: POS, register labels, regional labels, temporal labels
- Provides: Syllable counts (~30-50% coverage)
- Provides: Morphology data from etymology templates (~240,000 words)
  - **Derivation structure**: Prefix, suffix, affix, circumfix templates
  - **Compound word decomposition**: Including interfixes
  - **Base word and morpheme tracking**: Enables word family queries
  - **Affix inventory**: ~450 prefixes, ~380 suffixes, ~12 interfixes
  - **Coverage breakdown**:
    - Suffixed words: ~107,000 (44.6%)
    - Prefixed words: ~105,000 (43.6%)
    - Compounds: ~25,000 (10.3%)
    - Affixed (prefix+suffix): ~1,900 (0.8%)
    - With interfixes: ~850 words
  - **Phase 2 enhancements** (2025-11):
    - Template parameter cleaning (fixes ~3,800 polluted entries)
    - Interfix detection and classification
    - Reverse affix index for efficient queries
  - Enables word family queries and morphological analysis
- Source ID: `wikt`

---

### WordNet (Princeton)

**Author**: Princeton University

**License**: WordNet License (BSD-style, permissive)

**URL**: https://wordnet.princeton.edu/

**Word Count**: Used for enrichment (not direct word source)

**Description**:
WordNet is a lexical database grouping words into synsets (sets of cognitive synonyms). Used for:
- **Concreteness classification**: Distinguishes concrete vs. abstract nouns
- **POS backfilling**: Adds POS tags where missing

**Characteristics:**
- Hierarchical semantic network
- Focus on nouns, verbs, adjectives, adverbs
- Sense distinctions (polysemy)
- Lexical relations (synonymy, hypernymy, etc.)

**Attribution Required**: Yes (for academic use)

**Integration**:
- Accessed via NLTK
- Enriches existing entries with `concreteness` and `pos`
- Does not add new words to lexicon
- Source ID: `wordnet` (in provenance metadata)

---

### Brysbaert Concreteness Ratings

**Authors**: Marc Brysbaert, Amy Beth Warriner, Victor Kuperman

**License**: Research/Educational Use (shared by authors for research purposes)

**URL**: https://github.com/ArtsEngine/concreteness

**Entry Count**: 39,954

**Description**:
Concreteness ratings for ~40,000 English word lemmas collected via crowdsourcing. Each word was rated by multiple participants on a 1-5 scale, where 1 represents highly abstract concepts (like "freedom" or "justice") and 5 represents highly concrete, tangible objects (like "castle" or "apple"). The dataset includes both the mean rating and standard deviation for each word, providing confidence measures for the ratings.

**Academic Citation**:
> Brysbaert, M., Warriner, A.B., & Kuperman, V. (2014). Concreteness ratings for 40 thousand generally known English word lemmas. *Behavior Research Methods*, 46, 904-911. DOI: [10.3758/s13428-013-0403-5](https://doi.org/10.3758/s13428-013-0403-5)

**Characteristics:**
- Empirically collected via crowdsourcing
- Mean concreteness ratings (1.0-5.0 scale)
- Standard deviation for each rating (confidence measure)
- Lemmas only (base forms, not inflections)
- Significantly better coverage than WordNet alone (~40k vs ~20-30k)

**Attribution Required**: Yes (for academic/research use)

**Integration**:
- Enriches existing entries with three fields:
  - `concreteness`: Categorical classification (concrete/mixed/abstract)
  - `concreteness_rating`: Raw mean rating (1.0-5.0)
  - `concreteness_sd`: Standard deviation of ratings
- Preferred over WordNet concreteness by default
- Does not add new words to lexicon
- Source ID: `brysbaert` (in provenance metadata)
- License ID: `Brysbaert-Research` (in license tracking)

**Coverage Statistics**:
- Total entries with Brysbaert data: ~39,561
- Concrete (rating ≥ 3.5): ~37,933 nouns
- Abstract (rating < 2.5): ~31,188 nouns
- Mixed (rating 2.5-3.5): ~30,929 nouns

**Use Cases**:
- Children's educational apps (filter for concrete, tangible words)
- Language learning tools (start with concrete vocabulary)
- Accessibility applications (simplify to concrete language)
- Word games requiring specific vocabulary types
- NLP applications distinguishing abstract vs concrete concepts

---

### OpenSubtitles 2018 Frequency Data

**Compiler**: Hermit Dave (from OpenSubtitles.org data)

**License**: CC BY-SA 4.0

**URL**: https://github.com/hermitdave/FrequencyWords

**Entry Count**: 50,000

**Description**:
Word frequency data compiled from movie and TV subtitles corpus. Used to assign logarithmic frequency tier codes (A-Z) based on rank.

**Characteristics:**
- Based on spoken language (subtitles)
- Modern, conversational vocabulary
- Logarithmic scale (base 10^0.25) for even distribution across frequency spectrum
- Single-letter codes: A (rank 1) to T (top ~75k), Z (unranked)

**Attribution Required**: Yes

**Integration**:
- Loaded as frequency list (word + count)
- Mapped to logarithmic tier codes using rank_to_code()
- Enriches entries with `frequency_tier` field (single letter A-Z)
- Source ID: `frequency` (in provenance metadata)
- See [frequency_tiers.py](../src/openword/frequency_tiers.py) for tier algorithm

---

## License Summary

| Source | License | Distribution | Words | Attribution | ShareAlike |
|--------|---------|--------------|-------|-------------|------------|
| ENABLE | Public Domain (CC0) | Core | 172,823 | Optional | No |
| EOWL | UKACD License | Core | 128,983 | Required | No |
| Wiktionary | CC BY-SA 4.0 | Plus | Sample | Required | Yes |
| WordNet | WordNet License | Plus | (enrichment) | Required | No |
| Brysbaert | Research Use | Plus | 39,954 | Required | No |
| Frequency | CC BY-SA 4.0 | Plus | (tiers) | Required | Yes |

**Core distribution**: CC BY 4.0 (most permissive common license)

**Plus distribution**: CC BY-SA 4.0 (requires ShareAlike due to Wiktionary and Frequency data)

---

## Data Quality

### Overlap and Deduplication

Words appearing in multiple sources are merged with union of metadata:

```
Example: "castle"
  - ENABLE: ✓ (no metadata)
  - EOWL: ✓ (no metadata)
  - Wiktionary: ✓ (POS: noun, verb; syllables: 2)
  - WordNet: ✓ (concreteness: mixed)

  Merged entry:
    word: "castle"
    pos: ["noun", "verb"]
    concreteness: "mixed"
    syllables: 2
    sources: ["enable", "eowl", "wikt"]

Example: "happiness" (with morphology)
  - ENABLE: ✓ (no metadata)
  - Wiktionary: ✓ (POS: noun; morphology: suffixed, base="happy", suffixes=["-ness"])

  Merged entry:
    word: "happiness"
    pos: ["noun"]
    morphology: {
      type: "suffixed",
      base: "happy",
      components: ["happy", "-ness"],
      suffixes: ["-ness"]
    }
    sources: ["enable", "wikt"]
```

**Unique words:**
- Core: 208,201 (after deduplication)
- Plus: 208,204 (includes 3 words only in Wiktionary sample)

### Normalization

All words normalized to **Unicode NFKC** for consistency:
- Canonical decomposition + compatibility composition
- Example: `café` → `café` (consistent representation)

### Quality Checks

1. **Schema validation**: All entries pass JSON Schema validation
2. **Provenance**: Every entry tracks source datasets
3. **Checksums**: SHA256 hashes for reproducibility
4. **Smoke tests**: Sample words verified in each distribution

### Morphology Statistics

**Overall Coverage** (from Wiktionary etymology templates):
- Total words with morphology: ~240,000
- Coverage rate: ~18% of lexicon entries
- Data source: Custom scanner parser of Wiktionary XML dumps

**Formation Types:**
| Type | Count | Percentage | Example |
|------|------:|-----------:|---------|
| Suffixed | ~107,000 | 44.6% | happiness (happy + -ness) |
| Prefixed | ~105,000 | 43.6% | unhappy (un- + happy) |
| Compound | ~25,000 | 10.3% | bartender (bar + tender) |
| Affixed | ~1,900 | 0.8% | unbreakable (un- + break + -able) |
| Circumfixed | ~1,600 | 0.7% | enlightenment (en- + light + -ment) |

**Affix Inventory:**
- Unique prefixes: ~450
- Unique suffixes: ~380
- Unique interfixes: ~12 (linking morphemes like -s- in "beeswax")

**Most Productive Prefixes** (by word count):
| Prefix | Words | Top POS | Examples |
|--------|------:|---------|----------|
| un- | ~11,200 | adjective | unhappy, unable, unclear |
| non- | ~10,000 | adjective | nonexistent, nontrivial |
| anti- | ~3,300 | noun | antibody, antibiotic |
| re- | ~3,200 | verb | rebuild, return, rewrite |
| pre- | ~2,800 | adjective | preview, prehistoric |

**Most Productive Suffixes** (by word count):
| Suffix | Words | Top POS | Examples |
|--------|------:|---------|----------|
| -ly | ~12,700 | adverb | quickly, happily, slowly |
| -ness | ~9,700 | noun | happiness, darkness, kindness |
| -er | ~6,500 | noun | teacher, builder, worker |
| -ic | ~4,300 | adjective | historic, basic, magic |
| -ism | ~3,400 | noun | capitalism, socialism |

**Data Quality Improvements (Phase 2)**:
- Template parameter cleaning: Fixed ~3,800 entries (1.6% of morphology data)
- Interfix detection: Added ~850 compound words with linking morphemes
- Reverse affix index: Enables efficient affix→words lookups

---

## Future Sources (Under Consideration)

### GCIDE (GNU Collaborative International Dictionary of English)

- **License**: GPL (requires investigation for data-only use)
- **Coverage**: ~150,000 entries with definitions
- **Status**: Not yet integrated

### Moby Word Lists

- **License**: Public Domain
- **Coverage**: Multiple specialized lists
- **Status**: Not yet integrated

### Additional Frequency Corpora

- **Google Books Ngrams**: For historical frequency trends
- **BNC (British National Corpus)**: British English frequency
- **Status**: Not yet integrated

---

## Fetching Sources

All required sources are fetched automatically via `make fetch-en`:

```bash
# Fetch all required sources
make fetch-en

# This runs:
# - fetch_eowl.sh          # Core word list (required)
# - fetch_wiktionary.sh    # Large download (2-3 GB)
# - fetch_wordnet.sh       # Via NLTK
# - fetch_brysbaert.sh     # Concreteness ratings
# - fetch_frequency.sh     # Frequency data
```

### Optional: ENABLE Validation

ENABLE is **no longer required** for builds. Use it only for optional validation:

```bash
# Optional: Validate against ENABLE baseline
make validate-enable

# This will:
# 1. Fetch ENABLE (if not present)
# 2. Compare lexicon coverage against ENABLE
# 3. Report coverage statistics
```

Each script:
1. Downloads source data
2. Verifies integrity (where possible)
3. Creates `*.SOURCE.json` with metadata (URL, license, checksum, word count, download timestamp)

---

## Attribution

Full attribution for all sources is provided in [ATTRIBUTION.md](../ATTRIBUTION.md).

When using this lexicon, you must provide attribution according to the license of the distribution you use:

- **Core**: CC BY 4.0 attribution
- **Plus**: CC BY-SA 4.0 attribution + ShareAlike

---

## See Also

- [ATTRIBUTION.md](../ATTRIBUTION.md) — Full source credits
- [SCHEMA.md](SCHEMA.md) — Entry schema details
- [labels.md](../docs/labels.md) — Label taxonomy
- [DESIGN.md](DESIGN.md) — Architecture overview
