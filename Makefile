# Makefile (root) — uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

WIKTIONARY_DUMP := data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := data/intermediate/plus/wikt.jsonl

.PHONY: bootstrap venv deps fmt lint test clean clean-viewer scrub \
        fetch fetch-core fetch-plus fetch-post-process-plus \
        build-core build-plus export-wordlist build-binary package check-limits start-server \
        reports report-raw report-pipeline report-trie report-metadata report-compare

# Bootstrap local dev environment (idempotent)
bootstrap: venv deps
	@echo "Bootstrap complete."

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

fetch: fetch-core fetch-plus fetch-post-process-plus

# Fetch core sources (PD/permissive only)
fetch-core:
	@bash scripts/fetch/fetch_enable.sh
	@bash scripts/fetch/fetch_eowl.sh
	@bash scripts/sys/limits.sh update

# Fetch plus sources (CC-BY-SA enrichments)
fetch-plus:
	@bash scripts/fetch/fetch_wiktionary.sh
	@bash scripts/fetch/fetch_wordnet.sh
	@bash scripts/fetch/fetch_frequency.sh
	@bash scripts/sys/limits.sh update

fetch-post-process-plus: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run wiktwords "$(WIKTIONARY_DUMP)" \
		--out "$(WIKTIONARY_JSON)" \
		--dump-file-language-code en \
		--language-code en \
		--language-code MUL \
		--all

build-core:
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	$(UV) run python src/openword/export_wordlist.py

build-plus:
	$(UV) run python src/openword/core_ingest.py
	@if [ ! -f "$(WIKTIONARY_JSON)" ]; then \
		echo "✗ Missing $(WIKTIONARY_JSON). Run 'make fetch-post-process-plus' after producing a Wiktextract JSON."; \
		exit 1; \
	fi
	$(UV) run python src/openword/wikt_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	$(UV) run python src/openword/export_wordlist.py

# Export trie to plain text wordlist for browser viewer
export-wordlist:
	$(UV) run python src/openword/export_wordlist.py

# Build compact binary trie for browser (requires wordlist.txt)
build-binary:
	@echo "→ Building binary trie for browser..."
	@if ! command -v pnpm &> /dev/null; then \
		echo "✗ pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@if [ ! -f "data/build/core/wordlist.txt" ]; then \
		echo "✗ wordlist.txt not found. Run 'make export-wordlist' first."; \
		exit 1; \
	fi
	@if [ ! -d "viewer/node_modules" ]; then \
		echo "→ Installing viewer dependencies..."; \
		cd viewer && pnpm install; \
	fi
	@cd viewer && pnpm run build-trie

package:
	$(UV) run python src/openword/manifest.py
	$(UV) run python src/openword/package_release.py

clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +

clean-viewer:
	rm -rf viewer/node_modules viewer/pnpm-lock.yaml viewer/data viewer/dist

scrub: clean
	rm -rf .venv \
		data/intermediate data/filtered data/build data/core data/plus \
		data/artifacts \
		ATTRIBUTION.md \
		MANIFEST.json \
		data/LICENSE \
		data/.limits-log.json

# Start local development server for trie viewer
start-server:
	@echo "→ Starting local server for trie viewer..."
	@if ! command -v pnpm &> /dev/null; then \
		echo "✗ pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@if [ ! -f "data/build/core/wordlist.txt" ]; then \
		echo "✗ wordlist.txt not found. Run 'make build-core' first."; \
		echo "  Or run: make export-wordlist"; \
		exit 1; \
	fi
	@if [ ! -d "viewer/node_modules" ]; then \
		echo "→ Installing viewer dependencies..."; \
		cd viewer && pnpm install; \
	fi
	@echo "→ Starting server from project root on http://localhost:8080/viewer/"
	@cd viewer && npx http-server .. -p 8080 -o /viewer/ --cors

# ===========================
# Inspection & Reporting
# ===========================

# Generate all inspection reports
reports:
	$(UV) run python tools/generate_reports.py

# Generate specific reports
report-raw:
	$(UV) run python tools/inspect_raw.py

report-pipeline:
	$(UV) run python tools/inspect_pipeline.py core
	$(UV) run python tools/inspect_pipeline.py plus

report-trie:
	$(UV) run python tools/inspect_trie.py core
	$(UV) run python tools/inspect_trie.py plus

report-metadata:
	$(UV) run python tools/inspect_metadata.py core
	$(UV) run python tools/inspect_metadata.py plus

report-compare:
	$(UV) run python tools/compare_distributions.py
