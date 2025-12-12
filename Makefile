# OpenWord Lexicon Build System
# ==============================
#
# Primary targets:
#   make test      - Run all tests
#   make nightly   - Full nightly build (fetch + scan + enrich + validate)
#   make fetch     - Fetch data sources
#   make scan      - Run Wiktionary scanner
#   make enrich    - Run enrichment pipeline
#   make clean     - Clean build artifacts
#
# The build system uses Make's dependency tracking to avoid redundant work.
# Intermediate files are stored in data/intermediate/, final outputs in data/build/.

# =============================================================================
# Configuration
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Language configuration (can be overridden: make OW_LANG=de)
# Note: We use OW_LANG instead of LANG to avoid conflict with shell locale
OW_LANG ?= en

# Package manager
UV := uv

# Python commands via uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest

# CLI entry points (installed via pyproject.toml)
OWLEX := $(UV) run owlex
OWFETCH := $(UV) run owfetch
OWSCAN := $(UV) run owscan

# Rust scanner
RUST_SCANNER := crates/wiktionary-scanner/target/release/wiktionary-scanner

# =============================================================================
# Directory Structure
# =============================================================================

DATA_DIR := data
RAW_DIR := $(DATA_DIR)/raw/$(OW_LANG)
INTERMEDIATE_DIR := $(DATA_DIR)/intermediate
BUILD_DIR := $(DATA_DIR)/build
REPORTS_DIR := reports

# Create directories as needed
$(RAW_DIR) $(INTERMEDIATE_DIR) $(BUILD_DIR) $(REPORTS_DIR):
	mkdir -p $@

# =============================================================================
# Stamp Files (for dependency tracking)
# =============================================================================
# Instead of hardcoding data filenames, we use stamp files.
# The actual filenames are defined in YAML and read by the tools:
#   - schema/sources/index.yaml      -> owfetch knows what to download
#   - schema/enrichment/pipeline.yaml -> enrichment knows what data it needs
# This makes adding new sources a YAML-only change (plug-in style).

STAMPS_DIR := .stamps
$(STAMPS_DIR):
	mkdir -p $@

FETCH_STAMP := $(STAMPS_DIR)/fetch-$(OW_LANG).done
SCAN_STAMP := $(STAMPS_DIR)/scan-$(OW_LANG).done
ENRICH_STAMP := $(STAMPS_DIR)/enrich-$(OW_LANG).done

# =============================================================================
# Intermediate Files (generated)
# =============================================================================

SCANNER_OUTPUT := $(INTERMEDIATE_DIR)/$(OW_LANG)-wikt-v2.jsonl
SCANNER_STATS := $(INTERMEDIATE_DIR)/$(OW_LANG)-wikt-v2-stats.json
ENRICHED_OUTPUT := $(INTERMEDIATE_DIR)/$(OW_LANG)-wikt-v2-enriched.jsonl

# =============================================================================
# Build Outputs
# =============================================================================

UNIFIED_TRIE := $(BUILD_DIR)/$(OW_LANG).trie
GAME_TRIE := $(BUILD_DIR)/$(OW_LANG)-game.trie
METADATA := $(BUILD_DIR)/$(OW_LANG).meta.json

# =============================================================================
# Phony Targets
# =============================================================================

.PHONY: all test nightly weekly fetch scan enrich build clean scrub \
        deps lint fmt validate help \
        web-spec-editor web-viewer

.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help:
	@echo "OpenWord Lexicon Build System"
	@echo ""
	@echo "Primary targets:"
	@echo "  make test      Run all tests"
	@echo "  make nightly   Full nightly build"
	@echo "  make fetch     Fetch data sources"
	@echo "  make scan      Run Wiktionary scanner"
	@echo "  make enrich    Run enrichment pipeline"
	@echo "  make build     Build tries and metadata"
	@echo "  make clean     Clean build artifacts"
	@echo ""
	@echo "Development:"
	@echo "  make deps      Install dependencies"
	@echo "  make lint      Run linters"
	@echo "  make fmt       Format code"
	@echo ""
	@echo "Web tools:"
	@echo "  make web-spec-editor   Start spec editor dev server"
	@echo "  make web-viewer        Start viewer dev server"

# =============================================================================
# Dependencies
# =============================================================================

deps:
	$(UV) sync
	@echo "Dependencies installed"

# =============================================================================
# Testing
# =============================================================================

test: deps
	$(PYTEST) tests/ -v

test-quick: deps
	$(PYTEST) tests/ -v -x --ignore=tests/test_wiktionary_data_quality.py

# =============================================================================
# Fetching
# =============================================================================
# owfetch reads schema/sources/index.yaml to know what to download.
# The stamp file tracks completion - touch it to skip re-fetching.

$(FETCH_STAMP): schema/sources/index.yaml | $(RAW_DIR) $(STAMPS_DIR)
	$(OWFETCH)
	touch $@

fetch: $(FETCH_STAMP)

# Force re-fetch (ignores stamp)
fetch-force: deps | $(RAW_DIR)
	$(OWFETCH) --force
	touch $(FETCH_STAMP)

# =============================================================================
# Scanning
# =============================================================================
# Scanner depends on fetch being complete (via stamp) and schema files.
# The scanner reads the dump location from schema or convention.

$(SCANNER_OUTPUT): $(FETCH_STAMP) schema/core schema/bindings | $(INTERMEDIATE_DIR)
	@echo "Running Wiktionary scanner..."
	$(OWSCAN) "$(RAW_DIR)/$(OW_LANG)wiktionary-latest-pages-articles.xml.bz2" \
		"$(SCANNER_OUTPUT)" \
		--schema-core schema/core \
		--schema-bindings schema/bindings \
		--stats "$(SCANNER_STATS)"

scan: $(SCANNER_OUTPUT)

# =============================================================================
# Enrichment
# =============================================================================
# Enrichment depends on scanner output and fetch completion.
# The pipeline reads schema/enrichment/pipeline.yaml to know what data files
# it needs and where to find them.

$(ENRICHED_OUTPUT): $(SCANNER_OUTPUT) $(FETCH_STAMP) schema/enrichment/pipeline.yaml
	@echo "Running enrichment pipeline..."
	$(PYTHON) -m openword.enrich.pipeline \
		--input "$(SCANNER_OUTPUT)" \
		--output "$(ENRICHED_OUTPUT)" \
		--language $(OW_LANG)

enrich: $(ENRICHED_OUTPUT)

# =============================================================================
# Building (tries, metadata)
# =============================================================================

$(UNIFIED_TRIE): $(ENRICHED_OUTPUT) | $(BUILD_DIR)
	@echo "Building unified trie..."
	$(PYTHON) -m openword.trie_build \
		--input "$(ENRICHED_OUTPUT)" \
		--language "$(OW_LANG)"

$(METADATA): $(ENRICHED_OUTPUT) | $(BUILD_DIR)
	@echo "Building metadata..."
	$(PYTHON) -m openword.export_metadata \
		--input "$(ENRICHED_OUTPUT)" \
		--language "$(OW_LANG)" \
		--gzip

build: $(UNIFIED_TRIE) $(METADATA)

# =============================================================================
# Validation
# =============================================================================

validate: $(ENRICHED_OUTPUT)
	@echo "Running validation..."
	$(PYTEST) tests/test_wiktionary_data_quality.py -v

# =============================================================================
# Code Quality
# =============================================================================

lint:
	$(UV) run ruff check src/ tests/ tools/

fmt:
	$(UV) run ruff format src/ tests/ tools/
	$(UV) run black src/ tests/ tools/

# =============================================================================
# Nightly/Weekly Builds
# =============================================================================

nightly: deps fetch scan enrich build validate test
	@echo ""
	@echo "Nightly build complete!"
	@echo "  Scanner output: $(SCANNER_OUTPUT)"
	@echo "  Enriched output: $(ENRICHED_OUTPUT)"
	@echo "  Trie: $(UNIFIED_TRIE)"
	@wc -l "$(ENRICHED_OUTPUT)"

weekly: nightly
	@echo "Weekly build complete (same as nightly for now)"

# =============================================================================
# Web Tools
# =============================================================================

web-spec-editor:
	cd web/spec-editor && pnpm install && pnpm dev

web-viewer:
	cd web/viewer && pnpm install && pnpm dev

# =============================================================================
# Cleaning
# =============================================================================

clean:
	rm -rf $(INTERMEDIATE_DIR)/*.jsonl
	rm -rf $(INTERMEDIATE_DIR)/*.json
	rm -rf $(BUILD_DIR)/*.trie
	rm -rf $(BUILD_DIR)/*.json
	rm -rf $(STAMPS_DIR)
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Deep clean - also removes fetched data
scrub: clean
	rm -rf $(RAW_DIR)

# =============================================================================
# Rust Scanner (optional, for benchmarking)
# =============================================================================

rust-scanner: crates/wiktionary-scanner/Cargo.toml
	cd crates/wiktionary-scanner && cargo build --release

benchmark-rust: rust-scanner $(WIKT_DUMP)
	@echo "Benchmarking Rust scanner..."
	time $(RUST_SCANNER) "$(WIKT_DUMP)" /dev/null
