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

## Recent Improvements

**Unified Build (2025):**
- Unified build integrating all sources (ENABLE, EOWL, Wiktionary, WordNet)
- Per-word license tracking via `license_sources` field
- Language-based organization (English-only currently)
- Safe defaults philosophy for missing metadata
- Runtime filtering support (child-safe, region-specific, profanity, etc.)
- Fixed syllable data loss pipeline issue
- Added missing POS tag detection
- Enhanced analysis with source-specific sampling

---

**Generation:** Run `make report-en` or `uv run python tools/generate_reports.py`
