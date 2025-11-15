# Phrase Filtering Guide

**Note:** This document is for reference only. Ad hoc phrase filtering targets have been removed. Use the general-purpose `tools/filter_words.py` framework instead. See `docs/GAME_WORDS.md` for usage examples.

The Plus distribution includes multi-word phrases from Wiktionary, ranging from useful idioms like "kick the bucket" to full proverbs like "when you're up to your neck in alligators, it's hard to remember that your initial objective was to drain the swamp."

For reference, this guide describes phrase characteristics and filtering considerations.

## Analysis

The phrase analysis report (`reports/phrase_analysis_plus.md`) shows:
- Distribution by word count (1-word, 2-word, 3-word, etc.)
- Distribution by character length
- Examples at each threshold
- Suggested filter thresholds

## Filtering Options

### By Word Count

Limit the number of space-separated words in a phrase:

```bash
# Keep only 1-3 word phrases (excludes long proverbs)
make export-wordlist-filtered-w3

# Keep only 1-4 word phrases
make export-wordlist-filtered-w4

# Custom word count
uv run python src/openword/export_wordlist_filtered.py \
  --distribution plus \
  --max-words 5
```

**Recommended:** `--max-words 3` keeps useful idioms while excluding most proverbs.

### By Character Length

Limit the total character length:

```bash
# Keep entries ≤50 characters
make export-wordlist-filtered-c50

# Custom character limit
uv run python src/openword/export_wordlist_filtered.py \
  --distribution plus \
  --max-chars 40
```

### Combined Filters

Apply both word count and character length filters:

```bash
# Keep ≤3 words AND ≤50 characters
make export-wordlist-filtered-w3c50

# Custom combination
uv run python src/openword/export_wordlist_filtered.py \
  --distribution plus \
  --max-words 3 \
  --max-chars 40
```

## Output Files

Filtered wordlists are saved with descriptive names:

- `data/build/plus/wordlist-w3.txt` - Max 3 words
- `data/build/plus/wordlist-w4.txt` - Max 4 words
- `data/build/plus/wordlist-c50.txt` - Max 50 characters
- `data/build/plus/wordlist-w3-c50.txt` - Max 3 words AND 50 chars

## Building Binary Tries with Filters

To build a binary trie from a filtered wordlist:

```bash
# 1. Generate filtered wordlist
make export-wordlist-filtered-w3

# 2. Build binary trie from filtered list
cd viewer
pnpm run build-trie ../data/build/plus/wordlist-w3.txt data/plus-w3.trie.bin
```

Or specify the input/output paths directly:

```bash
tsx src/build-trie.ts \
  ../data/build/plus/wordlist-w3.txt \
  data/plus-w3.trie.bin
```

## Recommended Thresholds

Based on typical Wiktionary content:

| Use Case | Filter | What It Keeps | What It Removes |
|----------|--------|---------------|-----------------|
| **Single words only** | `--max-words 1` | Individual words | All multi-word phrases |
| **Words + short idioms** | `--max-words 3` | "kick the bucket", "in front of" | Long proverbs, sayings |
| **Words + expressions** | `--max-words 4` | Most idioms and phrases | Very long expressions |
| **Character-based** | `--max-chars 50` | Most words and idioms | Proverbs, full sentences |
| **Conservative** | `--max-words 3 --max-chars 50` | High-quality lexicon | Long/unusual entries |

## Examples

### What Gets Filtered

With `--max-words 3`:
- ✗ "when you're up to your neck in alligators, it's hard to remember that your initial objective was to drain the swamp" (24 words)
- ✗ "give a man a fish and you feed him for a day; teach a man to fish and you feed him for a lifetime" (21 words)
- ✓ "break the ice" (3 words)
- ✓ "in front of" (3 words)

With `--max-chars 50`:
- ✗ "electroencephalographically" (27 chars) - if you want to exclude technical terms
- ✓ "kick the bucket" (15 chars)
- ✓ Most normal words and idioms

## Integration with Build Pipeline

To use filtered wordlists by default, you can modify the export step in your build workflow:

```bash
# Option 1: Export both full and filtered
make export-wordlist  # Full version
make export-wordlist-filtered-w3  # Filtered version

# Option 2: Use filtered for binary builds
make export-wordlist-filtered-w3
cd viewer
pnpm run build-trie ../data/build/plus/wordlist-w3.txt data/plus.trie.bin
```

## Verbose Output

To see exactly what gets filtered:

```bash
uv run python src/openword/export_wordlist_filtered.py \
  --distribution plus \
  --max-words 3 \
  --verbose
```

This shows up to 50 examples of filtered entries.

## No Filtering

To export without filters (same as `export_wordlist.py`):

```bash
uv run python src/openword/export_wordlist_filtered.py \
  --distribution plus
```
