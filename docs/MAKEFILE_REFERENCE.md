# Makefile Command Reference

Quick reference for all Makefile targets in the openword-lexicon project.

---

## Analysis & Reporting Commands

### Comprehensive Analysis

| Command | Description | Runtime | Dependencies |
|---------|-------------|---------|--------------|
| `make analyze-all-reports` | Run ALL analysis and reports | ~10 min | Data + builds |
| `make analyze-enhanced-metadata` | Frequency, syllable, WordNet analysis | ~5 min | Raw data |
| `make analyze-game-metadata` | Game word filtering analysis | <1 min | Built lexicon |

### Individual Metadata Reports

| Command | Description | Runtime | Dependencies |
|---------|-------------|---------|--------------|
| `make report-frequency-analysis` | Analyze frequency tiers | <1 min | `en_50k.txt` |
| `make report-syllable-analysis` | Analyze syllable data in Wiktionary | ~2 min | Wiktionary dump |
| `make report-wordnet-concreteness` | Analyze WordNet categories | ~10 sec | NLTK (auto-downloads) |
| `make report-labels` | Analyze Wiktionary labels | ~3 min | Wiktionary JSONL |

### Standard Inspection Reports

| Command | Description | Runtime | Dependencies |
|---------|-------------|---------|--------------|
| `make reports` | Generate all inspection reports | ~2 min | Built lexicon |
| `make report-raw` | Inspect raw datasets | <1 min | Raw data |
| `make report-pipeline` | Inspect pipeline stages | <1 min | Built lexicon |
| `make report-trie` | Analyze trie structure | <1 min | Built lexicon |
| `make report-metadata` | Analyze metadata coverage | <1 min | Built lexicon |
| `make report-compare` | Compare core vs plus | <1 min | Both builds |

---

## Build Commands

### Environment Setup

| Command | Description |
|---------|-------------|
| `make bootstrap` | Set up development environment (venv + deps) |
| `make venv` | Create/refresh Python virtual environment |
| `make deps` | Install project dependencies |

### Data Fetching

| Command | Description | Download Size |
|---------|-------------|---------------|
| `make fetch` | Fetch all data (core + plus) | ~3-4 GB |
| `make fetch-core` | Fetch core sources (ENABLE, EOWL) | ~5 MB |
| `make fetch-plus` | Fetch plus sources (Wiktionary, WordNet, frequency) | ~3-4 GB |

### Building Distributions

| Command | Description | Runtime |
|---------|-------------|---------|
| `make build-core` | Build core distribution | ~5-10 min |
| `make build-plus` | Build plus distribution | ~30-60 min |
| `make build-wiktionary-json` | Extract Wiktionary to JSONL | ~30-60 min |

### Packaging

| Command | Description |
|---------|-------------|
| `make package` | Create release tarballs with SHA256 checksums |
| `make export-wordlist` | Export trie to plain text wordlist |

---

## Word Filtering Commands

### Game Words

| Command | Description | Output |
|---------|-------------|--------|
| `make game-words` | Generate scored game word lists | `data/game_words/` |

### Specialized Lists

| Command | Description | Output File |
|---------|-------------|-------------|
| `make build-wordlists` | Build all specialized lists | Multiple in `data/wordlists/` |
| `make export-wordlist-game` | Export game-appropriate words | TBD |
| `make export-wordlist-vulgar-blocklist` | Export profanity blocklist | TBD |
| `make export-wordlist-kids-nouns` | Export kids-appropriate nouns | TBD |
| `make export-wordlist-phrases` | Export multi-word phrases | TBD |

### Phrase Filtering

| Command | Description |
|---------|-------------|
| `make export-wordlist-filtered-w3` | Filter: max 3 words |
| `make export-wordlist-filtered-w4` | Filter: max 4 words |
| `make export-wordlist-filtered-c50` | Filter: max 50 characters |
| `make export-wordlist-filtered-w3c50` | Filter: max 3 words AND 50 chars |

---

## Development Commands

### Code Quality

| Command | Description |
|---------|-------------|
| `make fmt` | Format code with Black |
| `make lint` | Lint code with Ruff |
| `make test` | Run tests (placeholder) |

### Cleanup

| Command | Description |
|---------|-------------|
| `make clean` | Remove Python cache files |
| `make clean-build` | Remove built artifacts |
| `make clean-viewer` | Remove viewer build artifacts |
| `make scrub` | Remove all generated files (except raw data) |

### Utilities

| Command | Description |
|---------|-------------|
| `make check-limits` | Check disk/RAM usage |
| `make start-server` | Start web viewer on http://localhost:8080 |
| `make build-binary` | Build compressed binary trie for web viewer |

---

## Local Analysis Commands

### Wiktionary Analysis

| Command | Description | Runtime |
|---------|-------------|---------|
| `make analyze-local` | Extract Wiktionary + generate label stats | ~30-60 min |
| `make baseline-decompress` | Benchmark BZ2 decompression | ~1 min |

### Scanner Diagnostics

| Command | Description |
|---------|-------------|
| `make diagnose-scanner` | Run scanner in diagnostic mode |
| `make scanner-commit` | Commit scanner refactoring changes |
| `make scanner-push` | Push scanner changes to remote |

---

## Common Workflows

### Quick Start
```bash
make bootstrap          # Set up environment
make fetch-core         # Download core data (5 MB)
make build-core         # Build core distribution (~5 min)
make reports            # Generate inspection reports
```

### Complete Build
```bash
make bootstrap          # Set up environment
make fetch-plus         # Download all data (~3-4 GB)
make build-plus         # Build plus distribution (~60 min)
make analyze-all-reports  # Generate all reports (~10 min)
```

### Analysis Only (No Build)
```bash
make fetch-plus         # Get raw data
make analyze-enhanced-metadata  # Analyze what's available (~5 min)
```

### Generate Game Words
```bash
make build-core         # Build lexicon first
make game-words         # Generate filtered lists (<1 min)
cat data/game_words/review_core.md  # Review candidates
```

### Custom Wordlist Export
```bash
make build-plus
make export-wordlist-filtered-w3c50  # Short phrases only
ls -lh data/build/plus/wordlist-w3-c50.txt
```

---

## Output Locations

### Reports
```
reports/
├── frequency_analysis.md
├── syllable_analysis.md
├── wordnet_concreteness.md
├── label_statistics.md
├── label_examples.json
├── game_metadata_analysis_core.md
├── game_metadata_analysis_plus.md
├── trie_inspection_core.md
├── trie_inspection_plus.md
├── metadata_exploration_core.md
├── metadata_exploration_plus.md
├── pipeline_inspection_core.md
├── pipeline_inspection_plus.md
├── raw_data_inspection.md
└── distribution_comparison.md
```

### Data Artifacts
```
data/
├── raw/
│   ├── core/         # ENABLE, EOWL
│   └── plus/         # Wiktionary, WordNet, frequency
├── intermediate/     # Pipeline stages (JSONL)
├── filtered/         # Policy-filtered views
├── build/            # Final artifacts
│   ├── core/         # core.trie, core.meta.json, wordlist.txt
│   └── plus/         # plus.trie, plus.meta.json, wordlist.txt
├── wordlists/        # Specialized filtered lists
├── game_words/       # Game word filtering outputs
└── artifacts/
    └── releases/     # Packaged releases (tar.gz)
```

---

## Dependency Chains

### For Enhanced Metadata Analysis
```
fetch-plus → analyze-enhanced-metadata
  ├── en_50k.txt → report-frequency-analysis
  ├── wiktionary dump → report-syllable-analysis
  └── (NLTK auto-downloads) → report-wordnet-concreteness
```

### For Standard Reports
```
fetch → build → reports
  ├── build-core → report-trie (core)
  └── build-plus → report-trie (plus)
```

### For Game Word Filtering
```
fetch → build → game-words
  └── core.meta.json → filter_game_words.py
```

### For Label Analysis
```
fetch-plus → build-wiktionary-json → report-labels
  └── wikt.jsonl → report_label_statistics.py
```

---

## Pro Tips

### Speed Up Repeated Builds
```bash
# Only rebuild if sources changed (Make handles this)
make build-core  # Fast if nothing changed
```

### Generate Reports Without Full Build
```bash
# Some reports don't need full builds
make fetch-plus
make analyze-enhanced-metadata  # Works without building
```

### Check What Will Run
```bash
# Dry-run mode
make -n analyze-all-reports
```

### Run Targets in Parallel (Use Carefully)
```bash
# Only for independent targets
make report-frequency-analysis & \
make report-wordnet-concreteness &
wait
```

### Skip Dependency Checks
```bash
# Force regeneration
rm reports/wordnet_concreteness.md
make report-wordnet-concreteness
```

---

## See Also

- **[ANALYSIS_WORKFLOW.md](ANALYSIS_WORKFLOW.md)** - Detailed analysis workflow guide
- **[USAGE.md](USAGE.md)** - General CLI usage
- **[FILTERING.md](FILTERING.md)** - Query filtering documentation
- **[LOCAL_ANALYSIS.md](LOCAL_ANALYSIS.md)** - Local analysis setup

---

**Quick Help**: Run `make` (no arguments) to see available targets
