# Makefile (root) — uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

WIKTIONARY_DUMP := data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := data/intermediate/plus/wikt.jsonl

.PHONY: bootstrap venv deps fmt lint test clean clean-viewer scrub \
        fetch fetch-core fetch-plus fetch-post-process-plus fetch-simple fetch-scanner \
        build-core build-plus export-wordlist export-wordlist-filtered-w3 export-wordlist-filtered-w4 \
        export-wordlist-filtered-c50 export-wordlist-filtered-w3c50 build-binary package check-limits start-server \
        reports report-raw report-pipeline report-trie report-metadata report-compare \
        game-words analyze-game-metadata \
        audit-wiktionary report-labels analyze-local baseline-decompress \
        diagnose-scanner scanner-commit scanner-push

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

# Export with filters (plus distribution)
export-wordlist-filtered-w3:
	$(UV) run python src/openword/export_wordlist_filtered.py --distribution plus --max-words 3

export-wordlist-filtered-w4:
	$(UV) run python src/openword/export_wordlist_filtered.py --distribution plus --max-words 4

export-wordlist-filtered-c50:
	$(UV) run python src/openword/export_wordlist_filtered.py --distribution plus --max-chars 50

export-wordlist-filtered-w3c50:
	$(UV) run python src/openword/export_wordlist_filtered.py --distribution plus --max-words 3 --max-chars 50

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

# ===========================
# Game Word Filtering
# ===========================

# Filter words suitable for games (20 Questions, etc.)
game-words:
	$(UV) run python tools/filter_game_words.py --distribution core
	$(UV) run python tools/filter_game_words.py --distribution plus

# Analyze metadata coverage for game filtering
analyze-game-metadata:
	$(UV) run python tools/analyze_game_metadata.py core
	$(UV) run python tools/analyze_game_metadata.py plus

# ===========================
# Local Analysis (run locally with full Wiktionary dump)
# ===========================

# Fast Wiktionary extraction using simple streaming parser (alternative to wiktextract)
fetch-simple: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@echo "→ Extracting Wiktionary with simple streaming parser..."
	@echo "  (10-30 minutes for full dump, progress shown every 5k entries)"
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/prototypes/wiktionary_simple_parser.py \
		"$(WIKTIONARY_DUMP)" \
		"$(WIKTIONARY_JSON)"
	@echo "✓ Extraction complete: $(WIKTIONARY_JSON)"

# Fast Wiktionary extraction using lightweight scanner (even faster alternative)
fetch-scanner: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@echo "→ Extracting Wiktionary with lightweight scanner parser..."
	@echo "  (No full XML parsing - just string scanning for <page> boundaries)"
	@echo "  (Expected: 5-15 minutes for full dump)"
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/prototypes/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		"$(WIKTIONARY_JSON)"
	@echo "✓ Extraction complete: $(WIKTIONARY_JSON)"

# Audit Wiktionary extraction approach (validates simple parser on 10k sample)
audit-wiktionary: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@echo "→ Auditing Wiktionary extraction approach..."
	@echo "  (sampling 10,000 pages to validate approach)"
	$(UV) run python tools/audit_wiktionary_extraction.py \
		"$(WIKTIONARY_DUMP)" \
		--sample-size 10000
	@echo ""
	@echo "✓ Audit complete. Review reports:"
	@echo "  reports/wiktionary_audit.md"
	@echo "  reports/wiktionary_samples.json"
	@echo ""
	@echo "Commit these reports to version control for review."

# Generate label statistics from extracted Wiktionary data
report-labels: deps
	@if [ ! -f "$(WIKTIONARY_JSON)" ]; then \
		echo "✗ Missing $(WIKTIONARY_JSON). Run 'make fetch-simple' first."; \
		exit 1; \
	fi
	@echo "→ Generating label statistics report..."
	$(UV) run python tools/report_label_statistics.py "$(WIKTIONARY_JSON)"
	@echo ""
	@echo "✓ Statistics complete. Review reports:"
	@echo "  reports/label_statistics.md"
	@echo "  reports/label_examples.json"
	@echo ""
	@echo "Commit these reports to version control for review."

# Run full local analysis workflow (audit + extract + statistics)
analyze-local: audit-wiktionary fetch-simple report-labels
	@echo ""
	@echo "=========================================="
	@echo "✓ Local analysis complete!"
	@echo "=========================================="
	@echo ""
	@echo "Generated reports (commit to version control):"
	@echo "  reports/wiktionary_audit.md"
	@echo "  reports/wiktionary_samples.json"
	@echo "  reports/label_statistics.md"
	@echo "  reports/label_examples.json"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Review reports: less reports/wiktionary_audit.md"
	@echo "  2. Commit reports: git add reports/*.md reports/*.json && git commit"
	@echo "  3. Build distribution: make build-plus"
	@echo "  4. Test filters: uv run python tools/filter_words.py --use-case wordle"
	@echo ""
	@echo "See docs/LOCAL_ANALYSIS.md for detailed workflow."

# Baseline decompression benchmark (no XML parsing)
baseline-decompress: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@echo "→ Running baseline decompression benchmark..."
	@echo "  (This shows pure decompression speed without XML parsing)"
	@echo ""
	$(UV) run python tools/baseline_decompress.py "$(WIKTIONARY_DUMP)"

# ===========================
# Scanner Parser Diagnostics
# ===========================

# Run scanner parser in diagnostic mode to identify issues
diagnose-scanner: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@mkdir -p reports
	@echo "→ Running diagnostic scan..."
	@$(UV) run python tools/prototypes/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		/tmp/scanner_diagnostic.jsonl \
		--diagnostic 2>&1 | tee reports/scanner_diagnostic.txt
	@echo ""
	@echo "✓ Report saved to: reports/scanner_diagnostic.txt"
