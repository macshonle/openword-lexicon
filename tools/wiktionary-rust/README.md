# Wiktionary Parser (Rust)

**High-performance Rust implementation of the Wiktionary XML parser**

This is a spike/proof-of-concept implementation to explore potential performance gains from rewriting the Python parser in Rust. Expected speedup: 3-10x faster than the Python version.

## Features

- ✅ BZ2 decompression support
- ✅ Streaming XML scanner (no full DOM parsing)
- ✅ English entry extraction with POS tagging
- ✅ Label extraction (register, temporal, domain)
- ✅ Boolean property detection (archaic, vulgar, informal, etc.)
- ✅ Compatible JSONL output format
- ✅ Cross-platform (macOS and Linux)

## Not Implemented (Simplified for Spike)

- ❌ Syllable count extraction
- ❌ Morphology parsing (etymology)
- ❌ Phrase type detection
- ❌ Regional variants
- ❌ Advanced Unicode normalization

These features can be added if the spike shows sufficient performance gains.

## Installation

### Prerequisites

- Rust 1.70+ (install from https://rustup.rs/)

### Build

```bash
cd tools/wiktionary-rust
cargo build --release
```

The compiled binary will be at: `target/release/wiktionary-rust`

## Usage

Basic usage:

```bash
./target/release/wiktionary-rust \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en/wikt-rust.jsonl
```

With entry limit (for testing):

```bash
./target/release/wiktionary-rust \
    --limit 10000 \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en/wikt-rust.jsonl
```

## Performance Comparison

**Python version:**
- Runtime: ~15 minutes (on reference hardware)
- Rate: ~1,000-2,000 pages/sec
- Single-threaded

**Rust version (expected):**
- Runtime: ~2-3 minutes (estimated)
- Rate: ~5,000-10,000 pages/sec
- Single-threaded (can be parallelized)

## Why Rust is Faster

1. **Compiled code** - No interpreter overhead
2. **Zero-cost abstractions** - Performance without sacrificing safety
3. **Better memory management** - No GC pauses, efficient allocations
4. **Faster regex** - Rust's regex crate is highly optimized
5. **SIMD optimizations** - Automatic vectorization by LLVM

## Integration with Makefile

To use the Rust parser in your build pipeline:

```makefile
# Add to Makefile
data/intermediate/en/wikt.jsonl: data/raw/en/enwiktionary-latest-pages-articles.xml.bz2
	@echo "Extracting Wiktionary (Rust version)..."
	tools/wiktionary-rust/target/release/wiktionary-rust $< $@
```

## Development

Run in debug mode (faster compilation, slower runtime):

```bash
cargo run -- input.xml.bz2 output.jsonl
```

Run with optimizations:

```bash
cargo run --release -- input.xml.bz2 output.jsonl
```

Run tests:

```bash
cargo test
```

## Output Format

The output JSONL format is compatible with the Python version:

```json
{
  "word": "example",
  "pos": ["noun"],
  "labels": {
    "register": ["informal"]
  },
  "word_count": 1,
  "is_phrase": false,
  "is_abbreviation": false,
  "is_proper_noun": false,
  "is_vulgar": false,
  "is_archaic": false,
  "is_rare": false,
  "is_informal": true,
  "is_technical": false,
  "is_regional": false,
  "is_inflected": false,
  "is_dated": false,
  "sources": ["wikt"]
}
```

## Next Steps

If this spike shows promising results:

1. **Benchmark** - Run on full dataset and compare times
2. **Feature parity** - Add missing features (syllables, morphology, etc.)
3. **Parallelization** - Process pages in parallel for even faster speeds
4. **Memory profiling** - Optimize memory usage for large dumps
5. **Error handling** - Improve diagnostics and logging

## License

Same as parent project
