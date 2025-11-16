# Makefile (root) - uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11
LANG ?= en

# Directory structure (language-based)
RAW_DIR := data/raw/$(LANG)
INTERMEDIATE_DIR := data/intermediate/$(LANG)
BUILD_DIR := data/build/$(LANG)
REPORTS_DIR := reports
WORDLISTS_DIR := data/wordlists

# Build artifacts
WIKTIONARY_DUMP := $(RAW_DIR)/$(LANG)wiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := $(INTERMEDIATE_DIR)/wikt.jsonl
FREQUENCY_DATA := $(RAW_DIR)/$(LANG)_50k.txt
WORDNET_ARCHIVE := $(RAW_DIR)/english-wordnet-2024.tar.gz
UNIFIED_TRIE := $(BUILD_DIR)/$(LANG).trie
UNIFIED_META := $(BUILD_DIR)/$(LANG).meta.json
WORDLIST_TXT := $(BUILD_DIR)/wordlist.txt

.PHONY: bootstrap venv deps fmt lint test clean clean-build clean-viewer scrub \
        fetch-en build-en build-wiktionary-json build-trie package check-limits \
        report-en analyze-all-reports analyze-local diagnose-scanner \
        wordlist-builder wordlist-builder-install wordlist-builder-cli wordlist-builder-web owlex-filter help-builder

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

# Fetch all English language sources
fetch-en:
	@echo "=== Fetching English Language Sources ==="
	@bash scripts/fetch/fetch_enable.sh
	@bash scripts/fetch/fetch_eowl.sh
	@bash scripts/fetch/fetch_wiktionary.sh
	@bash scripts/fetch/fetch_wordnet.sh
	@bash scripts/fetch/fetch_frequency.sh
	@bash scripts/sys/limits.sh update
	@echo "=== Fetch complete ==="

# ===========================
# Build Pipeline
# ===========================

# Build English lexicon (unified pipeline)
build-en: fetch-en build-wiktionary-json
	@echo "=== Building English Lexicon ==="
	@echo "Step 1: Ingest source data"
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wikt_ingest.py
	@echo ""
	@echo "Step 2: Merge all sources"
	$(UV) run python src/openword/merge_all.py
	@echo ""
	@echo "Step 3: Enrich with WordNet"
	$(UV) run python src/openword/wordnet_enrich.py --unified
	@echo ""
	@echo "Step 4: Assign frequency tiers"
	$(UV) run python src/openword/frequency_tiers.py --unified
	@echo ""
	@echo "Step 5: Build trie"
	$(UV) run python src/openword/trie_build.py --unified
	@echo ""
	@echo "=== English lexicon build complete ==="

# Build Wiktionary JSONL using lightweight scanner parser (file-based dependency)
$(WIKTIONARY_JSON): $(WIKTIONARY_DUMP)
	@echo "Extracting Wiktionary..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		"$(WIKTIONARY_JSON)"

# Convenience target (will only rebuild if output missing or input newer)
build-wiktionary-json: deps $(WIKTIONARY_JSON)

# Build compact trie for browser visualization
build-trie: $(WORDLIST_TXT)
	@echo "Building browser-compatible trie..."
	@if ! command -v pnpm &> /dev/null; then \
		echo "Error: pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@if [ ! -d "viewer/node_modules" ]; then \
		echo "Installing viewer dependencies..."; \
		cd viewer && pnpm install; \
	fi
	@cd viewer && pnpm run build-trie

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

clean-build:
	rm -rf data/intermediate data/filtered data/build \
		data/artifacts data/.limits-log.json \
		ATTRIBUTION.md MANIFEST.json

clean-viewer:
	rm -rf viewer/node_modules viewer/pnpm-lock.yaml viewer/data viewer/dist

scrub: clean clean-build
	rm -rf .venv

# ===========================
# Inspection & Reporting
# ===========================

# Generate comprehensive analysis reports for English
report-en: deps
	@echo "=== Generating English Lexicon Reports ==="
	$(UV) run python tools/generate_reports.py
	@echo ""
	@echo "=== Reports complete ==="
	@echo "Reports generated in: $(REPORTS_DIR)/"
	@ls -lh $(REPORTS_DIR)/*.md 2>/dev/null || true

# Run ALL analysis and reporting (comprehensive audit)
analyze-all-reports: deps
	@echo "=========================================="
	@echo "Comprehensive Analysis - English Lexicon"
	@echo "=========================================="
	@echo ""
	@$(MAKE) report-en
	@echo ""
	@echo "=========================================="
	@echo "✓ All analysis complete!"
	@echo "=========================================="

# ===========================
# Local Development Workflows
# ===========================

# Run full local analysis workflow (extract Wiktionary data)
analyze-local: build-wiktionary-json
	@echo "Local analysis complete - Wiktionary data extracted"
	@echo "Run 'make report-en' after building to generate comprehensive reports"

# Run scanner parser in diagnostic mode
diagnose-scanner: deps $(WIKTIONARY_DUMP)
	@mkdir -p $(REPORTS_DIR)
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		/tmp/scanner_diagnostic.jsonl \
		--diagnostic $(REPORTS_DIR)/scanner_diagnostic.txt

# ===========================
# Interactive Word List Builder
# ===========================

# Display help for word list builder
help-builder:
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "  OpenWord Lexicon - Interactive Word List Builder"
	@echo "═══════════════════════════════════════════════════════════"
	@echo ""
	@echo "The word list builder helps you create custom filtered word lists"
	@echo "using the unified English lexicon with flexible runtime filtering."
	@echo ""
	@echo "Available Targets:"
	@echo ""
	@echo "  make wordlist-builder-cli"
	@echo "      Launch interactive CLI builder (terminal-based)"
	@echo ""
	@echo "  make wordlist-builder-web"
	@echo "      Open web-based builder interface in browser"
	@echo ""
	@echo "  make owlex-filter SPEC=<file.json>"
	@echo "      Generate filtered word list from specification"
	@echo ""
	@echo "Examples:"
	@echo ""
	@echo "  # Create specification interactively"
	@echo "  make wordlist-builder-cli"
	@echo ""
	@echo "  # Use web interface"
	@echo "  make wordlist-builder-web"
	@echo ""
	@echo "  # Generate word list from specification"
	@echo "  make owlex-filter SPEC=wordlist-spec.json > words.txt"
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
	@echo ""
	@echo "Documentation:"
	@echo "  - docs/FILTERING.md - Filtering guide"
	@echo "  - docs/FILTER_CAPABILITIES.md - Filter reference"
	@echo "  - docs/UNIFIED_BUILD_DESIGN.md - Architecture"
	@echo ""

# Build CLI tool dependencies with pnpm
wordlist-builder-install:
	@echo "Installing wordlist builder dependencies..."
	@if ! command -v pnpm >/dev/null 2>&1; then \
		echo "Error: pnpm is required but not installed."; \
		echo "Install with: npm install -g pnpm"; \
		echo "Or use: cd tools/wordlist-builder && npm install"; \
		exit 1; \
	fi
	@cd tools/wordlist-builder && pnpm install

# Launch CLI builder (requires Node.js)
wordlist-builder-cli:
	@echo "Launching interactive word list builder..."
	@if ! command -v node >/dev/null 2>&1; then \
		echo "Error: Node.js is required but not installed."; \
		echo "Please install Node.js from: https://nodejs.org/"; \
		exit 1; \
	fi
	@if [ -d "tools/wordlist-builder/node_modules/@clack/prompts" ]; then \
		echo "Using enhanced TUI (Clack)..."; \
		node tools/wordlist-builder/cli-builder-clack.js; \
	else \
		echo "Using basic CLI (run 'make wordlist-builder-install' for enhanced UI)..."; \
		node tools/wordlist-builder/cli-builder.js; \
	fi

# Open web builder in default browser
wordlist-builder-web:
	@echo "Opening web-based word list builder..."
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open tools/wordlist-builder/web-builder.html; \
	elif command -v open >/dev/null 2>&1; then \
		open tools/wordlist-builder/web-builder.html; \
	elif command -v start >/dev/null 2>&1; then \
		start tools/wordlist-builder/web-builder.html; \
	else \
		echo "Please open this file in your browser:"; \
		echo "  file://$(shell pwd)/tools/wordlist-builder/web-builder.html"; \
	fi

# Run owlex filter (requires SPEC parameter)
owlex-filter: deps
	@if [ -z "$(SPEC)" ]; then \
		echo "Error: SPEC parameter required"; \
		echo "Usage: make owlex-filter SPEC=wordlist-spec.json"; \
		echo ""; \
		echo "To create a specification, run:"; \
		echo "  make wordlist-builder-cli"; \
		echo "or:"; \
		echo "  make wordlist-builder-web"; \
		exit 1; \
	fi
	@if [ ! -f "$(SPEC)" ]; then \
		echo "Error: Specification file not found: $(SPEC)"; \
		exit 1; \
	fi
	@echo "Filtering with specification: $(SPEC)"
	$(UV) run python -m openword.owlex "$(SPEC)"

# Convenience target: Combined CLI builder workflow
wordlist-builder: help-builder

# ===========================
# Example Specifications
# ===========================

# Create sample filter specifications
examples/wordlist-specs:
	@mkdir -p examples/wordlist-specs
	@echo "Creating example specifications..."
	@echo '{"version":"1.0","name":"Wordle Words","filters":{"character":{"exact_length":5,"pattern":"^[a-z]+$$"},"phrase":{"max_words":1},"frequency":{"min_tier":"top10k"}}}' | jq '.' > examples/wordlist-specs/wordle.json
	@echo '{"version":"1.0","name":"Kids Game Words","filters":{"character":{"min_length":3,"max_length":10},"phrase":{"max_words":1},"frequency":{"tiers":["top1k","top10k"]},"pos":{"include":["noun"]},"concreteness":{"values":["concrete"]}}}' | jq '.' > examples/wordlist-specs/kids-nouns.json
	@echo '{"version":"1.0","name":"Profanity Blocklist","filters":{"labels":{"register":{"include":["vulgar","offensive","derogatory"]}}}}' | jq '.' > examples/wordlist-specs/profanity-blocklist.json
	@echo '{"version":"1.0","name":"Scrabble Words","filters":{"phrase":{"max_words":1},"character":{"pattern":"^[a-z]+$$"}}}' | jq '.' > examples/wordlist-specs/scrabble.json
	@echo "✓ Created example specifications in examples/wordlist-specs/"
	@ls -lh examples/wordlist-specs/
