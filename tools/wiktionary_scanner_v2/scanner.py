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
import json
import sys
import time
from pathlib import Path

from collections import Counter

from .cdaload import load_binding_config, CodeValidationError
from .evidence import BZ2StreamReader, scan_pages, extract_page, extract_evidence_with_unknowns
from .rules import apply_rules, entry_to_dict


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

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Statistics
    stats = {
        "pages_processed": 0,
        "pages_ok": 0,
        "pages_redirect": 0,
        "pages_special": 0,
        "pages_non_english": 0,
        "pages_dict_only": 0,
        "entries_written": 0,
        "entries_filtered": 0,
    }
    unknown_headers: Counter[str] = Counter()

    start_time = time.time()

    # Open input and output files
    if str(args.input).endswith(".bz2"):
        file_obj = BZ2StreamReader(args.input)
    else:
        file_obj = open(args.input, "rb")

    try:
        with file_obj as f, open(args.output, "w", encoding="utf-8") as out:
            # Process pages
            for page_xml in scan_pages(f):
                stats["pages_processed"] += 1

                # Extract page content
                result = extract_page(page_xml)

                # Track page status
                if result.status == "redirect":
                    stats["pages_redirect"] += 1
                    continue
                elif result.status == "special":
                    stats["pages_special"] += 1
                    continue
                elif result.status == "non_english":
                    stats["pages_non_english"] += 1
                    continue
                elif result.status == "dict_only":
                    stats["pages_dict_only"] += 1
                    continue
                elif result.status != "ok" or not result.text:
                    continue

                stats["pages_ok"] += 1

                # Extract evidence and apply rules
                extraction_result = extract_evidence_with_unknowns(
                    result.title,
                    result.text,
                    is_ignored_header=config.is_ignored_header,
                    pos_headers=config.pos_headers,
                )

                # Track unknown headers
                for header in extraction_result.unknown_headers:
                    unknown_headers[header.lower()] += 1

                for evidence in extraction_result.evidence:
                    entry = apply_rules(evidence, config)

                    if entry is None:
                        stats["entries_filtered"] += 1
                        continue

                    # Write entry
                    entry_dict = entry_to_dict(entry)
                    out.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")
                    stats["entries_written"] += 1

                    # Check limit
                    if args.limit and stats["entries_written"] >= args.limit:
                        print(f"\nReached limit of {args.limit} entries")
                        break

                # Check limit (outer loop)
                if args.limit and stats["entries_written"] >= args.limit:
                    break

                # Progress update every 10000 pages
                if stats["pages_processed"] % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = stats["pages_processed"] / elapsed if elapsed > 0 else 0
                    print(
                        f"  Progress: {stats['pages_processed']:,} pages, "
                        f"{stats['entries_written']:,} entries, "
                        f"{rate:.0f} pages/sec"
                    )

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    # Print summary
    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Pages processed:  {stats['pages_processed']:,}")
    print(f"  Pages OK:         {stats['pages_ok']:,}")
    print(f"  Redirects:        {stats['pages_redirect']:,}")
    print(f"  Special pages:    {stats['pages_special']:,}")
    print(f"  Non-English:      {stats['pages_non_english']:,}")
    print(f"  Dict-only:        {stats['pages_dict_only']:,}")
    print(f"  Entries written:  {stats['entries_written']:,}")
    print(f"  Entries filtered: {stats['entries_filtered']:,}")
    print(f"  Time:             {elapsed_min}m {elapsed_sec}s")
    if elapsed > 0:
        print(f"  Rate:             {stats['pages_processed'] / elapsed:.0f} pages/sec")
    print("=" * 60)

    # Report unknown headers
    if unknown_headers:
        total_unknown = sum(unknown_headers.values())
        print(f"\nUnknown headers ({total_unknown:,} occurrences, {len(unknown_headers)} unique):")
        # Show top 20 by count
        for header, count in unknown_headers.most_common(20):
            print(f"  {count:6,}  {header}")
        if len(unknown_headers) > 20:
            remaining = len(unknown_headers) - 20
            print(f"  ... and {remaining} more unique headers")

    return 0


if __name__ == "__main__":
    sys.exit(main())
