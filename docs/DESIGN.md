# Openword Lexicon — Design & Architecture

This document describes the design decisions and architecture of the Openword Lexicon.

## Table of Contents

- [Goals & Constraints](#goals--constraints)
- [Pipeline Architecture](#pipeline-architecture)
- [Data Structures](#data-structures)
- [Design Decisions](#design-decisions)
- [Performance Characteristics](#performance-characteristics)

---

## Goals & Constraints

### Primary Goals

1. **Permissive licensing**: Usable in any application (games, NLP, education)
2. **Rich metadata**: POS tags, frequency tiers, usage labels
3. **Fast lookups**: O(log n) membership tests, prefix searches
4. **Two distributions**: Ultra-permissive (core) vs. enhanced (plus)
5. **Reproducible builds**: Checksums, provenance tracking
6. **Compact storage**: Trie compression, efficient serialization

### Hard Constraints

- **Total downloads**: ≤ 100 GB (imposed by GitHub LFS and typical CI limits)
- **Peak RAM per step**: ≤ 2 GB (for CI/CD and modest hardware)
- **Build time**: < 2 hours for full pipeline (CI timeout limits)

### Soft Constraints

- **Trie size**: Aim for < 1 MB per distribution
- **Metadata size**: Aim for < 50 MB per distribution
- **Lookup speed**: Sub-millisecond for membership tests

---

## Pipeline Architecture

### High-Level Flow

```
┌─────────────────────────────────────┐
│  Guardrails (disk/RAM limits)       │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Fetch sources (checksums,          │
│  provenance)                        │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Normalization (schema, NFKC,       │
│  labels)                            │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Core ingest (EOWL → JSONL)         │
│  [ENABLE optional via validate]     │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Wiktionary extraction (plus only)  │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  WordNet enrichment (concreteness,  │
│  POS)                               │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Frequency tiers (bucketing)        │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Merge & deduplicate (per           │
│  distribution)                      │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Policy filters (family-friendly,   │
│  etc.)                              │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Attribution (ATTRIBUTION.md,       │
│  LICENSE)                           │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Trie build (MARISA + metadata      │
│  sidecar)                           │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  CI/CD (workflows, manifest)        │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Packaging (tarballs, checksums)    │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│  Documentation                      │
└─────────────────────────────────────┘
```

### Data Flow

```
data/raw/           ← Fetched sources (EOWL, Wiktionary dump, WordNet, etc.)
  ├── en/           ← English sources (ENABLE optional for validation)
  └── diagnostic/   ← Test/diagnostic data

data/intermediate/  ← Processed entries (JSONL)
  ├── core/
  │   ├── core_entries.jsonl         ← Raw ingest
  │   ├── core_entries_enriched.jsonl ← + WordNet
  │   ├── core_entries_tiered.jsonl   ← + Frequency
  │   └── entries_merged.jsonl        ← Deduplicated
  └── plus/
      └── (same structure)

data/filtered/      ← Policy-filtered views
  ├── core/
  │   └── family_friendly.jsonl
  └── plus/
      └── family_friendly.jsonl

data/build/         ← Final artifacts
  ├── core/
  │   ├── core.trie             ← MARISA trie
  │   └── core.meta.json        ← Metadata sidecar
  └── plus/
      └── (same structure)

data/artifacts/releases/  ← Packaged releases
  ├── openword-lexicon-core-0.1.0.tar.gz
  ├── openword-lexicon-core-0.1.0.tar.gz.sha256
  ├── openword-lexicon-plus-0.1.0.tar.gz
  └── openword-lexicon-plus-0.1.0.tar.gz.sha256
```

---

## Data Structures

### Entry Schema (Normalized)

```json
{
  "word": "castle",
  "pos": ["noun", "verb"],
  "labels": {
    "register": [],
    "region": [],
    "temporal": [],
    "domain": []
  },
  "is_phrase": false,
  "lemma": null,
  "concreteness": "mixed",
  "frequency_tier": "top10k",
  "sources": ["eowl", "wikt", "wordnet"]
}
```

### MARISA Trie

**Why MARISA?**
- **Space-efficient**: Orders of magnitude smaller than hash tables
- **Fast**: O(|word|) lookups, excellent cache locality
- **Persistent**: Mmap-friendly, no deserialization overhead
- **Prefix-friendly**: Built-in prefix search

**Characteristics:**
- **Trie size**: ~510 KB for 208k words (~2.5 bytes/word)
- **Lookup speed**: Sub-microsecond for membership tests
- **Prefix search**: Returns all matches efficiently

**Alternative considered**: DAWG (Directed Acyclic Word Graph)
- Similar compression, but less mature Python bindings

### Metadata Sidecar (JSON)

**Why separate metadata?**
1. **Trie optimized for keys only**: Adding values inflates size
2. **Flexible metadata**: Can extend schema without trie rebuild
3. **Streaming-friendly**: Can process JSONL incrementally
4. **Indexed access**: O(1) lookup by trie-returned ID

**Format**: JSON array indexed by trie ID

```json
[
  {"word": "aa", "pos": ["noun"], ...},
  {"word": "aah", "pos": ["interjection"], ...},
  ...
]
```

**Trade-off**: Two-file system (trie + metadata) vs. single file
- **Chosen**: Two files (better for large-scale)
- **Alternative**: SQLite with indexed BLOB column (considered for v2.0)

---

## Design Decisions

### 1. Unicode NFKC Normalization

**Decision**: Use NFKC (Normalization Form KC) for all words.

**Rationale**:
- **Canonical representation**: Eliminates visual duplicates (é vs. é)
- **Compatibility**: Collapses ligatures, alternative forms
- **Deterministic**: Same string → same normalized form
- **Interoperability**: Matches most text processing pipelines

**Trade-off**: Loses distinction between stylistic variants
- Example: `ﬁ` (ligature) → `fi` (separate letters)

### 2. Controlled Vocabulary for Labels

**Decision**: Fixed enum values for all label categories.

**Rationale**:
- **Queryability**: Easy to filter by exact label
- **Consistency**: Prevents typos, variations
- **Documentation**: Clear taxonomy in `labels.md`

**Trade-off**: Less flexible than free-text tags
- Solution: Can extend enum in schema updates

### 3. Frequency Tiers (not exact ranks)

**Decision**: Coarse buckets (top10, top100, ..., rare) instead of exact ranks.

**Rationale**:
- **Stability**: Rank buckets change less than exact ranks
- **Sufficient**: Most applications need "common" vs. "rare", not rank #1234
- **Compact**: Single enum field vs. integer rank

**Trade-off**: Less granular than exact frequency counts
- Example: Can't distinguish rank #50 from rank #90 (both top100)

### 4. Two Distributions (Core vs. Plus)

**Decision**: Separate core (ultra-permissive) and plus (enhanced) distributions.

**Rationale**:
- **License choice**: Users can choose based on needs
- **Core**: Maximum permissiveness for commercial/proprietary use
- **Plus**: Maximum coverage for open-source projects

**Trade-off**: Duplication of core data in plus
- Mitigation: Plus tarball only ~100 KB larger (3 unique words)

### 5. Policy Filters (not pre-filtered distributions)

**Decision**: Ship full data, apply filters at query time or build time.

**Rationale**:
- **Transparency**: Users see what's filtered, can customize
- **Flexibility**: Different applications have different needs
- **Auditability**: Filter rules in code, not baked into data

**Trade-off**: Slightly larger distributions
- Mitigation: Provide pre-filtered views (family_friendly.jsonl)

### 6. MARISA Trie (not DAWG or plain hash)

**Decision**: Use MARISA trie for word storage.

**Rationale**:
- **Compact**: ~2.5 bytes/word (vs. 10-20 for hash tables)
- **Fast**: O(|word|) lookups with great cache locality
- **Prefix search**: Built-in, no separate index needed
- **Mature**: Stable Python bindings, well-tested

**Trade-off**: Immutable (requires rebuild for updates)
- Acceptable: Lexicon updates are infrequent (release-based)

### 7. JSONL for Intermediate, JSON Array for Final

**Decision**: Use JSONL for intermediate processing, JSON array for final metadata.

**Rationale**:
- **JSONL**: Streaming-friendly, append-only, easy to process line-by-line
- **JSON array**: Indexed access, faster bulk loading, compatible with jq

**Trade-off**: JSON array requires full parse
- Mitigation: For 200k entries, ~28 MB fits comfortably in RAM

---

## Performance Characteristics

### Build Time (Estimated)

| Phase | Time | Bottleneck |
|-------|------|------------|
| Fetch (core) | 10 s | Network I/O |
| Fetch (plus) | 5 min | Network I/O (Wiktionary dump) |
| Core ingest | 3 s | Parsing |
| WordNet enrich | 20 s | WordNet lookups |
| Frequency tiers | 2 s | File I/O |
| Merge | 5 s | File I/O |
| Trie build | 5 s | MARISA construction |
| **Total** | **<10 min** | (excluding large downloads) |

### Memory Usage

| Phase | Peak RAM | Notes |
|-------|----------|-------|
| Core ingest | 500 MB | Holds all entries in memory |
| WordNet enrich | 800 MB | NLTK WordNet data |
| Trie build | 400 MB | Temporary trie construction |
| **Max** | **<1 GB** | Well under 2 GB limit |

### Disk Usage

| Artifact | Size | Compressed |
|----------|------|------------|
| Raw sources (core) | 5 MB | 2 MB |
| Raw sources (plus) | 2.5 GB | 700 MB |
| Intermediate JSONL | 80 MB | 15 MB |
| Trie (core/plus) | 510 KB | 200 KB (gzip) |
| Metadata JSON | 28 MB | 1.2 MB (gzip) |
| **Total** | **<3 GB** | **<1 GB compressed** |

### Query Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Membership test | <1 μs | O(\|word\|), trie lookup |
| Prefix search (10 results) | <100 μs | Trie iteration |
| Metadata fetch | <1 μs | O(1) array index |
| Full scan (filter) | 50 ms | 200k entries, Python loop |

**Optimization**: For repeated queries, build in-memory index:

```python
word_index = {entry['word']: entry for entry in metadata}
# Now: O(1) lookups, ~50 MB RAM
```

---

## Future Improvements

### v1.1 (Next Minor Release)

- [ ] CLI implementation (`owlex` command)
- [ ] SQLite backend for metadata (faster indexed queries)
- [ ] IPA pronunciation (from Wiktionary)
- [ ] Comprehensive test suite

### v2.0 (Major Release)

- [ ] Sense-level data (multiple definitions per word)
- [ ] Lexical relations (synonyms, antonyms, hypernyms)
- [ ] Etymology information
- [ ] Multilingual support (beyond English)

### Performance Optimizations

- [ ] MessagePack for metadata (smaller, faster than JSON)
- [ ] Bloom filter for negative lookups (reject non-words instantly)
- [ ] LMDB for metadata (persistent key-value store)

---

## Alternatives Considered

### 1. SQLite for Everything

**Considered**: Store words and metadata in SQLite.

**Pros**: Single-file, indexed queries, well-tested

**Cons**: Larger than trie (~10x), no prefix search built-in

**Decision**: Use trie + JSON sidecar for compactness and prefix search

### 2. Pre-computed Filters

**Considered**: Ship multiple filtered distributions (family-friendly, academic, etc.).

**Pros**: No filtering needed at query time

**Cons**: Explosion of artifacts, less transparent, harder to customize

**Decision**: Ship full data + filter scripts

### 3. Exact Frequency Ranks

**Considered**: Store exact rank (1, 2, 3, ...) instead of tiers.

**Pros**: More granular

**Cons**: Less stable across frequency sources, larger storage

**Decision**: Use coarse tiers (sufficient for most use cases)

---

## See Also

- [SCHEMA.md](SCHEMA.md) — Entry schema reference
- [DATASETS.md](DATASETS.md) — Source datasets
- [USAGE.md](USAGE.md) — API and usage examples
- [README.md](../README.md) — Project overview
