"""
wiktionary_scanner_python - Python implementation of Wiktionary scanner

This package provides the Python reference implementation for parsing
Wiktionary XML dumps. A Rust implementation with identical output is
available at tools/wiktionary-scanner-rust/ for production use.

Modules:
    scanner: Core XML parsing and entry extraction
    categories: Category computation (ported from Wiktionary Lua modules)

Usage:
    from wiktionary_scanner_python.scanner import (
        BZ2StreamReader,
        scan_pages,
    )
    from wiktionary_scanner_python.categories import (
        CategoryBuilder,
        is_phrasal_verb,
    )

Note: Most imports should be done directly from the submodules rather than
from this package, as the scanner module has many exports that are used
selectively by different tools.
"""

# Minimal package-level exports - import directly from submodules for more
