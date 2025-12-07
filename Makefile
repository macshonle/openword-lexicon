# Makefile (root) - uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11
LEXICON_LANG ?= en

# Directory structure (flat with language-prefixed files)
RAW_DIR := data/raw/$(LEXICON_LANG)
INTERMEDIATE_DIR := data/intermediate
BUILD_DIR := data/build
REPORTS_DIR := reports

# Build artifacts (language-prefixed filenames in flat directories)
WIKT_DUMP := $(RAW_DIR)/$(LEXICON_LANG)wiktionary-latest-pages-articles.xml.bz2
WIKT_JSON_PARENT :=$(INTERMEDIATE_DIR)
WIKT_JSON := $(WIKT_JSON_PARENT)/$(LEXICON_LANG)-wikt.jsonl
WIKT_JSON_SORTED := $(WIKT_JSON_PARENT)/$(LEXICON_LANG)-wikt-sorted.jsonl
FREQUENCY_DATA := $(RAW_DIR)/$(LEXICON_LANG)_50k.txt
WORDNET_ARCHIVE := $(RAW_DIR)/english-wordnet-2024.tar.gz
UNIFIED_TRIE := $(BUILD_DIR)/$(LEXICON_LANG).trie
GAME_TRIE := $(BUILD_DIR)/$(LEXICON_LANG)-game.trie
UNIFIED_META := $(BUILD_DIR)/$(LEXICON_LANG).meta.json
WORDLIST_TXT := $(BUILD_DIR)/$(LEXICON_LANG)-wordlist.txt

# Wiktionary pipeline outputs (two-file normalized format)
LEXEMES_JSON := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-lexemes.jsonl
SENSES_JSON := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-senses.jsonl
LEXEMES_MERGED := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-lexemes-merged.jsonl
LEXEMES_ENRICHED := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-lexemes-enriched.jsonl

# Additional source files
EOWL_FILE := $(RAW_DIR)/eowl.txt

# Rust tools
RUST_RELEASE_DIR := tools/wiktionary-scanner-rust/target/release
RUST_SCANNER := $(RUST_RELEASE_DIR)/wiktionary-scanner-rust

# Python scripts (src/openword/)
RUN_PYTHON := $(UV) run python
SOURCE_MERGE := $(RUN_PYTHON) src/openword/source_merge.py
BRYSBAERT_ENRICH := $(RUN_PYTHON) src/openword/brysbaert_enrich.py
FREQUENCY_TIERS := $(RUN_PYTHON) src/openword/frequency_tiers.py
TRIE_BUILD := $(RUN_PYTHON) src/openword/trie_build.py
EXPORT_METADATA := $(RUN_PYTHON) src/openword/export_metadata.py
EXPORT_LEMMA_GROUPS := $(RUN_PYTHON) src/openword/export_lemma_groups.py
EXPORT_WORDLIST := $(RUN_PYTHON) src/openword/export_wordlist.py
GENERATE_STATISTICS := $(RUN_PYTHON) src/openword/generate_statistics.py
WIKT_SORT := $(RUN_PYTHON) src/openword/wikt_sort.py
WIKT_NORMALIZE := $(RUN_PYTHON) src/openword/wikt_normalize.py
PACKAGE_RELEASE := $(RUN_PYTHON) src/openword/package_release.py

# Python scripts (tools/)
# Use -m to run as module so relative imports work properly
PYTHON_SCANNER := PYTHONPATH=tools $(RUN_PYTHON) -m wiktionary_scanner_python.scanner
COLLECT_POS := $(RUN_PYTHON) tools/collect_pos.py
UPDATE_CORPUS_DOC := $(RUN_PYTHON) tools/update_corpus_doc.py
GENERATE_REPORTS := $(RUN_PYTHON) tools/generate_reports.py
VALIDATE_ENABLE := $(RUN_PYTHON) tools/validate_enable_coverage.py
VALIDATE_PROFANITY := $(RUN_PYTHON) tools/validate_profanity_coverage.py
VALIDATE_CHILDISH := $(RUN_PYTHON) tools/validate_childish_terms.py
VALIDATE_PARITY := $(RUN_PYTHON) tools/wiktionary-scanner-rust/scripts/validate_parity.py
RUN_BENCHMARK := $(RUN_PYTHON) tools/wiktionary-scanner-rust/scripts/run_full_benchmark.py

# Benchmark outputs
BENCHMARK_DIR := data/benchmark

.PHONY: bootstrap venv deps fmt lint test test-python test-rust test-js test-full \
		clean scrub clean-fetched fetch-en \
        build-en build-rust-scanner build-trie build-metadata \
		package report-en diagnose-scanner corpus-stats \
		validate-all validate-enable validate-profanity validate-childish \
		validate-scanner-parity validate-scanner-parity-full \
        spec-editor-web wordlist-viewer-web \
		wordlists \
		benchmark-rust-scanner benchmark-validate \
		nightly weekly

# ===========================
# Development Environment
# ===========================

# Bootstrap local dev environment (idempotent)
bootstrap: venv deps

# Create/refresh project venv
venv:
	$(UV) venv --python $(PY_VERSION)
	@$(RUN_PYTHON) -c "import sys; print('Python', sys.version)"

# Install dependencies
deps:
	$(UV) pip install -e .
	$(UV) pip install -e .[dev]

# Code quality
fmt:
	$(UV) run black .

lint:
	$(UV) run ruff check .

# Run all tests (Python + Rust + JavaScript unit tests)
# For full parity validation, use: make test-full
test: test-python test-rust test-js

# Python unit tests only
test-python:
	@echo "Running Python tests..."
	$(UV) run pytest

# Rust unit tests only (requires cargo)
test-rust: | check-cargo
	@echo "Running Rust tests..."
	(cd tools/wiktionary-scanner-rust; cargo test)

# JavaScript/TypeScript unit tests (wordlist-viewer)
test-js: tools/wordlist-viewer/node_modules | check-pnpm
	@echo "Running JavaScript tests..."
	(cd tools/wordlist-viewer; pnpm test)

# Full test suite including scanner parity validation
# Requires Wiktionary dump to be present
test-full: test validate-scanner-parity

# ===========================
# Data Fetching
# ===========================

# Fetch all English language sources
fetch-en:
	$(UV) run scripts/fetch/fetch_sources.py

# ===========================
# Frontend Dependencies
# ===========================

.PHONY: check-pnpm
check-pnpm:
	@command -v pnpm >/dev/null 2>&1 || { \
		echo "Error: pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	}

# Install dependencies when package.json changes
%/node_modules: %/package.json | check-pnpm
	@echo "Installing dependencies in $*..."
	(cd $*; pnpm install)
	@touch $@

# ===========================
# Rust Tools
# ===========================

.PHONY: check-cargo
check-cargo:
	@command -v cargo >/dev/null 2>&1 || { \
		echo "Error: cargo not found. Install Rust from: https://rustup.rs/"; \
		exit 1; \
	}

# Build Rust-based Wiktionary scanner
# This is a high-performance replacement for tools/wiktionary-scanner-python/scanner.py
# The Rust version is faster (typically 4-5x) and produces identical output.
# Binary output: tools/wiktionary-scanner-rust/target/release/wiktionary-scanner-rust
$(RUST_SCANNER): tools/wiktionary-scanner-rust/Cargo.toml tools/wiktionary-scanner-rust/src/main.rs | check-cargo
	@echo "Building Rust scanner (release mode)..."
	(cd tools/wiktionary-scanner-rust; cargo build --release)

# Convenience target for building Rust scanner
build-rust-scanner: $(RUST_SCANNER)

# ===========================
# Build Pipeline
# ===========================

# Build English lexicon (two-file pipeline with multi-source support)
# Pipeline order:
#   0. Extract Wiktionary to wikt.jsonl (per-sense, unsorted)
#   1. Sort entries by word (creates wikt-sorted.jsonl)
#   2. Normalize into lexeme + senses tables (wikt_normalize.py)
#   3. Merge additional sources (EOWL, WordNet) into lexeme file
#   4. Enrich lexeme file (concreteness, frequency)
#   5. Build tries (full + game profile)
#   6. Generate statistics
build-en: fetch-en $(LEXEMES_JSON) $(SENSES_JSON)
	@echo "Merging sources (EOWL, WordNet)..."
	$(SOURCE_MERGE) \
		--wikt-lexemes $(LEXEMES_JSON) \
		--eowl $(EOWL_FILE) \
		--wordnet $(WORDNET_ARCHIVE) \
		--output $(LEXEMES_MERGED)
	@echo "Enriching lexemes file..."
	$(BRYSBAERT_ENRICH) --input $(LEXEMES_MERGED) --output $(LEXEMES_ENRICHED)
	$(FREQUENCY_TIERS) --input $(LEXEMES_ENRICHED) --output $(LEXEMES_ENRICHED)
	@echo "Building tries..."
	$(TRIE_BUILD) --input $(LEXEMES_ENRICHED) --profile full
	$(TRIE_BUILD) --input $(LEXEMES_ENRICHED) --profile game
	@echo "Exporting metadata modules..."
	$(EXPORT_METADATA) --input $(LEXEMES_ENRICHED) --modules all --gzip
	@echo "Exporting lemma metadata..."
	$(EXPORT_LEMMA_GROUPS) --senses $(SENSES_JSON) --gzip
	$(GENERATE_STATISTICS)

$(WIKT_JSON_PARENT):
	@mkdir -p "$(WIKT_JSON_PARENT)"

.PHONY: build-wikt-json
build-wikt-json: $(WIKT_JSON_SORTED)

# Build and sort Wiktionary JSONL using Rust scanner
# 1. Extract from XML dump to unsorted JSONL (kept for traceability)
# 2. Sort lexicographically by word (ensures duplicate entries are consecutive,
#    trie ordinal = line number, matches Python's default lexicographic sort)
# Default: channel-pipeline strategy with 4 threads (1.32x faster than sequential)
$(WIKT_JSON_SORTED): $(WIKT_DUMP) $(RUST_SCANNER) | $(WIKT_JSON_PARENT)
	@echo "Extracting Wiktionary (using Rust scanner)..."
	$(RUST_SCANNER) "$(WIKT_DUMP)" "$(WIKT_JSON)"
	@echo "Sorting Wiktionary entries by word..."
	$(WIKT_SORT) --input $(WIKT_JSON) --output $(WIKT_JSON_SORTED)

# Normalize into two-file format: lexemes + senses
# This step:
#   1. Groups entries by word
#   2. Extracts word-level properties into lexeme entries
#   3. Deduplicates senses by projection (pos, tags, flags)
#   4. Writes offset/length linking between files
$(LEXEMES_JSON) $(SENSES_JSON): $(WIKT_JSON_SORTED)
	@echo "Normalizing Wiktionary into lexemes + senses tables..."
	$(WIKT_NORMALIZE) \
		--input $(WIKT_JSON_SORTED) \
		--lexemes-output $(LEXEMES_JSON) \
		--senses-output $(SENSES_JSON) \
		-v

# Build compact trie for browser visualization (DAWG v4 format with varint deltas)
build-trie: $(WORDLIST_TXT) tools/wordlist-viewer/node_modules | check-pnpm
	(cd tools/wordlist-viewer; pnpm run build-trie --format=v4 ../../$(WORDLIST_TXT) data/$(LEXICON_LANG).trie.bin)

# Export modular metadata layers (frequency, concreteness, syllables, sources)
# Creates gzipped JSON files in data/build/{lang}-{module}.json.gz
build-metadata: $(LEXEMES_ENRICHED)
	@echo "Exporting metadata modules (gzipped)..."
	$(EXPORT_METADATA) --input $(LEXEMES_ENRICHED) --modules all --gzip

# Export trie to plain text wordlist
$(WORDLIST_TXT): $(UNIFIED_TRIE)
	$(EXPORT_WORDLIST)

# Package release artifacts
package:
	$(PACKAGE_RELEASE)

# ===========================
# Cleanup
# ===========================

clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +
	rm -rf data/intermediate data/filtered data/build data/artifacts
	rm -rf tools/wordlist-viewer/node_modules tools/wordlist-viewer/pnpm-lock.yaml tools/wordlist-viewer/data tools/wordlist-viewer/dist
	@if [ -d tools/wiktionary-scanner-rust/target ]; then \
		echo "Cleaning Rust build artifacts..."; \
		(cd tools/wiktionary-scanner-rust; cargo clean); \
	fi

# Clean fetched source data (for testing fetch_sources.py)
clean-fetched:
	@echo "Removing fetched source files..."
	rm -rf $(RAW_DIR)
	rm -rf data/raw/validation
	@echo "Done. Run 'make fetch-en' to re-download."

scrub: clean clean-fetched
	rm -rf .venv
	rm -rf $(BENCHMARK_DIR)

# ===========================
# Corpus Analysis
# ===========================

# Intermediate file for corpus stats
CORPUS_STATS_FILE := /tmp/corpus-stats.tsv
CORPUS_DOC := docs/WIKTIONARY-CORPUS.md

# Generate Wiktionary corpus statistics
# Updates docs/WIKTIONARY-CORPUS.md with current POS distribution
corpus-stats: $(WIKT_DUMP)
	$(COLLECT_POS) "$(WIKT_DUMP)" --stats-output "$(CORPUS_STATS_FILE)"
	$(UPDATE_CORPUS_DOC) "$(CORPUS_STATS_FILE)" "$(CORPUS_DOC)"
	@echo "Done! Review changes with: git diff $(CORPUS_DOC)"

# ===========================
# Reports & Validation
# ===========================

# Generate comprehensive analysis reports for English
report-en: deps
	@echo "Generating English Lexicon Reports..."
	$(GENERATE_REPORTS)
	@ls -lh $(REPORTS_DIR)/*.md 2>/dev/null || true

# Run all validation checks
validate-all: validate-enable validate-profanity validate-childish

# Validate lexicon coverage against ENABLE word list
validate-enable: deps
	@echo "Validating against ENABLE word list..."
	@bash scripts/fetch/fetch_enable.sh || echo "Warning: ENABLE fetch failed (GitHub CDN issue?)"
	@if [ -f data/raw/en/enable1.txt ]; then \
		echo "Running validation..."; \
		$(VALIDATE_ENABLE); \
	else \
		echo "Error: ENABLE not available for validation."; \
		echo "This is expected if GitHub CDN is having issues."; \
		exit 1; \
	fi

# Validate profanity/offensive term labeling
# WARNING: Downloads and analyzes lists with explicit/offensive content
validate-profanity: deps
	@$(UV) run scripts/fetch/fetch_sources.py --group profanity
	@$(VALIDATE_PROFANITY)

# Validate childish term labeling
validate-childish: deps
	@$(VALIDATE_CHILDISH)

# Validate Python/Rust scanner parity (quick - for nightly)
# Runs both scanners on 200k entries and compares outputs word-by-word
# Note: Uses sequential mode with --limit for efficient early termination
validate-scanner-parity: $(WIKT_DUMP) $(RUST_SCANNER) deps
	@echo "Running Python scanner (200000 entries)..."
	$(PYTHON_SCANNER) "$(WIKT_DUMP)" /tmp/parity-python.jsonl --limit 200000
	@echo "Running Rust scanner (200000 entries)..."
	$(RUST_SCANNER) "$(WIKT_DUMP)" /tmp/parity-rust.jsonl \
		--strategy sequential --limit 200000
	@echo "Validating parity..."
	$(VALIDATE_PARITY) \
		--python-output /tmp/parity-python.jsonl \
		--rust-output /tmp/parity-rust.jsonl

# Validate Python/Rust scanner parity (full - for weekly)
# Runs both scanners on ALL entries - slower but catches edge cases
# Note: Uses channel-pipeline for Rust (faster), sequential not needed without limit
validate-scanner-parity-full: $(WIKT_DUMP) $(RUST_SCANNER) deps
	@echo "Running Python scanner (full corpus)..."
	$(PYTHON_SCANNER) "$(WIKT_DUMP)" /tmp/parity-python-full.jsonl
	@echo "Running Rust scanner (full corpus)..."
	$(RUST_SCANNER) "$(WIKT_DUMP)" /tmp/parity-rust-full.jsonl
	@echo "Validating full parity..."
	$(VALIDATE_PARITY) \
		--python-output /tmp/parity-python-full.jsonl \
		--rust-output /tmp/parity-rust-full.jsonl

# ===========================
# Diagnostics
# ===========================

# Run Rust scanner on limited entries for quick testing
# Note: Uses sequential mode with --limit for efficient early termination
diagnose-scanner: $(WIKT_DUMP) $(RUST_SCANNER)
	@echo "Running Rust scanner with limit (first 10000 entries)..."
	$(RUST_SCANNER) "$(WIKT_DUMP)" /tmp/scanner_diagnostic.jsonl \
		--strategy sequential --limit 10000
	@echo "Output written to: /tmp/scanner_diagnostic.jsonl"

# ===========================
# Benchmarks
# ===========================

# Run complete benchmarks on full Wiktionary dataset
# Tests all parallelization strategies with thread counts: 4, 8, 16, 32
# Output: data/benchmark/en-wikt-{timestamp}-{strategy}[-t{threads}].jsonl
# For overnight runs, use:
#   caffeinate -i make benchmark-rust-scanner
benchmark-rust-scanner: $(WIKT_DUMP) $(RUST_SCANNER) | $(BENCHMARK_DIR)
	@echo "Running complete Rust scanner benchmarks..."
	$(RUN_BENCHMARK) \
		--input "$(WIKT_DUMP)" \
		--output-dir "$(BENCHMARK_DIR)" \
		--scanner "$(RUST_SCANNER)"

$(BENCHMARK_DIR):
	@mkdir -p "$(BENCHMARK_DIR)"

# Validate that all benchmark outputs are identical (when sorted)
benchmark-validate:
	$(RUN_BENCHMARK) --output-dir "$(BENCHMARK_DIR)" --validate-only

# ===========================
# Web Tools
# ===========================

# Spec editor - web UI for creating wordlist filter YAML specs
spec-editor-web: tools/wordlist-spec-editor/node_modules | check-pnpm
	@echo "Starting wordlist spec editor..."
	@echo "  Server will start at: http://localhost:8000"
	@echo "  Press Ctrl+C to stop the server"
	(cd tools/wordlist-spec-editor; pnpm start)

# Wordlist viewer - explore lexicon interactively
wordlist-viewer-web: tools/wordlist-viewer/node_modules | check-pnpm
	@echo "Starting interactive wordlist viewer..."
	@if [ ! -f "$(WORDLIST_TXT)" ]; then \
		echo "Error: Wordlist not found at $(WORDLIST_TXT)"; \
		echo "Run 'make build-en' first to generate the lexicon."; \
		exit 1; \
	fi
	@echo "  Server will start at: http://localhost:8080"
	@echo "  Press Ctrl+C to stop the server"
	(cd tools/wordlist-viewer; pnpm start)

# ===========================
# Word List Generation
# ===========================

# Directory containing the YAML specs understood by `owlex`
WORDLIST_SPECS_DIR := examples/wordlist-specs

# Directory where generated word lists will be written
WORDLISTS_DIR := data/wordlists

# Discover all YAML specs and derive output filenames
WORDLIST_SPEC_YAMLS := $(wildcard $(WORDLIST_SPECS_DIR)/*.yaml)
WORDLIST_TXTS := $(patsubst $(WORDLIST_SPECS_DIR)/%.yaml, \
                            $(WORDLISTS_DIR)/%.txt, \
                            $(WORDLIST_SPEC_YAMLS))

# Aggregate target: generate all word lists from specs
.PHONY: wordlists
wordlists: $(WORDLIST_TXTS)
	@echo "Generated word lists in $(WORDLISTS_DIR)/"
	@ls -lh $(WORDLISTS_DIR)/*.txt

# Pattern rule: YAML spec -> TXT word list
$(WORDLISTS_DIR)/%.txt: $(WORDLIST_SPECS_DIR)/%.yaml $(LEXEMES_ENRICHED) | $(WORDLISTS_DIR)
	@echo "Generating $(@F)..."
	$(UV) run owlex $< --output $@
	@wc -l $@

$(WORDLISTS_DIR):
	@mkdir -p "$@"

# ===========================
# Nightly CI Build
# ===========================

# Full pipeline for nightly CI builds
# Runs the complete fetch → build → package → report → validate → test cycle
#
# Pipeline stages:
#   1. Bootstrap: Set up Python environment and dependencies
#   2. Fetch: Download all source data (Wiktionary, WordNet, frequency lists, etc.)
#   3. Build: Compile Rust scanner, run full build-en pipeline, build browser trie
#   4. Package: Create release artifacts with manifest
#   5. Report: Generate comprehensive analysis reports
#   6. Validate: Run all validation checks (ENABLE coverage, profanity, childish terms)
#   7. Test: Run pytest and scanner parity validation
#   8. Diagnose: Run diagnostic checks on scanner output
#
# Usage:
#   make nightly                    # Run full pipeline
#   caffeinate -i make nightly      # Run with sleep prevention (macOS)
nightly:
	@echo "Start time: $$(date)"
	$(MAKE) build-and-prereqs
	$(MAKE) post-build
	@echo "End time: $$(date)"

weekly: build-and-prereqs post-build corpus-stats validate-scanner-parity-full

.PHONY: build-and-prereqs
build-and-prereqs: export UV_VENV_CLEAR=1
build-and-prereqs: bootstrap fetch-en build-rust-scanner build-en build-trie

.PHONY: post-build
post-build: export OPENWORD_CI=1
post-build: package report-en validate-all test-full diagnose-scanner wordlists
	@echo "Build artifacts:"
	@ls -lh $(BUILD_DIR)/*.trie $(BUILD_DIR)/*.json* 2>/dev/null || true
	@echo "Reports:"
	@ls -lh $(REPORTS_DIR)/*.md 2>/dev/null || true

.PHONY: benchmark
benchmark: benchmark-rust-scanner benchmark-validate
