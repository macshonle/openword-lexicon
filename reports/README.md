# Openword Lexicon - Inspection Reports

This directory contains automated inspection reports for the Openword Lexicon project.

## Available Reports

### Comprehensive Metadata Analysis
- [Metadata Analysis (EN)](metadata_analysis_en.md) - Comprehensive metadata, labels, and filtering analysis

**Note:** This consolidated report includes:
- Frequency tier distribution
- Source distribution (ENABLE, EOWL, Wiktionary)
- Label coverage (register, domain, region, temporal)
- Game-specific filtering analysis (concreteness, POS tags, syllables)
- Sense-based format recommendations
- Filtering recommendations and data quality insights
- Representative samples from all data sources

---

## Pipeline Architecture

**Two-File Format (2025):**
- Normalized format with separate lexemes and senses files
- Word-level properties in `en-lexemes-enriched.jsonl`
- Sense-level properties in `en-senses.jsonl`
- Flat directory structure with language-prefixed filenames
- Safe defaults philosophy for missing metadata
- Runtime filtering support (child-safe, region-specific, profanity, etc.)

---

**Generation:** Run `make report-en` or `uv run python tools/generate_reports.py`
