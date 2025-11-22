# Makefile (root) - uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11
LEXICON_LANG ?= en

# Directory structure (language-based)
RAW_DIR := data/raw/$(LEXICON_LANG)
INTERMEDIATE_DIR := data/intermediate/$(LEXICON_LANG)
BUILD_DIR := data/build/$(LEXICON_LANG)
REPORTS_DIR := reports
WORDLISTS_DIR := data/wordlists
SLICES_DIR := data/diagnostic/wikt_slices

# Build artifacts
WIKTIONARY_DUMP := $(RAW_DIR)/$(LEXICON_LANG)wiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := $(INTERMEDIATE_DIR)/wikt.jsonl
WIKTIONARY_JSON_SORTED := $(INTERMEDIATE_DIR)/wikt-sorted.jsonl
FREQUENCY_DATA := $(RAW_DIR)/$(LEXICON_LANG)_50k.txt
WORDNET_ARCHIVE := $(RAW_DIR)/english-wordnet-2024.tar.gz
UNIFIED_TRIE := $(BUILD_DIR)/$(LEXICON_LANG).trie
UNIFIED_META := $(BUILD_DIR)/$(LEXICON_LANG).meta.json
WORDLIST_TXT := $(BUILD_DIR)/wordlist.txt

# Rust tools
RUST_SCANNER := tools/wiktionary-rust/target/release/wiktionary-rust

.PHONY: bootstrap venv deps fmt lint test clean scrub \
        fetch-en build-en build-wiktionary-json build-rust-scanner build-trie package check-limits \
        report-en analyze-local diagnose-scanner validate-enable \
        wordlist-builder-web viewer-web

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
	@command -v pnpm >/dev/null 2>&1 || { echo "Error: pnpm not found. Install with: npm install -g pnpm"; exit 1; }

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
	@command -v cargo >/dev/null 2>&1 || { echo "Error: cargo not found. Install Rust from: https://rustup.rs/"; exit 1; }

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

# Build English lexicon (unified pipeline)
# Pipeline order:
#   0. Extract Wiktionary to wikt.jsonl (unsorted, XML order)
#   1. Sort Wiktionary entries by word (creates wikt-sorted.jsonl)
#   2. Ingest word sources (EOWL, Wiktionary, WordNet)
#   3. Merge all sources
#   4. WordNet POS backfill (concreteness deprecated)
#   5. Brysbaert concreteness enrichment (PRIMARY source for concreteness)
#   6. Frequency tiers
#   7. Build trie
#   8. Generate build statistics (MUST run after all enrichment)
build-en: fetch-en $(WIKTIONARY_JSON_SORTED)
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wikt_ingest.py
	$(UV) run python src/openword/wordnet_source.py
	$(UV) run python src/openword/merge_all.py
	$(UV) run python src/openword/wordnet_enrich.py --unified
	$(UV) run python src/openword/brysbaert_enrich.py --unified
	$(UV) run python src/openword/frequency_tiers.py --unified
	$(UV) run python src/openword/trie_build.py --unified
	$(UV) run python src/openword/generate_statistics.py

# Build Wiktionary JSONL using Rust scanner (file-based dependency)
# Outputs wikt.jsonl in unsorted XML source order (kept for traceability)
$(WIKTIONARY_JSON): $(WIKTIONARY_DUMP) $(RUST_SCANNER)
	@echo "Extracting Wiktionary (using Rust scanner)..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(RUST_SCANNER) "$(WIKTIONARY_DUMP)" "$(WIKTIONARY_JSON)"

# Sort Wiktionary entries lexicographically by word
# This ensures: 1) duplicate entries are consecutive, 2) trie ordinal = line number
# Sorting logic matches trie_build.py exactly (Python's default lexicographic sort)
$(WIKTIONARY_JSON_SORTED): $(WIKTIONARY_JSON)
	@echo "Sorting Wiktionary entries by word..."
	$(UV) run python src/openword/wikt_sort.py

# Convenience target (will only rebuild if output missing or input newer)
build-wiktionary-json: $(WIKTIONARY_JSON)

# Build compact trie for browser visualization
build-trie: $(WORDLIST_TXT) viewer/node_modules
	@echo "Building browser-compatible trie..."
	@echo "Building binary trie from $(WORDLIST_TXT)..."
	cd viewer && pnpm run build-trie -- ../$(WORDLIST_TXT) data/$(LEXICON_LANG).trie.bin

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
# Inspection & Reporting
# ===========================

# Generate comprehensive analysis reports for English
report-en: deps
	@echo "Generating English Lexicon Reports..."
	$(UV) run python tools/generate_reports.py
	@echo "Reports generated in: $(REPORTS_DIR)/"
	@ls -lh $(REPORTS_DIR)/*.md 2>/dev/null || true

# ===========================
# Local Development Workflows
# ===========================

# Run full local analysis workflow (extract Wiktionary data)
analyze-local: build-wiktionary-json

# ===========================
# Validation
# ===========================
validate-all: validate-enable validate-profanity validate-childish

# Validate lexicon coverage against ENABLE word list (baseline check)
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
# ⚠️  WARNING: Downloads and analyzes lists with explicit/offensive content ⚠️
validate-profanity: deps
	@bash scripts/fetch/fetch_profanity_lists.sh
	@echo "Running validation..."
	@$(UV) run python tools/validate_profanity_coverage.py

# Validate childish term labeling
validate-childish: deps
	@echo "Validating childish term labeling..."
	@$(UV) run python tools/validate_childish_terms.py

# Run Rust scanner with limit for quick diagnostics
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
# Interactive Word List Builder
# ===========================

# Display help for word list builder
help-builder:
	@echo "  # Create specification with web interface"
	@echo "  make wordlist-builder-web"
	@echo ""
	@echo "  # Generate word list from specification"
	@echo "  uv run python -m openword.owlex wordlist-spec.json > words.txt"
	@echo ""
	@echo "  # Use Python filters directly"
	@echo "  uv run python -m openword.filters \\"
	@echo "    data/intermediate/unified/entries_tiered.jsonl \\"
	@echo "    output.jsonl --preset kids-nouns"
	@echo ""
	@echo "Presets Available:"
	@echo "  - wordle: 5-letter common words"
	@echo "  - kids-nouns: Concrete nouns for children"
	@echo "  - scrabble: Single words for Scrabble"
	@echo "  - profanity: Flagged inappropriate words (for blocklist)"
	@echo "  - child-safe: Safe for children's games"

# Start web builder server
wordlist-builder-web: tools/wordlist-builder/node_modules
	@echo "Starting web-based word list builder..."
	@echo ""
	@echo "  Server will start at: http://localhost:8000"
	@echo "  Press Ctrl+C to stop the server"
	@echo ""
	@cd tools/wordlist-builder && pnpm start

# ===========================
# Interactive Trie Viewer
# ===========================

# Start trie viewer server
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
