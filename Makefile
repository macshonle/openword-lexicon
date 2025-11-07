# Makefile (root) — uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

WIKTIONARY_DUMP := data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := data/intermediate/plus/wikt.jsonl

.PHONY: bootstrap venv deps fmt lint test clean scrub \
        fetch-core fetch-plus fetch-post-process-core fetch-post-process-plus \
        build-core build-plus package check-limits

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
		--language English \
		--language Translingual \
		--all

build-core:
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py

build-plus:
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

package:
	$(UV) run python src/openword/manifest.py
	$(UV) run python src/openword/package_release.py

clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +

scrub: clean
	rm -rf .venv \
		data/intermediate data/filtered data/build data/core data/plus \
		data/artifacts \
		ATTRIBUTION.md \
		MANIFEST.json \
		data/LICENSE \
		data/.limits-log.json
