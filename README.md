# Openword Lexicon

Permissively usable English lexicon for any application (games, NLP, education). A unified build integrates all sources (ENABLE, EOWL, Wiktionary, WordNet) with per-source licensing tracking, enabling flexible runtime filtering for your specific use case.

## Approach

**Unified Build** (recommended): Single comprehensive dataset with all sources integrated. Filter at runtime based on your needs (child-safety, region, license requirements, etc.).

**Legacy Distributions** (deprecated): Separate Core (permissive-only) and Plus (comprehensive) builds. Use unified build for new projects.

**License Tracking**: Every entry includes `license_sources` mapping, so you know exactly which licenses apply to each word.

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

# Unified build (recommended - integrates all sources)
make build-unified

# Result: data/build/unified/unified.trie + unified.meta.json
```

**Pipeline Steps (automated by `make build-unified`):**
1. **Ingest** sources (ENABLE, EOWL, Wiktionary)
2. **Merge** all entries with license tracking
3. **Enrich** with WordNet (concreteness, POS tags)
4. **Tier** by frequency (10 granular tiers)
5. **Build** trie + metadata sidecar

**Legacy builds** (deprecated):
```bash
make build-core   # Permissive sources only
make build-plus   # All sources (old approach)
```

## High-level pipeline (Unified Build)
1. **Fetch** sources (ENABLE, EOWL, Wiktionary) with checksums & provenance
2. **Normalize** entries to JSONL (schema, NFKC, controlled labels)
3. **Merge** all sources with license tracking
4. **Enrich** with WordNet (concreteness/POS for ALL entries)
5. **Tier** by frequency (10 granular tiers)
6. **Build** trie (compressed MARISA) + metadata sidecar
7. **Filter** at runtime using `filters.py` (child-safe, region, license, etc.)

## Primary artifacts
- `unified.trie` + `unified.meta.json` (unified build)
- `entries_tiered.jsonl` (intermediate with all metadata)
- `ATTRIBUTION.md` (generated per build)
- Legacy: `core.trie`, `plus.trie` (deprecated)

## Interactive Word List Builder

Create custom filtered word lists using the interactive CLI or web interface:

```bash
# Install builder dependencies (optional, for enhanced UI)
make wordlist-builder-install  # Uses pnpm

# Launch interactive CLI builder
make wordlist-builder-cli

# Or use web interface
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

| Build | Words | Trie Size | License Model |
|-------|-------|-----------|---------------|
| **Unified** | ~1.3M | ~3 MB | Per-word tracking via `license_sources` |
| Core (legacy) | 208K | 510 KB | CC BY 4.0 |
| Plus (legacy) | 1.0M | 2.9 MB | CC BY-SA 4.0 |

**New in Unified**:
- WordNet enrichment on ALL entries (not just Core) → 4x better concreteness coverage
- Safe defaults for child-appropriate filtering
- Runtime license filtering (filter to CC0+UKACD if you want permissive-only)
- Better integration between sources

## Contributing

Contributions welcome! Please open an issue or pull request to discuss proposed changes.

## License

- **Code**: Apache-2.0
- **Core Data**: CC BY 4.0
- **Plus Data**: CC BY-SA 4.0

See [LICENSE](LICENSE) for code terms. Data licensing details are in ATTRIBUTION.md (generated during builds).
