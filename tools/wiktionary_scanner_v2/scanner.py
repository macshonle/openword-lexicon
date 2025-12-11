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
from .stats import (
    ScannerStats,
    extract_senseids,
    extract_etymology_sources,
    is_domain_label,
)


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

    parser.add_argument(
        "--stats",
        type=Path,
        default=None,
        help="Output path for statistics JSON file (optional)",
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
    if args.stats:
        print(f"  Stats:  {args.stats}")
    if args.limit:
        print(f"  Limit:  {args.limit} entries")

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Basic statistics (for summary output)
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

    # Detailed statistics collector (for JSON output)
    detailed_stats = ScannerStats() if args.stats else None

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

                # Record page for detailed stats
                if detailed_stats:
                    detailed_stats.record_page()

                    # Extract senseids from raw page text
                    for senseid_value in extract_senseids(result.text):
                        detailed_stats.record_senseid(senseid_value)

                    # Extract etymology sources from raw page text
                    for source_lang in extract_etymology_sources(result.text):
                        detailed_stats.record_etymology_source(source_lang)

                # Extract evidence and apply rules
                extraction_result = extract_evidence_with_unknowns(
                    result.title,
                    result.text,
                    is_ignored_header=config.is_ignored_header,
                    pos_headers=config.pos_headers,
                    definition_marker_pattern=config.definition_marker_pattern,
                    parse_definition_marker=config.parse_definition_marker,
                )

                # Track unknown headers
                for header in extraction_result.unknown_headers:
                    unknown_headers[header.lower()] += 1
                    if detailed_stats:
                        detailed_stats.record_unknown_header(header)

                # Collect entries for this page into an append-only ordered set
                # (deduplicate by JSON string, first appearance wins)
                seen_json: set[str] = set()
                page_entries: list[str] = []

                for evidence in extraction_result.evidence:
                    entry = apply_rules(evidence, config)

                    if entry is None:
                        stats["entries_filtered"] += 1
                        if detailed_stats:
                            detailed_stats.record_filtered_entry()
                        continue

                    # Record detailed stats for this entry
                    if detailed_stats:
                        # Record template usage
                        for template in evidence.head_templates:
                            detailed_stats.record_template(template.name)
                        for template in evidence.etymology_templates:
                            detailed_stats.record_template(template.name)
                            detailed_stats.record_morphology_template(template.name)
                        if evidence.inflection_template:
                            detailed_stats.record_template(evidence.inflection_template.name)
                            detailed_stats.record_inflection_template(evidence.inflection_template.name)
                        if evidence.altform_template:
                            detailed_stats.record_template(evidence.altform_template.name)
                            detailed_stats.record_altform_template(evidence.altform_template.name)

                        # Record labels and check for domain labels
                        for label in evidence.labels:
                            if is_domain_label(label):
                                detailed_stats.record_domain_label(label)
                            # Check if label mapped to a tag or domain
                            label_lower = label.lower()
                            if (label_lower not in config.label_to_tag and
                                label_lower not in config.label_to_domain):
                                detailed_stats.record_unmapped_label(label)

                        # Compute spelling region from spelling labels
                        spelling_region = None
                        for label in evidence.spelling_labels:
                            if label in config.label_to_tag:
                                # Check if it maps to a region tag like ENUS, ENGB
                                tag = config.label_to_tag[label]
                                if tag.startswith("EN"):
                                    spelling_region = tag
                                    break

                        # Record entry-level stats
                        detailed_stats.record_entry(
                            pos=entry.pos,
                            flags=entry.codes,
                            tags=entry.codes,  # codes contains both flags and tags
                            labels=evidence.labels,
                            categories=evidence.categories,
                            has_nsyll=entry.nsyll is not None,
                            has_lemma=entry.lemma is not None,
                            has_morphology=entry.morphology is not None,
                            def_level=evidence.definition_level,
                            def_type=evidence.definition_type,
                            spelling_region=spelling_region,
                        )

                    # Convert to JSON string for deduplication (compact, no whitespace)
                    entry_dict = entry_to_dict(entry)
                    entry_json = json.dumps(entry_dict, ensure_ascii=False, separators=(",", ":"))

                    # Only keep first occurrence of each unique entry
                    if entry_json not in seen_json:
                        seen_json.add(entry_json)
                        page_entries.append(entry_json)

                # Write deduplicated entries for this page
                for entry_json in page_entries:
                    out.write(entry_json + "\n")
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

    # Write detailed statistics if requested
    if detailed_stats and args.stats:
        args.stats.parent.mkdir(parents=True, exist_ok=True)
        detailed_stats.write_to_file(str(args.stats))
        print(f"\nStatistics written to: {args.stats}")

        # Print some highlights from the stats
        stats_dict = detailed_stats.to_dict()
        print(f"\nStatistics highlights:")
        print(f"  Unique labels:     {stats_dict['label_frequencies']['total_unique']:,}")
        print(f"  Unmapped labels:   {stats_dict['unmapped_labels']['total_unique']:,}")
        print(f"  Domain labels:     {stats_dict['domain_labels']['total_unique']:,}")
        print(f"  Unique senseids:   {stats_dict['senseid']['total_unique']:,}")
        print(f"  Wikidata QIDs:     {stats_dict['senseid']['total_qids']:,}")
        print(f"  Unique categories: {stats_dict['categories']['total_unique']:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
