# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

.PHONY: bootstrap venv deps devdeps fmt lint test clean distclean \
        fetch-core fetch-plus build-core build-plus check-limits

## Bootstrap local dev environment (idempotent)
bootstrap: venv deps devdeps
	@echo "Bootstrap complete."

## Create/refresh project venv with the requested interpreter
venv:
	$(UV) venv --python $(PY_VERSION)
	@$(UV) run python -c "import sys; print('Python', sys.version)"
	@echo "Venv: .venv created/updated"

## Install project runtime dependencies from pyproject
deps:
	$(UV) pip install -e .

## Install dev-only tooling (linters, tests)
devdeps:
	$(UV) pip install -e .[dev]

## Code style
fmt:
	$(UV) run black .

lint:
	$(UV) run ruff check .

## Tests (none yet; placeholder)
test:
	$(UV) run pytest -q || true

## Placeholders for later phases (wired up as scripts)
fetch-core:
	@echo "Phase 2: implement scripts to fetch PD sources into data/raw/core"

fetch-plus:
	@echo "Phase 3: implement scripts to fetch CC-BY-SA sources into data/raw/plus"

build-core:
	@echo "Phase 5+: implement core ingest/build pipeline"

build-plus:
	@echo "Phase 6+: implement plus ingest/build pipeline"

## Guardrails stub (wired in Phase 1)
check-limits:
	@echo "Phase 1: implement sys/limits.sh and hook here"

## Cleaning
clean:
	rm -rf build dist .pytest_cache .ruff_cache

distclean: clean
	rm -rf .venv
