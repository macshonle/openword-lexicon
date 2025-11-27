#!/usr/bin/env python3
"""
Run complete benchmarks on full Wiktionary dataset.

Tests all parallelization strategies with varying thread counts:
- sequential (baseline)
- batch-parallel with 4, 8, 16, 32 threads
- channel-pipeline with 4, 8, 16, 32 threads
- two-phase with 4, 8, 16, 32 threads

Usage:
    # Run benchmarks
    uv run python tools/wiktionary-rust/scripts/run_full_benchmark.py \
        --input data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        --output-dir data/benchmark \
        --scanner tools/wiktionary-rust/target/release/wiktionary-rust

    # With caffeinate for overnight runs
    caffeinate -i uv run python tools/wiktionary-rust/scripts/run_full_benchmark.py \
        --input data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        --output-dir data/benchmark \
        --scanner tools/wiktionary-rust/target/release/wiktionary-rust

    # Validate outputs are identical
    uv run python tools/wiktionary-rust/scripts/run_full_benchmark.py \
        --output-dir data/benchmark \
        --validate-only
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Test matrix: (strategy, threads or None for sequential)
TEST_MATRIX = [
    ("sequential", None),
    ("batch-parallel", 4),
    ("batch-parallel", 8),
    ("batch-parallel", 16),
    ("batch-parallel", 32),
    ("channel-pipeline", 4),
    ("channel-pipeline", 8),
    ("channel-pipeline", 16),
    ("channel-pipeline", 32),
    ("two-phase", 4),
    ("two-phase", 8),
    ("two-phase", 16),
    ("two-phase", 32),
]


def parse_scanner_output(output: str) -> dict:
    """Parse stats from scanner output."""
    stats = {}

    # Parse key metrics from output
    patterns = {
        "pages_processed": r"Pages processed:\s*(\d+)",
        "words_written": r"Words written:\s*(\d+)",
        "senses_written": r"Senses written:\s*(\d+)",
        "special": r"Special pages:\s*(\d+)",
        "redirects": r"Redirects:\s*(\d+)",
        "dict_only": r"Dictionary-only terms:\s*(\d+)",
        "non_english": r"Non-English pages:\s*(\d+)",
        "non_latin": r"Non-Latin scripts:\s*(\d+)",
        "skipped": r"Skipped:\s*(\d+)",
        "time_minutes": r"Time:\s*(\d+)m",
        "time_seconds": r"Time:\s*\d+m\s*(\d+)s",
        "rate": r"Rate:\s*([\d.]+)\s*pages/sec",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            value = match.group(1)
            stats[key] = float(value) if "." in value else int(value)

    # Calculate total seconds
    if "time_minutes" in stats and "time_seconds" in stats:
        stats["total_seconds"] = stats["time_minutes"] * 60 + stats["time_seconds"]

    return stats


def run_benchmark(
    scanner: Path,
    input_file: Path,
    output_dir: Path,
    strategy: str,
    threads: int | None,
) -> dict:
    """Run a single benchmark configuration."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Build output filename
    if threads:
        output_name = f"en-wikt-{timestamp}-{strategy}-t{threads}.jsonl"
    else:
        output_name = f"en-wikt-{timestamp}-{strategy}.jsonl"

    output_file = output_dir / output_name

    # Build command
    cmd = [
        str(scanner),
        str(input_file),
        str(output_file),
        "--strategy", strategy,
    ]
    if threads:
        cmd.extend(["--threads", str(threads)])

    print(f"\n{'='*60}")
    print(f"Running: {strategy}" + (f" (threads={threads})" if threads else ""))
    print(f"Output: {output_file}")
    print(f"Command: {' '.join(cmd)}")
    print("="*60)

    # Run scanner
    start_time = datetime.now()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    end_time = datetime.now()

    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Parse stats
    stats = parse_scanner_output(result.stdout)
    stats["strategy"] = strategy
    stats["threads"] = threads
    stats["timestamp"] = timestamp
    stats["output_file"] = str(output_file)
    stats["return_code"] = result.returncode
    stats["wall_time_seconds"] = (end_time - start_time).total_seconds()

    return stats


def validate_outputs(output_dir: Path) -> bool:
    """Validate that all benchmark outputs are identical when sorted."""
    jsonl_files = sorted(output_dir.glob("en-wikt-*.jsonl"))

    if len(jsonl_files) < 2:
        print(f"Need at least 2 JSONL files to compare, found {len(jsonl_files)}")
        return False

    print(f"\nValidating {len(jsonl_files)} output files...")
    print("Computing checksums of sorted content...")

    checksums = {}
    for f in jsonl_files:
        print(f"  Processing: {f.name}...")
        # Sort lines and compute checksum
        with open(f) as fp:
            lines = sorted(fp.readlines())
        content = "".join(lines)
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        checksums[f.name] = checksum
        print(f"    Checksum: {checksum} ({len(lines)} lines)")

    # Check if all checksums match
    unique_checksums = set(checksums.values())
    if len(unique_checksums) == 1:
        print(f"\n✓ All {len(jsonl_files)} files are identical (checksum: {list(unique_checksums)[0]})")
        return True
    else:
        print(f"\n✗ Found {len(unique_checksums)} different outputs:")
        for checksum in unique_checksums:
            files = [name for name, cs in checksums.items() if cs == checksum]
            print(f"  {checksum}: {', '.join(files)}")
        return False


def generate_summary(results: list[dict], output_dir: Path, run_timestamp: str):
    """Generate summary report in markdown and JSON."""
    # JSON results
    json_file = output_dir / f"benchmark-results-{run_timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON results: {json_file}")

    # Markdown summary
    md_file = output_dir / f"benchmark-summary-{run_timestamp}.md"
    with open(md_file, "w") as f:
        f.write(f"# Benchmark Results - {run_timestamp}\n\n")
        f.write("## Summary\n\n")
        f.write("| Strategy | Threads | Pages/sec | Time | Senses |\n")
        f.write("|----------|---------|-----------|------|--------|\n")

        for r in results:
            threads = r.get("threads", "-") or "-"
            rate = r.get("rate", 0)
            time_str = f"{r.get('time_minutes', 0)}m {r.get('time_seconds', 0)}s"
            senses = r.get("senses_written", 0)
            f.write(f"| {r['strategy']} | {threads} | {rate:,.0f} | {time_str} | {senses:,} |\n")

        f.write("\n## Details\n\n")
        for r in results:
            f.write(f"### {r['strategy']}" + (f" (threads={r['threads']})" if r.get('threads') else "") + "\n\n")
            f.write(f"- **Output file:** `{r.get('output_file', 'N/A')}`\n")
            f.write(f"- **Pages processed:** {r.get('pages_processed', 0):,}\n")
            f.write(f"- **Words written:** {r.get('words_written', 0):,}\n")
            f.write(f"- **Senses written:** {r.get('senses_written', 0):,}\n")
            f.write(f"- **Rate:** {r.get('rate', 0):,.0f} pages/sec\n")
            f.write(f"- **Wall time:** {r.get('wall_time_seconds', 0):.1f}s\n")
            f.write("\n")

    print(f"Markdown summary: {md_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Run complete Rust scanner benchmarks on full Wiktionary dataset"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input XML file (.xml or .xml.bz2)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for benchmark results",
    )
    parser.add_argument(
        "--scanner",
        type=Path,
        help="Path to wiktionary-rust binary",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing outputs, don't run benchmarks",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        success = validate_outputs(args.output_dir)
        sys.exit(0 if success else 1)

    # Validate inputs for benchmark mode
    if not args.input:
        parser.error("--input is required for benchmark mode")
    if not args.scanner:
        parser.error("--scanner is required for benchmark mode")
    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")
    if not args.scanner.exists():
        parser.error(f"Scanner binary not found: {args.scanner}")

    run_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    print("="*60)
    print("Wiktionary Rust Scanner - Full Benchmark Suite")
    print("="*60)
    print(f"Input: {args.input}")
    print(f"Output dir: {args.output_dir}")
    print(f"Scanner: {args.scanner}")
    print(f"Test configurations: {len(TEST_MATRIX)}")
    print(f"Run timestamp: {run_timestamp}")

    results = []
    for i, (strategy, threads) in enumerate(TEST_MATRIX, 1):
        print(f"\n[{i}/{len(TEST_MATRIX)}] ", end="")
        stats = run_benchmark(
            scanner=args.scanner,
            input_file=args.input,
            output_dir=args.output_dir,
            strategy=strategy,
            threads=threads,
        )
        results.append(stats)

        if stats["return_code"] != 0:
            print(f"WARNING: Benchmark failed with return code {stats['return_code']}")

    # Generate summary
    generate_summary(results, args.output_dir, run_timestamp)

    print("\n" + "="*60)
    print("Benchmark suite complete!")
    print(f"Results in: {args.output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()
