# Makefile (root) - uv-only Python workflow
# Use uv for ALL Python-related actions. No direct python/pip.

SHELL := /bin/bash
UV ?= uv
PY_VERSION ?= 3.11

WIKTIONARY_DUMP := data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
WIKTIONARY_JSON := data/intermediate/plus/wikt.jsonl
CORE_TRIE := data/build/core/core.trie
CORE_WORDLIST := data/build/core/wordlist.txt
GAME_WORD_LIST := data/wordlists/game-words.txt
VULGAR_BLOCKLIST := data/wordlists/vulgar-blocklist.txt
KIDS_NOUNS_LIST := data/wordlists/kids-nouns.txt
ALL_PHRASES_LIST := data/wordlists/all-phrases.txt
IDIOMS_LIST := data/wordlists/idioms.txt
PREP_PHRASES_LIST := data/wordlists/prepositional-phrases.txt
CORE_META := data/build/core/core.meta.json
PLUS_META := data/build/plus/plus.meta.json
GAME_WORDS_CORE := data/game_words/words_core.txt
GAME_WORDS_CORE_SCORED := data/game_words/words_scored_core.txt
GAME_WORDS_CORE_REVIEW := data/game_words/review_core.md
GAME_WORDS_PLUS := data/game_words/words_plus.txt
GAME_WORDS_PLUS_SCORED := data/game_words/words_scored_plus.txt
GAME_WORDS_PLUS_REVIEW := data/game_words/review_plus.md
GAME_META_REPORT_CORE := reports/game_metadata_analysis_core.md
GAME_META_REPORT_PLUS := reports/game_metadata_analysis_plus.md

.PHONY: bootstrap venv deps fmt lint test clean clean-viewer scrub \
        fetch fetch-core fetch-plus build-wiktionary-json \
        build-core build-plus export-wordlist export-wordlist-filtered-w3 export-wordlist-filtered-w4 \
        export-wordlist-filtered-c50 export-wordlist-filtered-w3c50 build-binary package check-limits start-server \
        reports report-raw report-pipeline report-trie report-metadata report-compare \
        game-words analyze-game-metadata \
        build-wordlists export-wordlist-game export-wordlist-vulgar-blocklist export-wordlist-kids-nouns export-wordlist-phrases \
        analyze-enhanced-metadata report-frequency-analysis report-syllable-analysis report-wordnet-concreteness \
        report-labels analyze-local baseline-decompress \
        diagnose-scanner scanner-commit scanner-push

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

fetch: fetch-core fetch-plus

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

build: build-core build-plus

build-core:
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	$(UV) run python src/openword/export_wordlist.py

build-plus: fetch-plus build-wiktionary-json
	$(UV) run python src/openword/core_ingest.py
	$(UV) run python src/openword/wikt_ingest.py
	$(UV) run python src/openword/wordnet_enrich.py
	$(UV) run python src/openword/frequency_tiers.py
	$(UV) run python src/openword/merge_dedupe.py
	$(UV) run python src/openword/policy.py
	$(UV) run python src/openword/attribution.py
	$(UV) run python src/openword/trie_build.py
	$(UV) run python src/openword/export_wordlist.py

# File-based rule: generate wordlist from trie
$(CORE_WORDLIST): $(CORE_TRIE)
	$(UV) run python src/openword/export_wordlist.py

# Export trie to plain text wordlist for browser viewer
export-wordlist: $(CORE_WORDLIST)

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
build-binary: $(CORE_WORDLIST)
	@echo "Building binary trie for browser..."
	@if ! command -v pnpm &> /dev/null; then \
		echo "Error: pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@if [ ! -d "viewer/node_modules" ]; then \
		echo "Installing viewer dependencies..."; \
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
start-server: $(CORE_WORDLIST)
	@echo "Starting local server for trie viewer..."
	@if ! command -v pnpm &> /dev/null; then \
		echo "Error: pnpm not found. Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@if [ ! -d "viewer/node_modules" ]; then \
		echo "Installing viewer dependencies..."; \
		cd viewer && pnpm install; \
	fi
	@echo "Server starting at http://localhost:8080/viewer/"
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
$(GAME_WORDS_CORE) $(GAME_WORDS_CORE_SCORED) $(GAME_WORDS_CORE_REVIEW): $(CORE_META)
	@mkdir -p $(dir $(GAME_WORDS_CORE))
	$(UV) run python tools/filter_game_words.py \
		--distribution core \
		--output-wordlist $(GAME_WORDS_CORE) \
		--output-scored $(GAME_WORDS_CORE_SCORED) \
		--output-review $(GAME_WORDS_CORE_REVIEW)

$(GAME_WORDS_PLUS) $(GAME_WORDS_PLUS_SCORED) $(GAME_WORDS_PLUS_REVIEW): $(PLUS_META)
	@mkdir -p $(dir $(GAME_WORDS_PLUS))
	$(UV) run python tools/filter_game_words.py \
		--distribution plus \
		--output-wordlist $(GAME_WORDS_PLUS) \
		--output-scored $(GAME_WORDS_PLUS_SCORED) \
		--output-review $(GAME_WORDS_PLUS_REVIEW)

game-words: $(GAME_WORDS_CORE) $(GAME_WORDS_PLUS)

# Analyze metadata coverage for game filtering
$(GAME_META_REPORT_CORE): $(CORE_META)
	@mkdir -p $(dir $@)
	$(UV) run python tools/analyze_game_metadata.py core --output $@

$(GAME_META_REPORT_PLUS): $(PLUS_META)
	@mkdir -p $(dir $@)
	$(UV) run python tools/analyze_game_metadata.py plus --output $@

analyze-game-metadata: $(GAME_META_REPORT_CORE) $(GAME_META_REPORT_PLUS)

# ===========================
# Specialized Word Lists
# ===========================

# Build all specialized word lists
build-wordlists: $(GAME_WORD_LIST) $(VULGAR_BLOCKLIST) $(KIDS_NOUNS_LIST) $(ALL_PHRASES_LIST) $(IDIOMS_LIST) $(PREP_PHRASES_LIST)

# Game-appropriate words (single words, common POS, no special characters)
$(GAME_WORD_LIST): $(WIKTIONARY_JSON)
	@mkdir -p $(dir $@)
	jq -r 'select( \
		.is_phrase == false and \
		(.pos | contains(["noun", "verb", "adjective", "adverb"])) and \
		(.word | test("^[a-z]+$$")) and \
		(.word | length >= 3) and \
		(.labels.temporal | length == 0) \
	) | .word' "$<" | sort -u > $@
	@echo "Game words: $$(wc -l < $@) entries"

export-wordlist-game: $(GAME_WORD_LIST)

# Vulgar/offensive word blocklist
$(VULGAR_BLOCKLIST): $(WIKTIONARY_JSON)
	@mkdir -p $(dir $@)
	jq -r 'select( \
		.labels.register | \
		contains(["vulgar"]) or contains(["offensive"]) or contains(["derogatory"]) \
	) | .word' "$<" | sort -u > $@
	@echo "Blocklist: $$(wc -l < $@) entries"

export-wordlist-vulgar-blocklist: $(VULGAR_BLOCKLIST)

# Kids' concrete nouns (animals, food, toys, etc.)
$(KIDS_NOUNS_LIST): $(WIKTIONARY_JSON)
	@mkdir -p $(dir $@)
	jq -r 'select( \
		(.pos | contains(["noun"])) and \
		.is_phrase == false and \
		(.word | test("^[a-z]+$$")) and \
		(.word | length >= 3 and length <= 10) and \
		(.labels.categories | any( \
			test("animal|food|plant|toy|color|colour|body|furniture|tool|vehicle|clothing") \
		)) \
	) | .word' "$<" | sort -u > $@
	@echo "Kids nouns: $$(wc -l < $@) entries"

export-wordlist-kids-nouns: $(KIDS_NOUNS_LIST)

# Phrase types (all phrases, idioms, prepositional phrases)
$(ALL_PHRASES_LIST) $(IDIOMS_LIST) $(PREP_PHRASES_LIST): $(WIKTIONARY_JSON)
	@mkdir -p $(dir $(ALL_PHRASES_LIST))
	jq -r 'select(.pos | contains(["phrase"])) | .word' "$<" \
		| sort -u > $(ALL_PHRASES_LIST)
	jq -r 'select(.labels.categories | any(contains("idiom"))) | .word' "$<" \
		| sort -u > $(IDIOMS_LIST)
	jq -r 'select(.labels.categories | any(contains("prepositional phrases"))) | .word' "$<" \
		| sort -u > $(PREP_PHRASES_LIST)
	@echo "All phrases: $$(wc -l < $(ALL_PHRASES_LIST)) entries"
	@echo "Idioms: $$(wc -l < $(IDIOMS_LIST)) entries"
	@echo "Prep phrases: $$(wc -l < $(PREP_PHRASES_LIST)) entries"

export-wordlist-phrases: $(ALL_PHRASES_LIST) $(IDIOMS_LIST) $(PREP_PHRASES_LIST)

# ===========================
# Enhanced Metadata Analysis (Phase 3)
# ===========================

# Run all enhanced metadata analysis
analyze-enhanced-metadata: report-frequency-analysis report-syllable-analysis report-wordnet-concreteness
	@echo "Enhanced metadata analysis complete"

# Analyze frequency data structure and tiers
report-frequency-analysis: deps data/raw/plus/en_50k.txt
	@mkdir -p reports
	$(UV) run python tools/analyze_frequency_data.py data/raw/plus/en_50k.txt

# Analyze syllable data availability in Wiktionary
report-syllable-analysis: deps $(WIKTIONARY_DUMP)
	@mkdir -p reports
	$(UV) run python tools/analyze_syllable_data.py "$(WIKTIONARY_DUMP)" 10000

# Analyze WordNet for concrete/abstract noun classification
report-wordnet-concreteness: deps data/raw/plus/english-wordnet-2024.tar.gz
	@mkdir -p reports
	$(UV) run python tools/analyze_wordnet_concreteness.py data/raw/plus/english-wordnet-2024.tar.gz

# ===========================
# Local Analysis (run locally with full Wiktionary dump)
# ===========================

# Build Wiktionary JSONL using lightweight scanner parser (file-based dependency)
$(WIKTIONARY_JSON): $(WIKTIONARY_DUMP)
	@echo "Extracting Wiktionary..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		"$(WIKTIONARY_JSON)"

# Convenience target (will only rebuild if output missing or input newer)
build-wiktionary-json: deps $(WIKTIONARY_JSON)

# Generate label statistics from extracted Wiktionary data
report-labels: deps $(WIKTIONARY_JSON)
	$(UV) run python tools/report_label_statistics.py "$(WIKTIONARY_JSON)"

# Run full local analysis workflow (extract + statistics)
analyze-local: build-wiktionary-json report-labels
	@echo "Local analysis complete"

# Baseline decompression benchmark (no XML parsing)
baseline-decompress: deps $(WIKTIONARY_DUMP)
	$(UV) run python tools/baseline_decompress.py "$(WIKTIONARY_DUMP)"

# ===========================
# Scanner Parser Diagnostics
# ===========================

# Run scanner parser in diagnostic mode to identify issues
diagnose-scanner: deps $(WIKTIONARY_DUMP)
	@mkdir -p reports
	$(UV) run python tools/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		/tmp/scanner_diagnostic.jsonl \
		--diagnostic reports/scanner_diagnostic.txt
