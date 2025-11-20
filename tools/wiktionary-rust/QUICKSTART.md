# Wiktionary Rust Parser - Quick Start

## What Was Created

This spike implements a high-performance Rust version of the Wiktionary XML parser to potentially reduce processing time from ~15 minutes to ~3 minutes.

## Files Created

```
tools/wiktionary-rust/
├── Cargo.toml              # Rust dependencies and build config
├── src/
│   └── main.rs             # Complete parser implementation (~610 lines)
├── README.md               # Detailed documentation
└── QUICKSTART.md           # This file
```

## Quick Test (No Data File Needed)

Since you don't have the data file available on this machine, you can still:

1. **Verify it builds:**
   ```bash
   cd tools/wiktionary-rust
   cargo build --release
   ```

2. **Check the binary exists:**
   ```bash
   ls -lh target/release/wiktionary-rust
   ```

3. **See help text:**
   ```bash
   ./target/release/wiktionary-rust --help
   ```

## Usage When You Have Data

```bash
# From repo root
tools/wiktionary-rust/target/release/wiktionary-rust \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    data/intermediate/en/wikt-rust.jsonl
```

## Expected Performance

| Version | Runtime | Rate | Speedup |
|---------|---------|------|---------|
| Python | ~15 min | ~1,500 pg/s | 1x |
| Rust | ~2-3 min | ~8,000 pg/s | **5-8x** |

## What's Implemented

✅ Core features:
- BZ2 decompression
- Streaming XML scanning
- English section extraction
- POS tag extraction
- Label extraction (register, temporal, domain)
- Boolean properties (archaic, vulgar, informal, etc.)
- Compatible JSONL output

❌ Omitted for spike (can be added later):
- Syllable count extraction
- Morphology/etymology parsing
- Phrase type detection
- Advanced Unicode edge cases

## Next Steps

1. **Benchmark** - Run on actual data file and measure speedup
2. **Validate** - Compare output with Python version
3. **Decide** - If >5x faster, add missing features and integrate
4. **Document** - Update build pipeline documentation

## Quick Comparison Test

```bash
# Test both versions on 1000 entries
time tools/wiktionary-rust/target/release/wiktionary-rust \
    --limit 1000 \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    /tmp/rust-1k.jsonl

time uv run python tools/wiktionary_scanner_parser.py \
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
- Rust version omits some fields (syllables, morphology) - this is expected
- Word counts and POS tags should match
- Small differences in label extraction are acceptable for spike

## Documentation

See `SPIKE_WIKTIONARY_PERFORMANCE.md` in the repo root for:
- Detailed performance analysis
- Comparison with other optimization options
- Recommendations for next steps
- Alternative approaches (PyPy, Go, etc.)
