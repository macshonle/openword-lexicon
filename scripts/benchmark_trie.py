#!/usr/bin/env python3
"""
benchmark_trie.py - Benchmark trie implementations across datasets.

Compares Python marisa_trie with TypeScript/JavaScript implementations using
the same word lists generated from owlex spec files.

Usage:
  uv run python scripts/benchmark_trie.py [options]

Options:
  --all          Run all predefined datasets (wordle, word-only, full)
  --wordle       Run only Wordle 5-letter words (~3K words)
  --word-only    Run only word-only entries (~1.2M words)
  --full         Run only full Wiktionary (~1.3M words, default)
  --json         Output results as JSON
  --compare      Also run TypeScript benchmark and compare

Examples:
  # Benchmark all datasets with Python marisa_trie
  uv run python scripts/benchmark_trie.py --all

  # Compare Python and TypeScript implementations
  uv run python scripts/benchmark_trie.py --all --compare
"""

import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import marisa_trie

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class DatasetConfig:
    """Configuration for a benchmark dataset."""

    name: str
    description: str
    spec_file: str


DATASETS: dict[str, DatasetConfig] = {
    "wordle": DatasetConfig(
        name="Wordle 5-letter",
        description="5-letter common words (no vulgar/offensive)",
        spec_file="examples/wordlist-specs/wordle.yaml",
    ),
    "word-only": DatasetConfig(
        name="Word-only",
        description="All words (no phrases, proper nouns, idioms)",
        spec_file="examples/wordlist-specs/word-only.yaml",
    ),
    "full": DatasetConfig(
        name="Full Wiktionary",
        description="All entries (includes phrases)",
        spec_file="examples/wordlist-specs/full.yaml",
    ),
}


@dataclass
class BenchResult:
    """Results from a single benchmark run."""

    format: str
    implementation: str  # "python" or "typescript"
    word_count: int
    binary_size: int
    bytes_per_word: float
    build_time_ms: float
    lookup_avg_us: float
    prefix_avg_us: float


def load_words_from_spec(spec_file: str) -> list[str]:
    """Load words using owlex with a spec file."""
    spec_path = PROJECT_ROOT / spec_file
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    print(f"  Running owlex {spec_file}...")
    result = subprocess.run(
        ["uv", "run", "owlex", str(spec_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    # Deduplicate and sort
    words = [w for w in result.stdout.strip().split("\n") if w]
    unique = sorted(set(words))
    return unique


def benchmark_lookups(
    trie: marisa_trie.Trie, words: list[str], iterations: int = 1000
) -> float:
    """Benchmark lookup performance. Returns average time in microseconds."""
    sample_size = min(iterations, len(words))
    sample_words = random.choices(words, k=sample_size)

    # Add some non-words
    non_words = [w + "xyz" for w in sample_words]
    all_words = sample_words + non_words

    start = time.perf_counter()
    for word in all_words:
        _ = word in trie
    elapsed = time.perf_counter() - start

    return (elapsed * 1_000_000) / len(all_words)  # microseconds per lookup


def benchmark_prefix_search(
    trie: marisa_trie.Trie, words: list[str], iterations: int = 100
) -> float:
    """Benchmark prefix search performance. Returns average time in microseconds."""
    prefixes = []
    for _ in range(iterations):
        word = random.choice(words)
        prefix_len = min(len(word), random.randint(2, 4))
        prefixes.append(word[:prefix_len])

    start = time.perf_counter()
    for prefix in prefixes:
        # Get up to 10 matches (similar to TypeScript benchmark)
        results = list(trie.keys(prefix))[:10]
        _ = results
    elapsed = time.perf_counter() - start

    return (elapsed * 1_000_000) / len(prefixes)  # microseconds per search


def benchmark_marisa_trie(words: list[str]) -> BenchResult:
    """Run benchmark for Python marisa_trie."""
    # Build
    build_start = time.perf_counter()
    trie = marisa_trie.Trie(words)
    build_time_ms = (time.perf_counter() - build_start) * 1000

    # Size - save to temp file to measure
    with tempfile.NamedTemporaryFile(suffix=".trie", delete=False) as f:
        temp_path = f.name
    trie.save(temp_path)
    binary_size = Path(temp_path).stat().st_size
    Path(temp_path).unlink()

    bytes_per_word = binary_size / len(words)

    # Lookups
    lookup_avg_us = benchmark_lookups(trie, words)

    # Prefix search
    prefix_avg_us = benchmark_prefix_search(trie, words)

    return BenchResult(
        format="marisa_trie",
        implementation="python",
        word_count=len(words),
        binary_size=binary_size,
        bytes_per_word=bytes_per_word,
        build_time_ms=build_time_ms,
        lookup_avg_us=lookup_avg_us,
        prefix_avg_us=prefix_avg_us,
    )


def fmt_bytes(n: int) -> str:
    """Format bytes as human-readable."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def print_results(dataset: DatasetConfig, results: list[BenchResult]) -> None:
    """Print benchmark results as a table."""
    print()
    print("=" * 110)
    print(f"BENCHMARK: {dataset.name}")
    print(f"{dataset.description}")
    print("=" * 110)
    print(f"Words: {results[0].word_count:,}")
    print()

    # Header
    header = (
        "Format".ljust(20)
        + "Impl".ljust(12)
        + "Size".ljust(12)
        + "B/word".ljust(10)
        + "Build".ljust(12)
        + "Lookup".ljust(12)
        + "Prefix"
    )
    print(header)
    print("-" * 110)

    # Data rows
    for r in results:
        row = (
            r.format.ljust(20)
            + r.implementation.ljust(12)
            + fmt_bytes(r.binary_size).ljust(12)
            + f"{r.bytes_per_word:.2f}".ljust(10)
            + f"{r.build_time_ms:.0f}ms".ljust(12)
            + f"{r.lookup_avg_us:.2f}us".ljust(12)
            + f"{r.prefix_avg_us:.1f}us"
        )
        print(row)

    print("-" * 110)


def run_typescript_benchmark(dataset_key: str) -> Optional[list[dict]]:
    """Run TypeScript benchmark and parse results."""
    # This is a placeholder - would need to parse TypeScript output
    # For now, we'll suggest running them side-by-side
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark trie implementations across datasets"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all predefined datasets"
    )
    parser.add_argument(
        "--wordle", action="store_true", help="Run only Wordle 5-letter words"
    )
    parser.add_argument(
        "--word-only", action="store_true", help="Run only word-only entries"
    )
    parser.add_argument(
        "--full", action="store_true", help="Run only full Wiktionary"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare with TypeScript implementations (not yet implemented)",
    )
    args = parser.parse_args()

    print("Trie Benchmark (Python marisa_trie)")
    print("=" * 40)
    print()

    # Determine which datasets to run
    if args.all:
        datasets_to_run = ["wordle", "word-only", "full"]
    elif args.wordle or args.word_only or args.full:
        datasets_to_run = []
        if args.wordle:
            datasets_to_run.append("wordle")
        if args.word_only:
            datasets_to_run.append("word-only")
        if args.full:
            datasets_to_run.append("full")
    else:
        # Default to full
        datasets_to_run = ["full"]

    all_results: list[tuple[DatasetConfig, list[BenchResult]]] = []

    for dataset_key in datasets_to_run:
        dataset = DATASETS[dataset_key]
        print(f"\nLoading {dataset.name} dataset...")

        try:
            words = load_words_from_spec(dataset.spec_file)
            print(f"  Loaded {len(words):,} unique words")

            if len(words) == 0:
                print(f"  Error: No words found for {dataset.name}")
                continue

            print("  Running benchmarks:")
            print("    Python marisa_trie...", end="", flush=True)
            result = benchmark_marisa_trie(words)
            print(" done")

            results = [result]
            all_results.append((dataset, results))

            if not args.json:
                print_results(dataset, results)

        except subprocess.CalledProcessError as e:
            print(f"  Error running owlex: {e.stderr}")
            continue
        except Exception as e:
            print(f"  Error loading {dataset.name}: {e}")
            continue

    # JSON output
    if args.json:
        output = []
        for dataset, results in all_results:
            output.append(
                {
                    "dataset": {
                        "name": dataset.name,
                        "description": dataset.description,
                        "spec_file": dataset.spec_file,
                    },
                    "results": [
                        {
                            "format": r.format,
                            "implementation": r.implementation,
                            "word_count": r.word_count,
                            "binary_size": r.binary_size,
                            "bytes_per_word": r.bytes_per_word,
                            "build_time_ms": r.build_time_ms,
                            "lookup_avg_us": r.lookup_avg_us,
                            "prefix_avg_us": r.prefix_avg_us,
                        }
                        for r in results
                    ],
                }
            )
        print(json.dumps(output, indent=2))
    else:
        # Summary
        if len(all_results) > 1:
            print()
            print("=" * 110)
            print("SUMMARY: Python marisa_trie Across Datasets")
            print("=" * 110)
            print()
            print(
                "Dataset".ljust(20)
                + "Words".ljust(14)
                + "Size".ljust(14)
                + "B/word".ljust(12)
                + "Build".ljust(12)
                + "Lookup"
            )
            print("-" * 110)
            for dataset, results in all_results:
                r = results[0]
                print(
                    dataset.name.ljust(20)
                    + f"{r.word_count:,}".ljust(14)
                    + fmt_bytes(r.binary_size).ljust(14)
                    + f"{r.bytes_per_word:.2f} B".ljust(12)
                    + f"{r.build_time_ms:.0f}ms".ljust(12)
                    + f"{r.lookup_avg_us:.2f}us"
                )
            print("=" * 110)

        # Notes
        print()
        print("Notes:")
        print("  - marisa_trie: Python wrapper for MARISA C++ library")
        print("  - Build time includes trie construction only")
        print("  - Binary size measured from serialized .trie file")
        print()
        print("To compare with TypeScript implementations, run:")
        print("  cd web/viewer && pnpm benchmark --all")


if __name__ == "__main__":
    main()
