# Makefile (root) — uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

.PHONY: bootstrap venv deps devdeps fmt lint test clean distclean \
        fetch-core fetch-plus build-core build-plus check-limits

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

## Future phases (build pipelines)
build-core:
	@echo "Phase 5+: implement core ingest/build pipeline"

build-plus:
	@echo "Phase 6+: implement plus ingest/build pipeline"

## Cleaning
clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf '{}' +
	find . -name '*.egg-info' -type d -prune -exec rm -rf '{}' +

distclean: clean
	rm -rf .venv
