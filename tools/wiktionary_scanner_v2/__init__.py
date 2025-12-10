"""
wiktionary_scanner_v2 - Schema-driven Wiktionary scanner

This package provides a v2 scanner that reads declarative schema files
from schema/core/ and schema/bindings/ to process Wiktionary XML dumps.

Modules:
    scanner: Main entry point and CLI
    schema: Schema loading and dataclasses

Usage:
    python -m wiktionary_scanner_v2.scanner INPUT OUTPUT --schema-core PATH --schema-bindings PATH
"""
