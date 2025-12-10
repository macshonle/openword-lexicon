"""
v2 Wiktionary scanner - Configuration-Driven Architecture (CDA).

This scanner uses declarative YAML schema files to drive extraction,
making the mapping from Wiktionary signals to output codes explicit
and data-driven rather than hardcoded.

Architecture:
    1. Configuration Layer (cdaload.py) - loads schema + bindings
    2. Evidence Extraction Layer (evidence.py) - parses Wiktionary markup
    3. Rule Engine Layer (rules.py) - applies bindings to produce entries

Usage:
    python -m wiktionary_scanner_v2.scanner INPUT OUTPUT [options]

Example:
    python -m wiktionary_scanner_v2.scanner \
        data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        data/intermediate/en-wikt-v2.jsonl \
        --schema-core schema/core \
        --schema-bindings schema/bindings
"""

import argparse
import sys
from pathlib import Path

from .cdaload import load_binding_config, CodeValidationError


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="v2 Wiktionary scanner with Configuration-Driven Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input Wiktionary XML dump (.xml or .xml.bz2)",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Output JSONL file",
    )

    parser.add_argument(
        "--schema-core",
        type=Path,
        default=Path("schema/core"),
        help="Path to schema/core/ directory (default: schema/core)",
    )

    parser.add_argument(
        "--schema-bindings",
        type=Path,
        default=Path("schema/bindings"),
        help="Path to schema/bindings/ directory (default: schema/bindings)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit processing to first N entries (for testing)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate input file exists
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Load CDA configuration (schema + bindings)
    try:
        print(f"Loading CDA configuration...")
        print(f"  Core schema: {args.schema_core}")
        print(f"  Bindings:    {args.schema_bindings}")
        config = load_binding_config(args.schema_core, args.schema_bindings)
        print(f"\n{config.summary()}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except CodeValidationError as e:
        print(f"Schema validation error: {e}", file=sys.stderr)
        return 1

    # Show processing configuration
    print(f"\nProcessing:")
    print(f"  Input:  {args.input}")
    print(f"  Output: {args.output}")
    if args.limit:
        print(f"  Limit:  {args.limit} entries")

    # Placeholder: actual processing will be implemented in Phase 2-4
    print(f"\n[Placeholder] Would process {args.input} -> {args.output}")
    print("Phase 1 complete. Evidence extraction (Phase 2) not yet implemented.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
