# Building the Lexicon

How to build the OpenWord Lexicon from source.

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Pipeline scripts |
| uv | latest | Python package manager |
| Rust | latest | Wiktionary scanner (5-10x faster than Python) |
| pnpm | latest | Web tools (optional) |
| ~10 GB | disk | Source data + build artifacts |

### Install Prerequisites

```bash
# macOS
brew install uv
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Quick Build

```bash
# Clone repository
git clone https://github.com/macshonle/openword-lexicon.git
cd openword-lexicon

# Setup environment and build
make bootstrap
make build-en
```

Build takes ~10-15 minutes depending on your machine.

## Build Steps

The `make build-en` command runs these steps:

### 1. Fetch Source Data

```bash
make fetch-en
```

Downloads:
- Wiktionary dump (~2-3 GB compressed)
- EOWL word list (~1 MB)
- WordNet 2024 (~22 MB)
- Frequency data (~600 KB)
- Brysbaert concreteness ratings

### 2. Extract Wiktionary

```bash
# Automatic via make build-en, or manually:
./tools/wiktionary-scanner-rust/target/release/wiktionary-scanner-rust \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en-wikt.jsonl
```

The Rust scanner extracts English entries from the Wiktionary XML dump. Produces per-sense JSONL with POS, labels, syllables.

### 3. Sort and Normalize

```bash
uv run python src/openword/wikt_sort.py \
    --input data/intermediate/en-wikt.jsonl \
    --output data/intermediate/en-wikt-sorted.jsonl

uv run python src/openword/wikt_normalize.py \
    --input data/intermediate/en-wikt-sorted.jsonl \
    --lexemes-output data/intermediate/en-lexemes.jsonl \
    --senses-output data/intermediate/en-senses.jsonl
```

Splits into two-file format: word-level properties in lexemes, sense-level in senses.

### 4. Merge Additional Sources

```bash
uv run python src/openword/source_merge.py \
    --wikt-lexemes data/intermediate/en-lexemes.jsonl \
    --eowl data/raw/en/eowl.txt \
    --wordnet data/raw/en/english-wordnet-2024.tar.gz \
    --output data/intermediate/en-lexemes-merged.jsonl
```

Adds words from EOWL and WordNet with source tracking.

### 5. Enrich with Metadata

```bash
# Brysbaert concreteness ratings
uv run python src/openword/brysbaert_enrich.py \
    --input data/intermediate/en-lexemes-merged.jsonl \
    --output data/intermediate/en-lexemes-enriched.jsonl

# Frequency tiers
uv run python src/openword/frequency_tiers.py \
    --input data/intermediate/en-lexemes-enriched.jsonl \
    --output data/intermediate/en-lexemes-enriched.jsonl
```

### 6. Build Tries

```bash
# Full lexicon
uv run python src/openword/trie_build.py \
    --input data/intermediate/en-lexemes-enriched.jsonl \
    --profile full

# Game profile (pure a-z only)
uv run python src/openword/trie_build.py \
    --input data/intermediate/en-lexemes-enriched.jsonl \
    --profile game
```

### 7. Export Metadata Modules

```bash
uv run python src/openword/export_metadata.py \
    --input data/intermediate/en-lexemes-enriched.jsonl \
    --modules all --gzip
```

Creates separate gzipped JSON files for frequency, concreteness, syllables, sources.

## Pipeline Architecture

```
Wiktionary XML ──► Rust Scanner ──► en-wikt.jsonl (per-sense, unsorted)
                                          │
                                          ▼
                                    wikt_sort.py
                                          │
                                          ▼
                                   en-wikt-sorted.jsonl
                                          │
                                          ▼
                                   wikt_normalize.py
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
               en-lexemes.jsonl                     en-senses.jsonl
               (word-level)                         (sense-level)
                        │
                        ▼
EOWL + WordNet ──► source_merge.py ──► en-lexemes-merged.jsonl
                                              │
                                              ▼
Brysbaert ────────► brysbaert_enrich.py
                                              │
                                              ▼
Frequency data ───► frequency_tiers.py ──► en-lexemes-enriched.jsonl
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                     ▼                     ▼
                  trie_build.py        export_metadata.py    export_wordlist.py
                        │                     │                     │
                        ▼                     ▼                     ▼
                   en.trie              en-*.json.gz          en-wordlist.txt
                en-game.trie
```

## Output Files

After build, you'll find:

### data/build/

| File | Description |
|------|-------------|
| `en.trie` | Full MARISA trie (~4 MB) |
| `en-game.trie` | Game profile trie (~2.5 MB) |
| `en-wordlist.txt` | Plain text word list (~16 MB) |
| `en-frequency.json.gz` | Frequency tier mapping |
| `en-concreteness.json.gz` | Concreteness ratings |
| `en-syllables.json.gz` | Syllable counts |
| `en-sources.json.gz` | Source attributions |

### data/intermediate/

| File | Description |
|------|-------------|
| `en-lexemes-enriched.jsonl` | Full lexeme data (~300 MB) |
| `en-senses.jsonl` | Sense data (~70 MB) |
| `en-wikt.jsonl` | Raw Wiktionary extraction |
| `en-wikt-sorted.jsonl` | Sorted Wiktionary data |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make bootstrap` | Setup Python environment |
| `make fetch-en` | Download source data |
| `make build-en` | Full build pipeline |
| `make build-rust-scanner` | Build Rust Wiktionary scanner |
| `make build-trie` | Build browser binary trie |
| `make clean` | Remove build artifacts |
| `make validate-enable` | Validate against ENABLE wordlist |
| `make validate-profanity` | Check profanity labeling |

## Troubleshooting

### Rust scanner not building

```bash
# Ensure Rust is installed
rustc --version

# Build manually
cd tools/wiktionary-scanner-rust
cargo build --release
```

### Out of memory during build

The pipeline is designed to stay under 2 GB RAM. If you hit issues:

```bash
# Process in smaller batches (not usually needed)
# Or increase swap space
```

### Missing frequency data

```bash
# Re-fetch frequency file
bash scripts/fetch/fetch_frequency.sh
```

### Validation failures

```bash
# Check ENABLE coverage (optional validation)
make validate-enable

# Check profanity labeling
make validate-profanity
```

## Customizing the Build

### Add a New Source

1. Create fetch script in `scripts/fetch/`
2. Create ingest module in `src/openword/`
3. Update `source_merge.py` to include new source
4. Update `SOURCE_LICENSES` mapping

### Change Trie Profiles

Edit `src/openword/trie_build.py`:

```python
PROFILES = {
    'full': None,  # No filter
    'game': filter_game,  # Pure a-z
    # Add custom profiles here
}
```

### Modify Frequency Tiers

Edit `src/openword/frequency_tiers.py` to change the A-X tier boundaries (see `TIER_DEFINITIONS`).
