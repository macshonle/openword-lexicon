# OpenWord Lexicon - Wordlist Viewer

Interactive browser-based viewer for exploring the OpenWord Lexicon trie data structure.

## Quick Start

```bash
# From project root
make wordlist-viewer-web

# Server will start at: http://localhost:8080
# Requires: pnpm (install with: npm install -g pnpm)
# Requires: Run 'make build-en' first to generate wordlist data
```

## Features

- **Prefix Search**: Type to see all words starting with your prefix
- **Word Validation**: Check if a word exists in the lexicon
- **Visual Feedback**: Green for valid prefixes, red for invalid parts
- **Next Letters**: Shows which letters can follow the current prefix
- **Neighbor Words**: When typing an invalid word, shows nearest valid words
- **Random Words**: Generate random words from the lexicon
- **Statistics**: Word count, node count, and current input state

## How It Works

The viewer automatically selects the best loading strategy:

### Binary DAWG (Preferred)

If a pre-built binary trie is available (`/data/en.trie.bin`):
- **Load time**: ~100-200ms (instant)
- **File size**: ~6 MB (v4 format)
- **Memory**: ~20-40 MB in browser

Build the binary trie with:
```bash
make build-trie
```

### Dynamic Trie (Fallback)

If no binary trie is available, falls back to loading the plain text wordlist:
- **Load time**: ~5-10 seconds for full lexicon
- **File size**: ~10-15 MB uncompressed text
- **Memory**: ~50-100 MB in browser

## Binary Trie Format

The `.trie.bin` files use a custom compact DAWG format:

**Header (12 bytes):**
- Magic: "OWTRIE" (6 bytes)
- Version: uint16 (2 bytes)
- Word count: uint32 (4 bytes)

**Current Versions:**

The builder auto-selects between v2/v4 for DAWG, or use `--format=v2|v4|v5`:

| Version | Structure | Node IDs | Best For | Bytes/Word |
|---------|-----------|----------|----------|------------|
| v2 | DAWG | 16-bit absolute | ≤65K nodes | ~3 |
| v4 | DAWG | varint delta | Any size | ~2-3 |
| v5 | LOUDS trie | bitvector | Word ID mapping | ~1.5-2 |

**v2 Format (compact, limited):**
- Flags byte: bit 0 = is_terminal
- Child count byte: 0-255
- Children: (char: uint8, node_id: uint16) per child
- Max 65,535 nodes

**v4 Format (universal, efficient):**
- Flags byte: bit 0 = is_terminal
- Child count byte: 0-255
- Children: (char: varint, delta: varint) per child
- Delta = parentId - childId (always positive in post-order)
- Full Unicode support via varint code points

**v5 Format (LOUDS trie with word IDs):**

LOUDS (Level-Order Unary Degree Sequence) is a succinct data structure that
encodes tree topology using bitvectors with O(1) rank and O(log n) select.

Header (16 bytes):
- Magic: "OWTRIE" (6 bytes)
- Version: uint16 = 5 (2 bytes)
- Word count: uint32 (4 bytes)
- Node count: uint32 (4 bytes)

Body:
- LOUDS bitvector (packed bits + rank directory)
- Terminal bitvector (marks end-of-word nodes)
- Labels array (varint-encoded Unicode code points)

Key features:
- **Word ID mapping**: Each word maps to a sequential 0-indexed ID via
  `wordId = rank1(terminal, nodePosition) - 1`. IDs are assigned in BFS
  (level-order) traversal, enabling dense array lookups for enrichment data.
- **Prefix search**: Navigate via `findChild()` with binary search on labels
- **Compact**: ~1.5-2 bytes per word (vs ~2-3 for v4)

Build with `--format=v5`:
```bash
pnpm run build-trie wordlist.txt output.bin --format=v5
```

References:
- Jacobson, G. (1989) "Space-efficient Static Trees and Graphs" - FOCS 1989
- Delpratt, O., Rahman, N., Raman, R. (2006) "Engineering the LOUDS
  Succinct Tree Representation" - WEA 2006
- Hanov, S. "Succinct Data Structures" - stevehanov.ca/blog/?id=120

**DAWG Optimization (v2/v4):**
- Nodes with identical suffixes are merged (deduplication)
- Children sorted by character for consistency
- Node IDs assigned in post-order (root is last node)

**Supported Versions:** v2, v4, v5 (v1/v3 were deprecated and removed)

See `src/build-trie.ts` for implementation details.

## Project Structure

```
tools/wordlist-viewer/
├── index.html              # Single entry point
├── styles.css              # Stylesheet
├── app.js                  # Main application (unified trie loader)
├── src/
│   ├── build-trie.ts       # Binary trie builder (Node.js/tsx)
│   ├── build-trie.test.ts  # Builder tests
│   ├── bitvector.ts        # Rank/select bitvector for LOUDS
│   ├── bitvector.test.ts   # Bitvector tests
│   ├── louds.ts            # LOUDS tree encoding
│   ├── louds.test.ts       # LOUDS tree tests
│   ├── louds-trie.ts       # LOUDS trie with word ID mapping
│   └── louds-trie.test.ts  # LOUDS trie tests
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
├── data/                   # Generated binary tries (gitignored)
│   └── en.trie.bin
└── README.md               # This file
```

## Development

### Scripts

```bash
# Install dependencies
pnpm install

# Build binary trie from wordlist (auto-selects v2/v4 DAWG)
pnpm run build-trie [input.txt] [output.bin]

# Build LOUDS trie with word ID support (v5)
pnpm run build-trie [input.txt] [output.bin] --format=v5

# Run tests
pnpm test

# Start development server
pnpm start
```

### Dependencies

- **tsx** - TypeScript execution for build-trie.ts
- **http-server** - Local development server
- **typescript** - Type checking

## Requirements

- **pnpm**: JavaScript package manager
  ```bash
  npm install -g pnpm
  ```

- **Wordlist**: Generated by `make build-en`
  - Location: `data/build/en-wordlist.txt`

## Troubleshooting

### "Binary trie not available" fallback

This is normal if you haven't built the binary trie:
```bash
make build-trie
```

The viewer will still work using the dynamic trie fallback.

### "Wordlist not found" error

Run the build first:
```bash
make build-en
```

### CORS errors

The viewer must be served via HTTP, not opened as `file://`.

**Solution:** Use `make wordlist-viewer-web` which starts an HTTP server.

## Use Cases

- **Lexicon Exploration**: Browse the full word list interactively
- **Word Validation**: Check if words exist in the lexicon
- **Prefix Analysis**: See all words with a given prefix
- **Enrichment Data Lookup**: Use v5 word IDs to index into dense arrays of
  metadata (definitions, frequencies, etc.) stored in companion files
- **Vocabulary Games**: Random word generation
- **Debugging**: Verify build output
- **Education**: Visualize trie/DAWG and LOUDS succinct data structures

## See Also

- [Wordlist Spec Editor](../wordlist-spec-editor/) - Web UI for creating filter specs
- [Main README](../../README.md) - Project overview
- [SOURCES.md](../../docs/SOURCES.md) - Data sources and licensing
