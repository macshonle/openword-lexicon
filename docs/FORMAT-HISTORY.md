# OWTRIE Format History

This document records the evolution of the OWTRIE binary trie format and the rationale behind design decisions.

## Current Formats (December 2024)

### v7 - MARISA Trie (Uncompressed)
- **Header**: 24 bytes (magic + version + word count + node count + flags + tail buffer size)
- **Structure**: LOUDS bitvector + terminal bitvector + link flags + varint labels + recursive tail trie
- **Features**:
  - Full Unicode support
  - Word ID mapping via terminal.rank1()
  - Reverse lookup via getWord(id)
  - Path compression with recursive tail trie
- **Best for**: Runtime efficiency (~4 MB for 1.3M words), no WASM dependency

### v8 - MARISA Trie (Brotli Compressed)
- **Header**: 24 bytes (uncompressed) + 4 bytes compressed length
- **Structure**: Same as v7, but payload is brotli-compressed
- **Features**: All v7 features, plus ~33% smaller download size
- **Best for**: Bandwidth-constrained deployments
- **Trade-off**: Requires brotli-wasm (~40 MB runtime memory overhead)

## Deprecated Formats

The following formats were removed in the v7/v8 consolidation. They remain in git history if ever needed.

### v2 - DAWG with 16-bit Node IDs (Removed)
- ASCII only (code points 0-255)
- Maximum 65,535 nodes
- 3 bytes per child (1 char + 2 node ID)
- **Removed because**: Limited to ASCII, superseded by v4

### v4 - DAWG with Varint Node IDs (Removed)
- Full Unicode support
- Varint delta encoding for node IDs
- ~2-3 bytes per child average
- **Removed because**: Build-only format with no runtime query support in browser

### v5 - LOUDS Trie (Removed)
- LOUDS bitvector encoding
- Word ID mapping via terminal ranking
- No path compression
- **Removed because**: Superseded by v7 which has better compression and reverse lookup

### v6.0/v6.1 - Early MARISA Variants (Removed)
- v6.0: Basic LOUDS without link flags
- v6.1: Added link flags and flat tail buffer with suffix sharing
- **Removed because**: Superseded by recursive tail trie (v6.3 -> v7)

### v6.3 - MARISA with Recursive Tails (Now v7)
- Recursive trie over tail strings
- Best runtime memory efficiency
- Renamed to v7 for clean version break

### v6.4 - MARISA with Huffman Labels (Removed)
- Huffman-encoded label array
- **Removed because**: Minimal size benefit (~5%) didn't justify complexity

### v6.5 - MARISA with Brotli (Now v8)
- Brotli-compressed payload (quality 11)
- Best download size
- Renamed to v8 for clean version break

### v6.6 - MARISA with Fast Brotli (Removed)
- Brotli quality 5 for faster compression
- **Removed because**: No clear use case vs v6.3 (runtime) or v6.5 (download)

## Key Findings from Benchmarks

### Full Wiktionary Dataset (~1.3M words)

| Metric | v7 (uncompressed) | v8 (brotli) |
|--------|-------------------|-------------|
| Download size | 4.52 MB | 2.95 MB |
| Runtime memory | ~4 MB | ~40 MB |
| Load time | ~50 ms | ~200 ms |
| Query time | <1 ms | <1 ms |

### Compression Comparison

v8 (brotli-compressed trie) outperforms all general-purpose compression on raw word lists:

| Method | Full Wiktionary | Notes |
|--------|-----------------|-------|
| **v8 (OWTRIE + brotli)** | **2.95 MB** | Queryable, best overall |
| xz -9 | 3.48 MB | Text only |
| brotli -11 | 3.49 MB | Text only |
| zstd -19 | 3.63 MB | Text only |
| gzip -9 | 4.27 MB | Text only |
| **v7 (OWTRIE)** | **4.52 MB** | Queryable, no WASM |

### Recursion Depth Analysis

The MARISA algorithm supports configurable recursion depth for tail tries. Benchmarks show:

| Depth | v7 (Full) | v8 (Full) | Build Time |
|-------|-----------|-----------|------------|
| 1 (default) | 4.52 MB | 2.95 MB | ~10s |
| 5 | 4.29 MB | 2.94 MB | ~17s |
| 8 | 4.29 MB | 2.94 MB | ~17s |
| 16 | 4.29 MB | 2.94 MB | ~19s |
| 32 | 4.30 MB | 2.94 MB | ~22s |

**Key findings:**
- Depth 5 captures all meaningful compression gains (~5% for v7)
- Depths beyond 5 show no improvement (tail strings become too short)
- Brotli (v8) makes recursion depth irrelevant—it compresses to the same size regardless
- Small datasets (e.g., 5-letter Wordle words) are *hurt* by deeper recursion due to overhead
- Default depth of 1 is optimal for most use cases

### Morpheme Encoding Experiment (Negative Result)

An experiment was conducted to test whether morpheme-aware encoding could improve compression. The hypothesis was that replacing common affixes (e.g., "un-", "-ness", "-ly") with single Unicode Private Use Area (PUA) code points might:
- Reduce file size by encoding multi-character affixes as single bytes
- Speed up build time by reducing redundant trie traversal

**Results:** Morpheme encoding makes everything worse:

| Dataset | Metric | Baseline | Morpheme | Change |
|---------|--------|----------|----------|--------|
| Full (v7) | Size | 4.52 MB | 5.96 MB | +32% |
| Full (v7) | Build | 10.0s | 24.1s | +141% |
| Full (v8) | Size | 2.95 MB | 3.26 MB | +10% |
| Full (v8) | Build | 9.9s | 23.8s | +141% |
| Word-only (v7) | Size | 3.87 MB | 5.15 MB | +33% |
| Word-only (v8) | Size | 2.52 MB | 2.77 MB | +10% |

**Why morpheme encoding fails:**

1. **PUA code points are expensive**: Unicode PUA code points (U+E000+) require 3 bytes in varint encoding, while common prefixes like "un" or "re" are only 2 ASCII bytes.

2. **MARISA already optimizes sharing**: The trie algorithm already shares common prefixes efficiently through path compression. Morpheme substitution doesn't improve on this.

3. **Brotli captures patterns**: For v8, brotli compression already identifies and compresses repeated byte patterns, making pre-encoding redundant.

4. **Preprocessing overhead**: The time spent encoding/decoding words adds substantial overhead (2-3x slower builds).

**Conclusion:** The current MARISA implementation is already near-optimal. Morpheme-aware encoding provides no benefit for this use case.

### Reverse Suffix Trie Experiment (Negative Result)

A second experiment tested whether storing words in **reverse order** could improve compression by sharing common suffixes (-ing, -tion, -ness) as prefixes.

**Hypothesis**: English has many common suffixes. Reversing words transforms suffix sharing into prefix sharing, which the trie handles efficiently.

**Results:**

| Dataset | v7-forward | v7-reverse | v8-forward | v8-reverse |
|---------|------------|------------|------------|------------|
| Wordle (3K) | 9.9 KB | 9.6 KB (-3%) | 6.7 KB | 6.3 KB (-6%) |
| Word-only (1.2M) | 3.87 MB | 4.28 MB (+11%) | 2.52 MB | 2.68 MB (+6%) |
| Full (1.3M) | 4.52 MB | 4.98 MB (+10%) | 2.95 MB | 3.20 MB (+8%) |

**Key findings:**

1. **Small datasets benefit slightly from reverse**: Wordle (5-letter words) shows 3-6% improvement with reverse ordering.

2. **Large datasets are worse with reverse**: Word-only and Full Wiktionary are 6-11% larger when reversed.

3. **English has more prefix sharing than suffix sharing**: Common prefixes (un-, re-, pre-, dis-, over-, under-) provide more compression benefit than common suffixes (-ing, -ed, -ly, -ness, -tion).

4. **Build time is worse**: Reverse ordering takes 1.5-1.7x longer to build due to different branching patterns.

**Conclusion:** Forward (standard) ordering is optimal for English word lists. The trie's natural prefix sharing outperforms suffix sharing via reversal.

### Recommendations

1. **Use v7** when:
   - Runtime memory is constrained
   - No WASM dependency is preferred
   - Load time is critical

2. **Use v8** when:
   - Download size is the primary concern
   - Runtime memory is not constrained
   - WASM is already in use

3. **Use depth > 1** only when:
   - Building v7 format (not v8)
   - Dataset has very long keys (URLs, file paths)
   - Willing to accept 2x build time for ~5% size reduction

## Binary Format Specification

### v7/v8 Header (24 bytes)
```
Offset  Size  Description
0       6     Magic: "OWTRIE"
6       2     Version: 7 or 8 (little-endian)
8       4     Word count (little-endian)
12      4     Node count (little-endian)
16      4     Flags (little-endian)
20      4     Tail buffer size (little-endian)
```

### v8 Additional Header (after 24-byte header)
```
Offset  Size  Description
24      4     Compressed payload length (little-endian)
28      N     Brotli-compressed payload
```

### Flags
- `0x08` - RECURSIVE: Tails stored in recursive trie (always set in v7/v8)
- `0x20` - BROTLI: Payload is brotli-compressed (set in v8)

### Payload Structure
1. LOUDS bitvector (tree structure)
2. Terminal bitvector (word endings)
3. Link flags bitvector (path compression markers)
4. Labels array (varint-encoded Unicode code points)
5. Tail trie size (4 bytes)
6. Serialized recursive tail trie

## Migration Notes

When migrating from v6.x to v7/v8:
- Regenerate all trie files using the new format
- v7 is functionally equivalent to v6.3
- v8 is functionally equivalent to v6.5
- Old v6.0/v6.1 files are not compatible and must be regenerated

## Acknowledgments and References

The OWTRIE format and algorithm are inspired by the MARISA-trie data structure:

- **MARISA-trie**: Matching Algorithm with Recursively Implemented StorAge
  - Original C++ implementation by Susumu Yata
  - GitHub: https://github.com/s-yata/marisa-trie
  - Paper: Yata, S. et al. "A Compact Static Double-Array Keeping Character Codes" (2007)

- **marisa-trie (Python)**: Python bindings for MARISA-trie
  - GitHub: https://github.com/pytries/marisa-trie
  - Used during early development for benchmarking and validation

The OWTRIE TypeScript implementation is a clean-room reimplementation optimized for
browser deployment, featuring:
- LOUDS bitvector encoding (Jacobson, 1989)
- Recursive tail trie for path compression
- Optional brotli compression for reduced download size
- Full Unicode support via varint-encoded code points

Key references:
- Jacobson, G. "Space-efficient Static Trees and Graphs" (1989) - LOUDS encoding
- Navarro, G. & Mäkinen, V. "Compressed Full-Text Indexes" (2007) - Rank/select operations
