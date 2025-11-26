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
SLICES_DIR := data/diagnostic/wikt_slices

# Build artifacts (language-prefixed filenames in flat directories)
WIKTIONARY_DUMP := $(RAW_DIR)/$(LEXICON_LANG)wiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-wikt.jsonl
WIKTIONARY_JSON_SORTED := $(INTERMEDIATE_DIR)/$(LEXICON_LANG)-wikt-sorted.jsonl
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
RUST_SCANNER := tools/wiktionary-rust/target/release/wiktionary-rust

.PHONY: bootstrap venv deps fmt lint test clean scrub \
        fetch-en build-en build-wiktionary-json build-rust-scanner build-trie build-metadata package \
        report-en diagnose-scanner validate-all validate-enable validate-profanity validate-childish \
        extract-slices wordlist-builder-web viewer-web

# ===========================
# Development Environment
# ===========================

# Bootstrap local dev environment (idempotent)
bootstrap: venv deps

# Create/refresh project venv
venv:
	$(UV) venv --python $(PY_VERSION)
	@$(UV) run python -c "import sys; print('Python', sys.version)"
	@echo "Venv: .venv created/updated"

# Install dependencies
deps:
	$(UV) pip install -e .
	$(UV) pip install -e .[dev]

# Code quality
fmt:
	$(UV) run black .

lint:
	$(UV) run ruff check .

# Tests (placeholder until implemented)
test:
	$(UV) run pytest -q || true

# ===========================
# Data Fetching
# ===========================

# Fetch all English language sources (ENABLE removed - optional validation only)
fetch-en:
	@echo "Fetching English Language Sources..."
	bash scripts/fetch/fetch_eowl.sh
	bash scripts/fetch/fetch_wiktionary.sh
	bash scripts/fetch/fetch_wordnet.sh
	bash scripts/fetch/fetch_frequency.sh
	bash scripts/fetch/fetch_brysbaert.sh

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
%/node_modules: %/package.json check-pnpm
	@echo "Installing dependencies in $*..."
	cd $* && pnpm install
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
# This is a high-performance replacement for tools/wiktionary_scanner_parser.py
# The Rust version is significantly faster (typically 5-10x) and produces identical output.
#
# Build command: cd tools/wiktionary-rust && cargo build --release
# Binary output: tools/wiktionary-rust/target/release/wiktionary-rust
$(RUST_SCANNER): tools/wiktionary-rust/Cargo.toml tools/wiktionary-rust/src/main.rs | check-cargo
	@echo "Building Rust scanner (release mode)..."
	cd tools/wiktionary-rust && cargo build --release
	@echo "Rust scanner built: $(RUST_SCANNER)"

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
	$(UV) run python src/openword/source_merge.py \
		--wikt-lexemes $(LEXEMES_JSON) \
		--eowl $(EOWL_FILE) \
		--wordnet $(WORDNET_ARCHIVE) \
		--output $(LEXEMES_MERGED)
	@echo "Enriching lexemes file..."
	$(UV) run python src/openword/brysbaert_enrich.py \
		--input $(LEXEMES_MERGED) \
		--output $(LEXEMES_ENRICHED)
	$(UV) run python src/openword/frequency_tiers.py \
		--input $(LEXEMES_ENRICHED) \
		--output $(LEXEMES_ENRICHED)
	@echo "Building tries..."
	$(UV) run python src/openword/trie_build.py \
		--input $(LEXEMES_ENRICHED) --profile full
	$(UV) run python src/openword/trie_build.py \
		--input $(LEXEMES_ENRICHED) --profile game
	@echo "Exporting metadata modules..."
	$(UV) run python src/openword/export_metadata.py \
		--input $(LEXEMES_ENRICHED) --modules all --gzip
	$(UV) run python src/openword/generate_statistics.py

# Build and sort Wiktionary JSONL using Rust scanner
# 1. Extract from XML dump to unsorted JSONL (kept for traceability)
# 2. Sort lexicographically by word (ensures duplicate entries are consecutive,
#    trie ordinal = line number, matches Python's default lexicographic sort)
$(WIKTIONARY_JSON_SORTED): $(WIKTIONARY_DUMP) $(RUST_SCANNER)
	@echo "Extracting Wiktionary (using Rust scanner)..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(RUST_SCANNER) "$(WIKTIONARY_DUMP)" "$(WIKTIONARY_JSON)"
	@echo "Sorting Wiktionary entries by word..."
	$(UV) run python src/openword/wikt_sort.py \
		--input $(WIKTIONARY_JSON) \
		--output $(WIKTIONARY_JSON_SORTED)

# Normalize into two-file format: lexemes + senses
# This step:
#   1. Groups entries by word
#   2. Extracts word-level properties into lexeme entries
#   3. Deduplicates senses by projection (pos, tags, flags)
#   4. Writes offset/length linking between files
$(LEXEMES_JSON) $(SENSES_JSON): $(WIKTIONARY_JSON_SORTED)
	@echo "Normalizing Wiktionary into lexemes + senses tables..."
	$(UV) run python src/openword/wikt_normalize.py \
		--input $(WIKTIONARY_JSON_SORTED) \
		--lexemes-output $(LEXEMES_JSON) \
		--senses-output $(SENSES_JSON) \
		-v

# Convenience target (will only rebuild if output missing or input newer)
build-wiktionary-json: $(WIKTIONARY_JSON_SORTED)

# Build compact trie for browser visualization
build-trie: $(WORDLIST_TXT) viewer/node_modules
	@echo "Building browser-compatible trie..."
	@echo "Building binary trie from $(WORDLIST_TXT)..."
	cd viewer && pnpm run build-trie ../$(WORDLIST_TXT) data/$(LEXICON_LANG).trie.bin

# Export modular metadata layers (frequency, concreteness, syllables, sources)
# Creates gzipped JSON files in data/build/{lang}-{module}.json.gz
build-metadata: $(LEXEMES_ENRICHED)
	@echo "Exporting metadata modules (gzipped)..."
	$(UV) run python src/openword/export_metadata.py \
		--input $(LEXEMES_ENRICHED) --modules all --gzip

# Export trie to plain text wordlist
$(WORDLIST_TXT): $(UNIFIED_TRIE)
	$(UV) run python src/openword/export_wordlist.py

# Package release artifacts
package:
	$(UV) run python src/openword/manifest.py
	$(UV) run python src/openword/package_release.py

# ===========================
# Cleanup
# ===========================

clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +
	rm -rf data/intermediate data/filtered data/build data/artifacts \
		ATTRIBUTION.md MANIFEST.json
	rm -rf viewer/node_modules viewer/pnpm-lock.yaml viewer/data viewer/dist
	@if [ -d tools/wiktionary-rust/target ]; then \
		echo "Cleaning Rust build artifacts..."; \
		cd tools/wiktionary-rust && cargo clean; \
	fi

scrub: clean
	rm -rf .venv

# ===========================
# Reports & Validation
# ===========================

# Generate comprehensive analysis reports for English
report-en: deps
	@echo "Generating English Lexicon Reports..."
	$(UV) run python tools/generate_reports.py
	@echo "Reports generated in: $(REPORTS_DIR)/"
	@ls -lh $(REPORTS_DIR)/*.md 2>/dev/null || true

# Run all validation checks
validate-all: validate-enable validate-profanity validate-childish

# Validate lexicon coverage against ENABLE word list
validate-enable: deps
	@echo "Validating against ENABLE word list..."
	@bash scripts/fetch/fetch_enable.sh || echo "Warning: ENABLE fetch failed (GitHub CDN issue?)"
	@if [ -f data/raw/en/enable1.txt ]; then \
		echo "Running validation..."; \
		$(UV) run python tools/validate_enable_coverage.py; \
	else \
		echo "Error: ENABLE not available for validation."; \
		echo "This is expected if GitHub CDN is having issues."; \
		exit 1; \
	fi

# Validate profanity/offensive term labeling
# WARNING: Downloads and analyzes lists with explicit/offensive content
validate-profanity: deps
	@bash scripts/fetch/fetch_profanity_lists.sh
	@echo "Running validation..."
	@$(UV) run python tools/validate_profanity_coverage.py

# Validate childish term labeling
validate-childish: deps
	@echo "Validating childish term labeling..."
	@$(UV) run python tools/validate_childish_terms.py

# ===========================
# Diagnostics
# ===========================

# Run Rust scanner on limited entries for quick testing
diagnose-scanner: $(WIKTIONARY_DUMP) $(RUST_SCANNER)
	@echo "Running Rust scanner with limit (first 10000 entries)..."
	$(RUST_SCANNER) "$(WIKTIONARY_DUMP)" /tmp/scanner_diagnostic.jsonl --limit 10000
	@echo "Output written to: /tmp/scanner_diagnostic.jsonl"

# Extract diagnostic XML slices for analysis
extract-slices: deps $(WIKTIONARY_DUMP)
	@echo "Extracting diagnostic XML slices..."
	@mkdir -p "$(SLICES_DIR)"
	$(UV) run python tools/wiktionary_xml_slicer.py \
		"$(WIKTIONARY_DUMP)" "$(SLICES_DIR)"
	@echo "Slices written -- add to git with: git add $(SLICES_DIR)"

# ===========================
# Web Tools
# ===========================

# Word list builder - create filtered word lists via web UI
wordlist-builder-web: tools/wordlist-builder/node_modules
	@echo "Starting web-based word list builder..."
	@echo ""
	@echo "  Server will start at: http://localhost:8000"
	@echo "  Press Ctrl+C to stop the server"
	@echo ""
	@cd tools/wordlist-builder && pnpm start

# Trie viewer - explore lexicon interactively
viewer-web: viewer/node_modules
	@echo "Starting interactive trie viewer..."
	@if [ ! -f "$(WORDLIST_TXT)" ]; then \
		echo ""; \
		echo "Warning: Wordlist not found at $(WORDLIST_TXT)"; \
		echo "Run 'make build-en' first to generate the lexicon."; \
		echo ""; \
		echo "The viewer will start, but data will not be available until you build."; \
		echo ""; \
		sleep 2; \
	fi
	@echo "  Server will start at: http://localhost:8080"
	@echo "  Press Ctrl+C to stop the server"
	@echo ""
	@echo "  Available pages:"
	@echo "    /index.html        - Dynamic trie builder"
	@echo "    /index-binary.html - Binary trie loader"
	@echo ""
	@cd viewer && pnpm start
