"""
openword.scanner.v2 - Schema-driven Wiktionary scanner

This package provides a v2 scanner that reads declarative schema files
from schema/core/ and schema/bindings/ to process Wiktionary XML dumps.

Modules:
    scanner: Main entry point and CLI
    schema: Schema loading and dataclasses
    cdaload: Configuration-Driven Architecture loader
    evidence: Evidence extraction from wikitext
    rules: Rule engine for producing output entries

Usage:
    owscan INPUT OUTPUT --schema-core PATH --schema-bindings PATH

Or:
    python -m openword.scanner.v2.scanner INPUT OUTPUT --schema-core PATH --schema-bindings PATH
"""

from openword.scanner.v2.scanner import main

__all__ = ['main']
