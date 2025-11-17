# Openword Lexicon

Permissively usable English lexicon for any application (games, NLP, education). Unified build integrates all sources (ENABLE, EOWL, Wiktionary, WordNet) with per-source licensing tracking, enabling flexible runtime filtering for your specific use case.

## Approach

**Unified English Build**: Single comprehensive dataset with all sources integrated. Filter at runtime based on your needs (child-safety, region, license requirements, etc.).

**License Tracking**: Every entry includes `license_sources` mapping, so you know exactly which licenses apply to each word.

**Language-Based Organization**: Architecture supports future expansion to other languages while maintaining clean separation.

**Code License:** Apache-2.0

## Constraints
- Total downloads ≤ **100 GB**
- Peak RAM per step ≤ **2 GB**

## Quickstart

### Using Pre-built Releases

Download and extract a release:

```bash
# Download latest release
wget https://github.com/macshonle/openword-lexicon/releases/latest/download/openword-lexicon-core-0.1.0.tar.gz

# Extract
tar xzf openword-lexicon-core-0.1.0.tar.gz
cd openword-lexicon-core-0.1.0

# Verify (optional)
sha256sum -c *.sha256

# Use in Python
python3 -m pip install marisa-trie
python3
>>> import marisa_trie, json
>>> trie = marisa_trie.Trie()
>>> trie.load('core.trie')
>>> 'castle' in trie
True
>>> len(trie)
208201
```

### Building from Source (uv)

```bash
# Install uv (one time)
brew install uv  # macOS
# or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/macshonle/openword-lexicon.git
cd openword-lexicon

# Bootstrap environment
make bootstrap

# Build English lexicon
make build-en

# Result: data/build/en/en.trie + en.meta.json
```

**Pipeline Steps (automated by `make build-en`):**
1. **Fetch** English sources (ENABLE, EOWL, Wiktionary, WordNet, frequency data)
2. **Ingest** source data to normalized JSONL
3. **Merge** all entries with license tracking
4. **Enrich** with WordNet (concreteness, POS tags for ALL entries)
5. **Tier** by frequency (10 granular tiers)
6. **Build** trie + metadata sidecar

## High-level pipeline
1. **Fetch** English sources with checksums & provenance
2. **Normalize** entries to JSONL (schema, NFKC, controlled labels)
3. **Merge** all sources with license tracking
4. **Enrich** with WordNet (concreteness/POS for ALL entries)
5. **Tier** by frequency (10 granular tiers)
6. **Build** trie (compressed MARISA) + metadata sidecar
7. **Filter** at runtime using `filters.py` (child-safe, region, license, etc.)

## Primary artifacts
- `en.trie` + `en.meta.json` (English lexicon)
- `entries_tiered.jsonl` (intermediate with all metadata)
- `ATTRIBUTION.md` (generated per build)

## Interactive Word List Builder

Create custom filtered word lists using the web interface:

```bash
# Open web-based builder
make wordlist-builder-web
```

The builder creates JSON specifications that describe filtering criteria:

```bash
# Generate word list from specification
make owlex-filter SPEC=wordlist-spec.json > words.txt

# With verbose output for debugging
uv run python -m openword.owlex wordlist-spec.json --verbose --output words.txt
```

### Available Filters

- **Character**: Length, patterns, regex (100% coverage)
- **Frequency**: 6 tiers from top10 to rare (100% coverage)
- **Part-of-speech**: noun, verb, adjective, etc. (~52.5% coverage)
- **Concreteness**: concrete/abstract/mixed nouns (~34.5% core, ~8.8% plus)
- **Labels** (Plus only): register, domain, temporal, region (~3-11% coverage)
- **Policy**: family-friendly, modern-only, no-jargon shortcuts

### Example Specifications

Pre-built examples in `examples/wordlist-specs/`:

- `wordle.json` - 5-letter common words
- `kids-nouns.json` - Concrete nouns for children
- `scrabble.json` - Single words for Scrabble
- `profanity-blocklist.json` - Flagged inappropriate words

See `tools/wordlist-builder/README.md` for complete documentation.

## Status

✅ **Core Pipeline Complete**
- Repository scaffolding and guardrails
- Source fetching with provenance tracking
- Normalization, ingest, enrichment, and merge
- Policy filters, attribution, and trie build
- CI/CD, packaging, releases, and documentation

🚧 **TODO**
- Comprehensive test suite
- Performance benchmarks

See [docs/planned/](docs/planned/) for future feature plans.

## Documentation

- [USAGE.md](docs/USAGE.md) — Python API usage and examples
- [SCHEMA.md](docs/SCHEMA.md) — Entry schema reference
- [DATASETS.md](docs/DATASETS.md) — Source dataset details
- [DESIGN.md](docs/DESIGN.md) — Architecture and design decisions
- [ATTRIBUTION.md](ATTRIBUTION.md) — Full source attributions (generated during builds)

## Statistics

| Language | Words | Trie Size | License Model |
|----------|-------|-----------|---------------|
| **English** | ~1.3M | ~3 MB | Per-word tracking via `license_sources` |

**Metadata Coverage** (English):
- WordNet enrichment on ALL entries (not just permissive sources)
- 4x better concreteness coverage vs separate pipelines
- Safe defaults for child-appropriate filtering
- Runtime license filtering (filter to CC0+UKACD for permissive-only)
- Syllable data from Wiktionary hyphenation (~30-50% coverage)

## Contributing

Contributions welcome! Please open an issue or pull request to discuss proposed changes.

## License

- **Code**: Apache-2.0
- **Data**: Per-word license tracking via `license_sources` field
  - ENABLE: CC0 (Public Domain)
  - EOWL: UKACD (Permissive)
  - Wiktionary: CC BY-SA 4.0
  - WordNet: WordNet License
  - Frequency data: CC BY 4.0

See [LICENSE](LICENSE) for code terms. Data licensing details in ATTRIBUTION.md (generated during builds).
