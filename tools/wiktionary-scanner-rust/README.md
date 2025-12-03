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

## Features - ✅ Full Parity with Python Version

All features from the Python version are now implemented:

- ✅ Syllable count extraction (hyphenation, rhymes, categories)
- ✅ Morphology parsing (etymology) - prefix, suffix, affix, compound, confix
- ✅ Phrase type detection (idiom, proverb, prepositional phrase, etc.)
- ✅ Regional variant extraction (en-GB, en-US, en-CA, en-AU, etc.)
- ✅ Complete label extraction (register, temporal, domain, region)
- ✅ Unicode normalization (Latin Extended support: 0x00C0-0x024F)

**Note:** The Rust implementation accepts a wider range of punctuation (including commas)
than the Python version, which results in ~0.1% more entries (primarily English proverbs
and idioms with commas).

## Installation

### Prerequisites

- Rust 1.70+ (install from https://rustup.rs/)

### Build

```bash
cd tools/wiktionary-scanner-rust
cargo build --release
```

The compiled binary will be at: `target/release/wiktionary-scanner-rust`

## Usage

Basic usage:

```bash
./target/release/wiktionary-scanner-rust \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en/wikt-rust.jsonl
```

With entry limit (for testing):

```bash
./target/release/wiktionary-scanner-rust \
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
	tools/wiktionary-scanner-rust/target/release/wiktionary-scanner-rust $< $@
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
  "pos": "noun",
  "word_count": 1,
  "is_phrase": false,
  "is_abbreviation": false,
  "is_inflected": false,
  "register_tags": ["informal"],
  "domain_tags": [],
  "region_tags": [],
  "temporal_tags": []
}
```

Note: Proper nouns use `pos: "proper"` instead of a separate flag.

## Next Steps

If this spike shows promising results:

1. **Benchmark** - Run on full dataset and compare times
2. **Feature parity** - Add missing features (syllables, morphology, etc.)
3. **Parallelization** - Process pages in parallel for even faster speeds
4. **Memory profiling** - Optimize memory usage for large dumps
5. **Error handling** - Improve diagnostics and logging

## License

Same as parent project
