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
| Download size | 4.66 MB | 3.09 MB |
| Runtime memory | ~4 MB | ~40 MB |
| Load time | ~50 ms | ~200 ms |
| Query time | <1 ms | <1 ms |

### Recommendations

1. **Use v7** when:
   - Runtime memory is constrained
   - No WASM dependency is preferred
   - Load time is critical

2. **Use v8** when:
   - Download size is the primary concern
   - Runtime memory is not constrained
   - WASM is already in use

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
