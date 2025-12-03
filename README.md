# OpenWord Lexicon

A comprehensive English wordlist with metadata for word games, educational apps, and spell checkers.

## What You Get

- **1.35M words** with part-of-speech, frequency tiers, concreteness ratings
- **Game-ready wordlist** (`en-game.trie`) — pure a-z words, no hyphens or apostrophes
- **Modular metadata** — load only what you need (frequency, concreteness, syllables, sources)
- **Per-word licensing** — filter by source to meet your license requirements

## Quick Start

```bash
# Clone and build
git clone https://github.com/macshonle/openword-lexicon.git
cd openword-lexicon
make bootstrap
make build-en

# Check a word exists
uv run python -c "
import marisa_trie
trie = marisa_trie.Trie().mmap('data/build/en.trie')
print('castle' in trie)  # True
"
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for more usage examples.

## Output Files

After `make build-en`, you'll find:

| File | Description | Size |
|------|-------------|------|
| `data/build/en.trie` | Full lexicon (MARISA trie) | ~4 MB |
| `data/build/en-game.trie` | Game profile (a-z only) | ~2.5 MB |
| `data/build/en-wordlist.txt` | Plain text word list | ~16 MB |
| `data/build/en-frequency.json.gz` | Frequency tiers (A-L/Y/Z) | ~5 MB |
| `data/build/en-concreteness.json.gz` | Concreteness ratings | ~150 KB |
| `data/build/en-syllables.json.gz` | Syllable counts | ~200 KB |
| `data/build/en-sources.json.gz` | Source attributions | ~5 MB |

## Use Cases

| Use Case | Recommended Files | Filter Strategy |
|----------|-------------------|-----------------|
| Wordle clone | `en-game.trie` + frequency | 5 letters, tiers A-F |
| Kids vocabulary | lexemes + concreteness | Concrete nouns, tiers A-G |
| Spell checker | `en.trie` | Full lexicon |
| Profanity filter | lexemes file | Check `labels.register` for vulgar/offensive |
| Scrabble | `en-game.trie` | Pure a-z, check proper noun flags |

## Creating Custom Word Lists

Use the interactive web builder or command-line tool:

```bash
# Web interface for creating filter specs
make spec-editor-web

# Command line with JSON spec
uv run python -m openword.owlex examples/wordlist-specs/wordle.json
```

See [docs/FILTERING.md](docs/FILTERING.md) for filter options.

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Get words into your app in 5 minutes |
| [SCHEMA.md](docs/SCHEMA.md) | Data format and field reference |
| [BUILDING.md](docs/BUILDING.md) | Build pipeline and architecture |
| [FILTERING.md](docs/FILTERING.md) | Create custom filtered wordlists |
| [SOURCES.md](docs/SOURCES.md) | Data sources and licensing |

## Statistics

| Metric | Value |
|--------|-------|
| Total words | ~1,350,000 |
| Game words (a-z only) | ~330,000 |
| With frequency data | ~75,000 (tiers A-L) |
| With concreteness | ~39,000 |
| With syllable counts | ~30,000 |
| With POS tags | ~700,000 |

## License

- **Code**: Apache-2.0
- **Data**: Per-word tracking via `sources` field
  - Wiktionary: CC BY-SA 4.0
  - EOWL: UKACD (permissive)
  - WordNet: CC BY 4.0
  - Brysbaert: Research/Educational

Filter by source if you need permissive-only words. See [docs/SOURCES.md](docs/SOURCES.md).

## Contributing

Contributions welcome! Please open an issue to discuss proposed changes.
