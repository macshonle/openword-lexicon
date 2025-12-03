# Wiktionary Rust Parser - Quick Start

## Overview

High-performance Rust implementation of the Wiktionary XML parser, now integrated as the default parser in the build pipeline. Reduces processing time from ~15 minutes to ~2-3 minutes (5-10x faster than Python).

## Files

```
tools/wiktionary-scanner-rust/
├── Cargo.toml              # Rust dependencies and build config
├── src/
│   └── main.rs             # Complete parser implementation (~850 lines)
├── README.md               # Detailed documentation
└── QUICKSTART.md           # This file
```

## Building the Scanner

To build or rebuild the Rust scanner:

1. **Verify it builds:**
   ```bash
   cd tools/wiktionary-scanner-rust
   cargo build --release
   ```

2. **Check the binary exists:**
   ```bash
   ls -lh target/release/wiktionary-scanner-rust
   ```

3. **See help text:**
   ```bash
   ./target/release/wiktionary-scanner-rust --help
   ```

## Usage

The Rust scanner is automatically used by the Makefile:

```bash
# Build via Makefile (recommended)
make build-wiktionary-json
```

Or run directly:

```bash
# From repo root
tools/wiktionary-scanner-rust/target/release/wiktionary-scanner-rust \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en/wikt.jsonl
```

## Expected Performance

| Version | Runtime | Rate | Speedup |
|---------|---------|------|---------|
| Python | ~15 min | ~1,500 pg/s | 1x |
| Rust | ~2-3 min | ~8,000 pg/s | **5-8x** |

## What's Implemented

✅ **Full feature parity with Python version** - All features implemented:
- BZ2 decompression
- Streaming XML scanning
- English section extraction
- POS tag extraction
- Label extraction (register, temporal, domain, region)
- Boolean properties (archaic, vulgar, informal, etc.)
- Syllable count extraction (hyphenation, rhymes, categories)
- Morphology/etymology parsing (prefix, suffix, affix, compound, confix)
- Phrase type detection (idiom, proverb, prepositional phrase, etc.)
- Unicode normalization (Latin Extended support: 0x00C0-0x024F)
- Compatible JSONL output

## Status

✅ **Integrated into build pipeline** - The Rust scanner is now the default:
- Makefile uses Rust scanner for `build-wiktionary-json` target
- Python version remains available for reference/testing
- Full feature parity achieved
- Significant performance improvement (5-10x faster than Python)

## Quick Comparison Test

```bash
# Test both versions on 1000 entries
time tools/wiktionary-scanner-rust/target/release/wiktionary-scanner-rust \
    --limit 1000 \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    /tmp/rust-1k.jsonl

time uv run python tools/wiktionary_scanner_python/scanner.py \
    --limit 1000 \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    /tmp/python-1k.jsonl

# Compare entry counts
wc -l /tmp/rust-1k.jsonl /tmp/python-1k.jsonl

# Sample comparison
head -5 /tmp/rust-1k.jsonl
head -5 /tmp/python-1k.jsonl
```

## Troubleshooting

**Build fails:**
- Make sure Rust is installed: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- Update Rust: `rustup update`

**Runtime errors:**
- Check input file exists and is readable
- Ensure output directory exists
- Try with `--limit 10` first to test quickly

**Output differences:**
- Rust and Python versions produce functionally equivalent output
- Rust version accepts slightly wider range of punctuation (~0.1% more entries, primarily idioms/proverbs with commas)
- All core fields (word, POS, labels, syllables, morphology, phrase_type) are present in both versions

## Documentation

See `SPIKE_WIKTIONARY_PERFORMANCE.md` in the repo root for:
- Detailed performance analysis
- Comparison with other optimization options
- Recommendations for next steps
- Alternative approaches (PyPy, Go, etc.)
