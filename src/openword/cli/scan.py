#!/usr/bin/env python3
"""
owscan - Wiktionary scanner CLI.

Parses Wiktionary XML dumps to extract lexicon entries using the
Configuration-Driven Architecture (CDA) v2 scanner.

Usage:
    owscan INPUT OUTPUT [options]

Example:
    owscan data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \\
           data/intermediate/en-wikt-v2.jsonl \\
           --schema-core schema/core \\
           --schema-bindings schema/bindings
"""

import sys


def main() -> int:
    """Entry point for owscan CLI."""
    # Import here to avoid circular imports and speed up CLI startup
    from openword.scanner.v2.scanner import main as scanner_main
    return scanner_main()


if __name__ == "__main__":
    sys.exit(main())
