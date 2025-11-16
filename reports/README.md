# Openword Lexicon - Inspection Reports

This directory contains automated inspection reports for the Openword Lexicon project.

## Available Reports

### Raw Data Analysis
- [Raw Data Inspection](raw_data_inspection.md) - Samples from downloaded datasets

### Pipeline Analysis
- [Pipeline Inspection (Core)](pipeline_inspection_core.md) - Core distribution pipeline stages
- [Pipeline Inspection (Plus)](pipeline_inspection_plus.md) - Plus distribution pipeline stages

### Trie Analysis
- [Trie Inspection (Core)](trie_inspection_core.md) - Core trie structure and tests
- [Trie Inspection (Plus)](trie_inspection_plus.md) - Plus trie structure and tests

### Comprehensive Metadata Analysis
- [Metadata Analysis (Core)](metadata_analysis_core.md) - Comprehensive metadata, labels, and filtering analysis
- [Metadata Analysis (Plus)](metadata_analysis_plus.md) - Comprehensive metadata, labels, and filtering analysis

**Note:** These consolidated reports include:
- Frequency tier distribution
- Source distribution (ENABLE, EOWL, Wiktionary)
- Label coverage (register, domain, region, temporal)
- Game-specific filtering analysis (concreteness, POS tags)
- Sense-based format recommendations
- Filtering recommendations and data quality insights

### Distribution Comparison
- [Distribution Comparison](distribution_comparison.md) - Core vs Plus analysis

---

## Recent Improvements

**Report Consolidation (2025):**
- Merged metadata exploration, game analysis, and label statistics into comprehensive metadata reports
- Fixed label data loss pipeline issue - labels now preserved from Wiktionary extraction
- Added syllable extraction to Wiktionary scanner parser (handles complex hyphenation formats)
- Removed obsolete exploratory reports (frequency analysis, WordNet concreteness)
- Added sense-based intermediate format analysis and recommendations

---

**Generation:** Run `make reports` or `uv run python tools/generate_reports.py`
