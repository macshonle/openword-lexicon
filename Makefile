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
FREQUENCY_DATA := $(RAW_DIR)/$(LEXICON_LANG)_50k.txt
WORDNET_ARCHIVE := $(RAW_DIR)/english-wordnet-2024.tar.gz
UNIFIED_TRIE := $(BUILD_DIR)/$(LEXICON_LANG).trie
UNIFIED_META := $(BUILD_DIR)/$(LEXICON_LANG).meta.json
WORDLIST_TXT := $(BUILD_DIR)/wordlist.txt

.PHONY: bootstrap venv deps fmt lint test clean scrub \
        fetch-en build-en build-wiktionary-json build-trie package check-limits \
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

check-limits:
	@bash scripts/sys/limits.sh check

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
	bash scripts/sys/limits.sh update

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
# Build Pipeline
# ===========================

# Build English lexicon (unified pipeline)
# Pipeline order:
#   1. Ingest word sources (EOWL, Wiktionary, WordNet)
#   2. Merge all sources
#   3. WordNet POS backfill (concreteness deprecated)
#   4. Brysbaert concreteness enrichment (PRIMARY source for concreteness)
#   5. Frequency tiers
#   6. Build trie
build-en: fetch-en build-wiktionary-json
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wikt_ingest.py
	$(UV) run python src/openword/wordnet_source.py
	$(UV) run python src/openword/merge_all.py
	$(UV) run python src/openword/wordnet_enrich.py --unified
	$(UV) run python src/openword/brysbaert_enrich.py --unified
	$(UV) run python src/openword/frequency_tiers.py --unified
	$(UV) run python src/openword/trie_build.py --unified
	@echo "✓ English lexicon build complete"

# Build Wiktionary JSONL using lightweight scanner parser (file-based dependency)
$(WIKTIONARY_JSON): $(WIKTIONARY_DUMP)
	@echo "Extracting Wiktionary..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" "$(WIKTIONARY_JSON)"

# Convenience target (will only rebuild if output missing or input newer)
build-wiktionary-json: deps $(WIKTIONARY_JSON)

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
	rm -rf data/intermediate data/filtered data/build \
		data/artifacts data/.limits-log.json \
		ATTRIBUTION.md MANIFEST.json
	rm -rf viewer/node_modules viewer/pnpm-lock.yaml viewer/data viewer/dist

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

# Run scanner parser in diagnostic mode
diagnose-scanner: deps $(WIKTIONARY_DUMP)
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" /tmp/scanner_diagnostic.jsonl \
		--diagnostic $(REPORTS_DIR)/scanner_diagnostic.txt

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
