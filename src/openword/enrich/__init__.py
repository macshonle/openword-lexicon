"""
Enrichment pipeline for lexicon entries.

This package provides data enrichment from external sources:
- frequency: Word frequency tiers from OpenSubtitles corpus
- concreteness: Brysbaert et al. concreteness ratings
- aoa: Kuperman et al. Age of Acquisition ratings

The pipeline module orchestrates all enrichments in a single pass.
"""

from openword.enrich.pipeline import (
    process_file,
    get_pipeline_config,
    get_field_schemas,
)

__all__ = [
    "process_file",
    "get_pipeline_config",
    "get_field_schemas",
]
