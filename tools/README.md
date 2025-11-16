# Inspection Tools

This directory contains tools for inspecting and analyzing the Openword Lexicon data at various stages of the pipeline.

## Purpose

These tools serve multiple purposes:
- **Sanity checks** - Verify data quality and pipeline correctness
- **Data exploration** - Understand the contents and structure of datasets
- **Documentation** - Generate reports that can be committed to version control
- **Debugging** - Identify issues in the pipeline or data sources

## Tools

### `inspect_raw.py`
Samples from the original downloaded datasets (ENABLE, EOWL, Wiktionary, WordNet, frequency data).

**Generates:** `reports/raw_data_inspection.md`

```bash
uv run python tools/inspect_raw.py
# or
make report-raw
```

### `inspect_pipeline.py`
Analyzes intermediate stages of the pipeline, showing how data transforms at each step.

**Generates:** `reports/pipeline_inspection_{core,plus}.md`

```bash
uv run python tools/inspect_pipeline.py core
uv run python tools/inspect_pipeline.py plus
# or
make report-pipeline
```

### `inspect_trie.py`
Analyzes the final MARISA trie structure, including word counts, lookups, and prefix searches.

**Generates:** `reports/trie_inspection_{core,plus}.md`

```bash
uv run python tools/inspect_trie.py core
uv run python tools/inspect_trie.py plus
# or
make report-trie
```

### `analyze_metadata.py`
Comprehensive metadata analysis consolidating multiple analyses:
- Frequency tier distribution and coverage
- Source distribution (ENABLE, EOWL, Wiktionary)
- Label coverage (register, domain, region, temporal)
- Game-specific filtering analysis (concreteness, POS tags)
- Sense-based format recommendations
- Data quality insights and filtering recommendations

**Generates:** `reports/metadata_analysis_{core,plus}.md`

```bash
uv run python tools/analyze_metadata.py core
uv run python tools/analyze_metadata.py plus
# or
make report-metadata
```

**Note:** This replaces the previous separate scripts (`inspect_metadata.py`, `analyze_game_metadata.py`, `report_label_statistics_built.py`) which have been consolidated into this comprehensive analysis.

### `compare_distributions.py`
Compares the core and plus distributions, identifying unique words and metadata differences.

**Generates:** `reports/distribution_comparison.md`

```bash
uv run python tools/compare_distributions.py
# or
make report-compare
```

### `generate_reports.py`
Master script that runs all inspection tools and generates a complete set of reports.

**Generates:** All reports listed above + `reports/README.md`

```bash
uv run python tools/generate_reports.py
# or
make reports
```

## Recent Improvements (2025)

**Report Consolidation:**
- Merged metadata exploration, game analysis, and label statistics into comprehensive metadata reports
- Reduced from 12 generating scripts to 6 (~50% reduction)
- Reduced from 21 report files to ~11 files
- No duplication, better organization

**Pipeline Enhancements:**
- **Fixed label data loss:** Labels are now properly preserved from Wiktionary extraction through the entire pipeline (was 0.0% coverage, now 11%+)
- **Added syllable extraction:** Wiktionary scanner parser now extracts syllable counts from hyphenation templates, handling complex formats like language codes and alternatives
- **Sense-based format analysis:** New reports include recommendations for sense-level data representation (e.g., `crow.n.1`, `crow.v.1`)

**Removed Obsolete Reports:**
- `analyze_frequency_data.py` - Frequency tiers already implemented
- `analyze_wordnet_concreteness.py` - WordNet enrichment already operational
- `analyze_syllable_data.py` - Syllable extraction now in scanner parser
- Orphaned reports without source scripts

## Generated Reports

All reports are written to the `reports/` directory as markdown files. These files are committed to version control, allowing you to:
- Track changes over time
- Share findings with collaborators
- Document the data at specific points in development

## Usage Workflow

1. **After fetching data:**
   ```bash
   make report-raw
   ```
   Verify downloads are complete and formatted correctly.

2. **After building distributions:**
   ```bash
   make reports
   ```
   Generate comprehensive analysis of the entire pipeline.

3. **When debugging:**
   Run individual tools to focus on specific stages:
   ```bash
   make report-pipeline  # Check intermediate stages
   make report-trie      # Verify final trie structure
   ```

4. **Commit and share:**
   ```bash
   git add reports/
   git commit -m "Add inspection reports for build X"
   ```

## Customization

All tools use `random.seed(42)` for reproducible sampling. To get different samples, modify the seed value in each tool.

The number of samples can be adjusted by changing the `n` parameter in function calls (typically 5-10 samples per dataset).

## Dependencies

These tools require the same dependencies as the main pipeline:
- Python 3.11+
- marisa-trie
- Standard library modules (json, random, pathlib, collections)

All dependencies are managed via `uv` and the project's `pyproject.toml`.
