# Parallel Processing Optimizations for Wiktionary Scanner

This document describes the parallel processing strategies implemented to optimize the Rust-based Wiktionary XML scanner.

## Overview

The original scanner processed pages sequentially, achieving ~31,457 pages/sec. This optimization adds multiple parallelization strategies that can significantly improve throughput on multi-core systems.

## Available Strategies

### 1. Sequential (Baseline)
```bash
./target/release/wiktionary-rust input.xml.bz2 output.jsonl -s sequential
```
- Original single-threaded processing
- Best for single-core systems or baseline comparison
- Expected: ~30K pages/sec

### 2. Batch-Parallel
```bash
./target/release/wiktionary-rust input.xml.bz2 output.jsonl -s batch-parallel
```
- Collects pages into batches
- Processes each batch in parallel using thread pool
- Configurable batch size: `--batch-size 1000`
- **Recommended for most use cases**
- Expected: 2-4x speedup on 4+ cores

### 3. Channel-Pipeline
```bash
./target/release/wiktionary-rust input.xml.bz2 output.jsonl -s channel-pipeline
```
- Producer-consumer pattern using std::sync::mpsc channels
- One reader thread, N worker threads, one writer thread
- Configurable buffer size: `--channel-buffer 10000`
- Good for I/O-bound scenarios
- Expected: 1.5-3x speedup

### 4. Two-Phase
```bash
./target/release/wiktionary-rust input.xml.bz2 output.jsonl -s two-phase
```
- Phase 1: Read all pages into memory
- Phase 2: Process all pages in parallel
- Phase 3: Write results
- Best for systems with sufficient RAM (~10GB for full dump)
- Expected: 2-4x speedup on Phase 2

## CLI Options

```
wiktionary-rust [OPTIONS] <INPUT> <OUTPUT>

Arguments:
  <INPUT>   Input XML file (.xml or .xml.bz2)
  <OUTPUT>  Output JSONL file

Options:
  -s, --strategy <STRATEGY>
          Processing strategy [default: sequential]
          [possible values: sequential, batch-parallel, channel-pipeline, two-phase]

  -t, --threads <THREADS>
          Number of threads (0 = auto-detect) [default: 0]

      --batch-size <BATCH_SIZE>
          Batch size for batch-parallel strategy [default: 1000]

      --channel-buffer <CHANNEL_BUFFER>
          Channel buffer size for channel-pipeline strategy [default: 10000]

      --limit <LIMIT>
          Limit number of entries to extract (for testing)

      --timing
          Show detailed timing breakdown

  -q, --quiet
          Quiet mode - minimal output

      --benchmark
          Benchmark mode - run all strategies and compare

  -V, --version
          Print version

  -h, --help
          Print help
```

## Benchmark Mode

Run all strategies and compare performance:

```bash
./target/release/wiktionary-rust input.xml.bz2 output.jsonl --benchmark
```

This will run each strategy and print a comparison table showing:
- Execution time
- Pages/second throughput
- Speedup relative to sequential baseline

## Tuning Guide

### For Maximum Throughput
1. Use `batch-parallel` strategy
2. Set batch size to 1000-2000
3. Use all available cores: `-t 0`

### For Memory-Constrained Systems
1. Use `sequential` or `batch-parallel` with small batch size
2. Avoid `two-phase` (loads entire file into memory)

### For I/O-Bound Scenarios (slow disk/network)
1. Use `channel-pipeline`
2. Increase buffer size: `--channel-buffer 50000`

### Testing Parameters
Use the synthetic data generator to create test files:

```bash
# Small test (10K pages, ~5 MB compressed)
python3 scripts/generate_synthetic_data.py --small

# Medium test (100K pages, ~50 MB compressed)
python3 scripts/generate_synthetic_data.py --medium

# Large test (500K pages, ~250 MB compressed)
python3 scripts/generate_synthetic_data.py --large

# Full scale (1M pages, ~500 MB compressed)
python3 scripts/generate_synthetic_data.py --full
```

## Example Commands

```bash
# Basic usage with default settings
./target/release/wiktionary-rust data/enwiktionary.xml.bz2 output.jsonl

# Parallel processing with 8 threads
./target/release/wiktionary-rust data/enwiktionary.xml.bz2 output.jsonl \
    -s batch-parallel -t 8

# Quick test with limit
./target/release/wiktionary-rust data/enwiktionary.xml.bz2 output.jsonl \
    -s batch-parallel --limit 10000 -q

# Full benchmark
./target/release/wiktionary-rust data/enwiktionary.xml.bz2 output.jsonl \
    --benchmark
```

## Implementation Notes

### Thread Safety
- All strategies use Rust's thread-safe primitives (`Arc`, `Mutex`, `mpsc` channels)
- Regex patterns are compiled once using `lazy_static!` (thread-safe)
- No unsafe code or data races

### Memory Usage
- Sequential: O(1) - streaming, minimal memory
- Batch-parallel: O(batch_size * page_size) - bounded by batch size
- Channel-pipeline: O(buffer_size * page_size) - bounded by buffer size
- Two-phase: O(total_pages * page_size) - loads entire file

### Decompression Bottleneck
Note: bzip2 decompression is single-threaded and can be a bottleneck. For maximum speed:
1. Decompress to plain XML first: `bunzip2 -k file.xml.bz2`
2. Process the uncompressed file
3. Consider using `pbzip2` for parallel decompression (external tool)

## Expected Performance

On a typical 4-core system with full Wiktionary dump (~3GB bz2):

| Strategy        | Time    | Pages/sec | Speedup |
|-----------------|---------|-----------|---------|
| Sequential      | 5.5 min | 31,000    | 1.0x    |
| Batch-parallel  | ~2 min  | 80,000+   | 2.5x    |
| Channel-pipeline| ~2.5min | 65,000+   | 2.0x    |
| Two-phase       | ~2 min  | 80,000+   | 2.5x    |

*Note: Actual results depend on CPU, disk speed, and available memory.*

## Future Optimizations

Potential improvements not yet implemented:

1. **Rayon integration**: Using rayon crate would provide work-stealing and better load balancing (requires network access to add dependency)

2. **Memory-mapped I/O**: For uncompressed files, mmap could reduce copying

3. **SIMD regex**: The `regex` crate already uses SIMD, but custom patterns could be further optimized

4. **Parallel bzip2**: Using `bzip2-rs` with parallel decompression or external `pbzip2`
