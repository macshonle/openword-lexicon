# Openword Lexicon - Inspection Reports

This directory contains automated inspection reports for the Openword Lexicon project.

## Available Reports

### Raw Data
- [Raw Data Inspection](raw_data_inspection.md) - Samples from downloaded datasets

### Pipeline Analysis
- [Pipeline Inspection (Core)](pipeline_inspection_core.md) - Core distribution pipeline stages
- [Pipeline Inspection (Plus)](pipeline_inspection_plus.md) - Plus distribution pipeline stages

### Trie Analysis
- [Trie Inspection (Core)](trie_inspection_core.md) - Core trie structure and tests
- [Trie Inspection (Plus)](trie_inspection_plus.md) - Plus trie structure and tests

### Metadata Exploration
- [Metadata Exploration (Core)](metadata_exploration_core.md) - Core metadata analysis
- [Metadata Exploration (Plus)](metadata_exploration_plus.md) - Plus metadata analysis

### Distribution Comparison
- [Distribution Comparison](distribution_comparison.md) - Core vs Plus analysis

---

**Generation:** Run `make reports` or `uv run python tools/generate_reports.py`
