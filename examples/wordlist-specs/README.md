# Example Word List Specifications

This directory contains example JSON specifications for common word list filtering scenarios.

## Usage

To generate a word list from any of these specifications:

```bash
# Using Makefile
make owlex-filter SPEC=examples/wordlist-specs/wordle.json > wordle-words.txt

# Or directly with owlex
uv run python -m openword.owlex examples/wordlist-specs/wordle.json > wordle-words.txt
```

## Available Examples

### `wordle.json`
**Distribution**: Core
**Target**: Wordle-style word guessing games
**Filters**:
- Exactly 5 letters
- Only lowercase alphabetic characters
- Single words only
- Top 10k frequency or better

**Expected results**: ~2,000-3,000 words

---

### `kids-nouns.json`
**Distribution**: Core
**Target**: Children's educational games
**Filters**:
- 3-10 characters
- Concrete nouns only
- Top 1k-10k frequency
- Family-friendly (no profanity)
- Modern language only

**Expected results**: ~500-1,000 words

**Note**: Requires WordNet enrichment (automatic during build)

---

### `profanity-blocklist.json`
**Distribution**: Plus (requires Wiktionary)
**Target**: Content filtering systems
**Filters**:
- Words labeled as vulgar, offensive, or derogatory

**Expected results**: ~10,000 words

**Note**:
- Must build Plus distribution first: `make build-plus`
- Coverage is ~11% - some inappropriate words may not be labeled
- Combine with external blocklists for production use

---

### `scrabble.json`
**Distribution**: Core
**Target**: Scrabble and word games
**Filters**:
- Single words only (no phrases)
- Top 100k frequency or better

**Expected results**: ~100,000-150,000 words

---

## Creating Your Own

### Method 1: Interactive CLI

```bash
make wordlist-builder-cli
```

Follow the prompts to build your specification.

### Method 2: Web Interface

```bash
make wordlist-builder-web
```

Use the visual form to configure filters.

### Method 3: Copy and Modify

Copy one of these examples and edit:

```bash
cp examples/wordlist-specs/wordle.json my-spec.json
# Edit my-spec.json
make owlex-filter SPEC=my-spec.json > my-words.txt
```

---

## Schema Reference

All specifications must follow this structure:

```json
{
  "version": "1.0",           // Required: schema version
  "name": "...",              // Optional: human-readable name
  "description": "...",       // Optional: description
  "distribution": "core",     // Required: "core" or "plus"
  "filters": {                // Optional: filter criteria
    "character": {...},
    "phrase": {...},
    "frequency": {...},
    "pos": {...},
    "concreteness": {...},
    "labels": {...},
    "policy": {...}
  },
  "output": {                 // Optional: output configuration
    "format": "text",
    "sort_by": "alphabetical",
    "limit": 1000
  }
}
```

See [docs/schema/wordlist_spec.schema.json](../../docs/schema/wordlist_spec.schema.json) for complete schema.

---

## Testing Specifications

Test your specification before generating large lists:

```bash
# Preview first 20 results
make owlex-filter SPEC=my-spec.json | head -20

# Count total matches
make owlex-filter SPEC=my-spec.json | wc -l

# Verbose mode for debugging
uv run python -m openword.owlex my-spec.json --verbose | head -20
```

---

## Tips

### Combining Specifications

You can combine multiple filtered lists:

```bash
# Generate individual lists
make owlex-filter SPEC=examples/wordlist-specs/wordle.json > wordle.txt
make owlex-filter SPEC=my-hard-words.json > hard.txt

# Combine
cat wordle.txt hard.txt | sort -u > combined.txt
```

### Excluding Words

To exclude profanity from your list:

```bash
# Generate main list
make owlex-filter SPEC=my-spec.json > words.txt

# Generate blocklist (requires Plus)
make owlex-filter SPEC=examples/wordlist-specs/profanity-blocklist.json > blocked.txt

# Remove blocked words
grep -vFxf blocked.txt words.txt > clean-words.txt
```

### Performance

For very large lists, use JSONL output for better performance:

```json
{
  "output": {
    "format": "jsonl",
    "include_metadata": false
  }
}
```

Then extract words:

```bash
make owlex-filter SPEC=my-spec.json | jq -r '.word' > words.txt
```

---

## Documentation

- [Word List Builder README](../README.md) - Complete builder documentation
- [Filter Capabilities](../../docs/FILTER_CAPABILITIES.md) - Available filters and coverage
- [JSON Schema](../../docs/schema/wordlist_spec.schema.json) - Specification format

---

## Contributing

Have a useful specification? Submit a pull request!

1. Create your specification in this directory
2. Add documentation to this README
3. Test that it works on both Core and Plus (if applicable)
4. Submit PR with description of use case
