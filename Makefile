# Makefile (root) — uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

WIKTIONARY_DUMP := data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := data/intermediate/plus/wikt.jsonl

.PHONY: bootstrap venv deps devdeps fmt lint test clean distclean \
        fetch-core fetch-plus fetch-post-process-core fetch-post-process-plus \
        build-core build-plus package check-limits

## Bootstrap local dev environment (idempotent)
bootstrap: venv deps devdeps
	@echo "Bootstrap complete."

## Create/refresh project venv
venv:
	$(UV) venv --python $(PY_VERSION)
	@$(UV) run python -c "import sys; print('Python', sys.version)"
	@echo "Venv: .venv created/updated"

## Install project runtime dependencies from pyproject
deps:
	$(UV) pip install -e .

## Install dev-only tooling
devdeps:
	$(UV) pip install -e .[dev]

## Code quality
fmt:
	$(UV) run black .

lint:
	$(UV) run ruff check .

## Tests (placeholder until implemented)
test:
	$(UV) run pytest -q || true

## Phase 1: Guardrails
check-limits:
	@bash scripts/sys/limits.sh check

## Phase 2: Fetch core sources (PD/permissive only)
fetch-core:
	@echo "→ Fetching CORE distribution sources..."
	@bash scripts/fetch/fetch_enable.sh
	@bash scripts/fetch/fetch_eowl.sh
	@bash scripts/sys/limits.sh update
	@echo "✓ CORE sources fetched to data/raw/core"

## Phase 3: Fetch plus sources (CC-BY-SA enrichments)
fetch-plus:
	@echo "→ Fetching PLUS distribution sources..."
	@bash scripts/fetch/fetch_wiktionary.sh
	@bash scripts/fetch/fetch_wordnet.sh
	@bash scripts/fetch/fetch_frequency.sh
	@bash scripts/sys/limits.sh update
	@echo "✓ PLUS sources fetched to data/raw/plus"

## Phase 3½: Post-process fetched sources (e.g., Wiktionary dump → JSONL)
fetch-post-process-core: deps
	@echo "→ Post-processing CORE distribution sources..."
	@echo "   No additional post-processing required for core sources."

fetch-post-process-plus: deps
	@echo "→ Post-processing PLUS distribution sources (wiktextract)..."
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run wiktwords "$(WIKTIONARY_DUMP)" \
		--out "$(WIKTIONARY_JSON)" \
		--language English \
		--language Translingual \
		--all
	@echo "✓ Wiktionary JSON written to $(WIKTIONARY_JSON)"

## Build pipelines (Phases 5-12)
build-core:
	@echo "→ Building CORE distribution..."
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	@echo "✓ CORE build complete: data/build/core/"

build-plus:
	@echo "→ Building PLUS distribution..."
	$(UV) run python src/openword/core_ingest.py
	@if [ ! -f "$(WIKTIONARY_JSON)" ]; then \
		echo "↻ $(WIKTIONARY_JSON) not found – running fetch-post-process-plus..."; \
		$(MAKE) fetch-post-process-plus; \
	fi
	$(UV) run python src/openword/wikt_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	@echo "✓ PLUS build complete: data/build/plus/"

## Package releases (Phase 16)
package:
	@echo "→ Packaging releases..."
	$(UV) run python src/openword/manifest.py
	$(UV) run python src/openword/package_release.py
	@echo "✓ Release packages: data/artifacts/releases/"

## Cleaning
clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +

distclean: clean
	rm -rf .venv
