# Openword Lexicon

Permissively usable English lexicon for any application (games, NLP, education). Two distributions and a fast trie enable configurable, high‑quality word lists with rich labels and frequency tiers.

## Distributions
- **core** — ultra‑permissive sources only (data: CC0 or CC BY 4.0)
- **plus** — enhanced coverage/labels incl. CC‑BY‑SA inputs (data: CC BY‑SA 4.0)  
**Code:** Apache‑2.0

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

# Build core distribution (permissive sources only)
make fetch-core

# Note: uv will download wikitextprocessor directly from GitHub to pick up the latest Scribunto fixes.

# Build plus distribution inputs (optional; includes Wiktionary extraction)
make fetch-plus
make fetch-post-process-plus  # runs wiktextract → data/intermediate/plus/wikt.jsonl

uv run python src/openword/core_ingest.py
uv run python src/openword/wordnet_enrich.py
uv run python src/openword/frequency_tiers.py
uv run python src/openword/merge_dedupe.py
uv run python src/openword/policy.py
uv run python src/openword/trie_build.py

# Package release
uv run python src/openword/package_release.py

# Result: data/artifacts/releases/openword-lexicon-core-0.1.0.tar.gz
```

> **Building PLUS:** Run `make fetch-plus && make fetch-post-process-plus`, then include `uv run python src/openword/wikt_ingest.py` before `wordnet_enrich.py` (or run `make build-plus` to automate the entire sequence).

## High‑level pipeline
1. **Fetch** sources (core | plus) with checksums & provenance.
2. **Normalize** entries to JSONL (schema, NFKC, controlled labels).
3. **Enrich** with WordNet (concreteness/POS); **Tier** by frequency.
4. **Merge & deduplicate** per distribution.
5. **Policy filters** (e.g., family‑friendly) for curated views.
6. **Trie build** (compressed radix/DAWG) + sidecar metadata.
7. **CLI & releases** (artifacts + ATTRIBUTION + data LICENSE).

## Primary artifacts
- `core.trie` / `plus.trie` and `*.meta.db`
- `entries_merged.jsonl` (intermediate)
- `ATTRIBUTION.md`, `data/LICENSE`
- Release archives: `*-core-<ver>.tar.zst` / `*-plus-<ver>.tar.zst`

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
- CLI implementation (`owlex` command)
- Comprehensive test suite
- Performance benchmarks

## Documentation

- [USAGE.md](docs/USAGE.md) — CLI usage and examples
- [SCHEMA.md](docs/SCHEMA.md) — Entry schema reference
- [DATASETS.md](docs/DATASETS.md) — Source dataset details
- [DESIGN.md](docs/DESIGN.md) — Architecture and design decisions
- [ATTRIBUTION.md](ATTRIBUTION.md) — Full source attributions

## Statistics

| Distribution | Words | Trie Size | License |
|--------------|-------|-----------|---------|
| Core | 208,201 | 510 KB | CC BY 4.0 |
| Plus | 1,039,950 | 2.9 MB | CC BY-SA 4.0 |

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon) for guidelines.

## License

- **Code**: Apache-2.0
- **Core Data**: CC BY 4.0
- **Plus Data**: CC BY-SA 4.0

See [LICENSE](LICENSE) for code terms. Data licensing details are in ATTRIBUTION.md (generated during builds).
