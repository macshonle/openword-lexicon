# OpenWord Lexicon - Interactive Word List Builder

The Interactive Word List Builder provides a user-friendly way to create custom filtered word lists from the OpenWord Lexicon. Instead of manually writing filter criteria, you can use the web interface to build a JSON specification that describes exactly what words you want.

---

## Quick Start

### Option 1: Web Interface

```bash
# Open web builder in browser
make wordlist-builder-web

# Or manually open
open tools/wordlist-builder/web-builder.html
```

The web interface provides a visual form-based builder with immediate feedback and allows you to see all available options at once.

### Option 2: Manual JSON Specification

Create a JSON file directly using the schema:

```json
{
  "version": "1.0",
  "name": "My Word List",
  "distribution": "core",
  "filters": {
    "character": {
      "min_length": 3,
      "max_length": 10
    },
    "frequency": {
      "tiers": ["top1k", "top3k", "top10k"]
    }
  }
}
```

---

## Generating Word Lists

Once you have a specification file, use the `owlex` command to generate your word list:

```bash
# Using Makefile
make owlex-filter SPEC=wordlist-spec.json > words.txt

# Or directly with owlex
uv run python -m openword.owlex wordlist-spec.json > words.txt

# With verbose output
uv run python -m openword.owlex wordlist-spec.json --verbose --output words.txt
```

---

## Complete Workflow Example

```bash
# 1. Build the English lexicon (one-time setup)
make build-en

# 2. Create a specification with web interface
make wordlist-builder-web

# 3. Generate the word list
make owlex-filter SPEC=wordlist-spec.json > my-words.txt

# 4. Review results
head -20 my-words.txt
wc -l my-words.txt
```

---

## Available Presets

The builder includes several pre-configured presets for common use cases:

### `wordle`
**Distribution**: Core
**Description**: 5-letter common words for Wordle-style games
**Filters**: Exact length 5, top 10k frequency, single words only

### `kids-nouns`
**Distribution**: Core
**Description**: Concrete nouns appropriate for children
**Filters**: 3-10 characters, top 1k-10k frequency, concrete nouns, family-friendly

### `scrabble`
**Distribution**: Core
**Description**: Single words for Scrabble
**Filters**: Single words only, top 100k frequency

### `profanity-blocklist`
**Distribution**: Plus (requires Wiktionary)
**Description**: Words flagged as vulgar, offensive, or derogatory
**Filters**: Include vulgar/offensive/derogatory register labels

### `crossword`
**Distribution**: Plus
**Description**: Words for crossword puzzles
**Filters**: Single words only, minimum 3 characters

To use a preset, open the web builder and select from the preset dropdown, or use the example specifications in `examples/wordlist-specs/`:

```bash
# Use an example preset specification
make owlex-filter SPEC=examples/wordlist-specs/wordle.json
```

---

## Architecture

The word list builder consists of three main components:

### 1. Specification Schema (`docs/schema/wordlist_spec.schema.json`)

Defines the JSON format for word list specifications. Includes:
- Distribution selection (core vs plus)
- Filter categories (character, frequency, POS, etc.)
- Output configuration (format, sorting, limits)

### 2. Decision Engine (`spec-builder.js`)

JavaScript library that:
- Works in both Node.js and browser environments
- Validates filter availability per distribution
- Provides capability metadata
- Expands policy filters to concrete criteria
- Estimates result counts

### 3. Interactive Builder

**Web Builder** (`web-builder.html`):
- Visual form-based interface
- Real-time validation and feedback
- See all available options at once
- Download or copy specification
- Works offline (no server required)

### 4. Filter Engine (`owlex.py`)

Python CLI tool that:
- Reads JSON specifications
- Filters JSONL entry data
- Supports all filter types
- Outputs in multiple formats (text, JSON, CSV, TSV)

---

## Filter Capabilities

### Distribution-Dependent Features

| Feature | Core | Plus | Coverage |
|---------|------|------|----------|
| Character filters | ✅ | ✅ | 100% |
| Frequency tiers | ✅ | ✅ | 100% |
| POS tags | ✅ | ✅ | ~52.5% |
| Concreteness | ✅ | ✅ | 34.5% (Core), 8.8% (Plus) |
| Register labels | ❌ | ✅ | ~3.2% |
| Domain labels | ❌ | ✅ | ~3.3% |
| Temporal labels | ❌ | ✅ | ~5.0% |
| Region labels | ❌ | ✅ | ~1.9% |

**Core Distribution**: Ultra-permissive licenses (Public Domain, UKACD). Best for commercial projects.

**Plus Distribution**: Includes Wiktionary (CC BY-SA 4.0). Required for label-based filtering and maximum vocabulary coverage.

### Filter Types

**Character Filters** (Always available):
- Exact, min, or max length
- Regex patterns
- Starts with / ends with / contains

**Frequency Filters** (Always available):
- 10 tiers: top10, top100, top300, top500, top1k, top3k, top10k, top25k, top50k, rare
- Based on OpenSubtitles 2018 corpus (50,000 words)
- Linguistically meaningful breakpoints (esp. top3k = 95% comprehension)
- 100% coverage (all words assigned a tier)

**POS Filters** (~52.5% coverage):
- Filter by part of speech
- Options: noun, verb, adjective, adverb, etc.
- Via WordNet enrichment

**Concreteness Filters** (34.5% Core, 8.8% Plus):
- Concrete (physical objects)
- Abstract (ideas, concepts)
- Mixed (both senses)
- Nouns only

**Label Filters** (Plus only, ~3-5% coverage):
- **Register**: vulgar, offensive, slang, formal, etc.
- **Domain**: medical, legal, technical, etc.
- **Temporal**: archaic, obsolete, dated, modern
- **Region**: en-US, en-GB, etc.

**Policy Filters** (Convenience shortcuts):
- `family_friendly`: Exclude vulgar/offensive/derogatory
- `modern_only`: Exclude archaic/obsolete/dated
- `no_jargon`: Exclude technical/medical/legal/scientific

For complete filter documentation, see [FILTER_CAPABILITIES.md](../../docs/FILTER_CAPABILITIES.md).

---

## Specification Format

### Minimal Example

```json
{
  "version": "1.0",
  "distribution": "core"
}
```

This outputs all words from the core distribution with no filtering.

### Complete Example

```json
{
  "version": "1.0",
  "name": "Educational Vocabulary",
  "description": "Common words for language learners",
  "distribution": "core",
  "filters": {
    "character": {
      "min_length": 3,
      "max_length": 12,
      "pattern": "^[a-z]+$"
    },
    "phrase": {
      "max_words": 1
    },
    "frequency": {
      "tiers": ["top1k", "top3k", "top10k"]
    },
    "pos": {
      "include": ["noun", "verb", "adjective"],
      "require_pos": true
    },
    "policy": {
      "family_friendly": true,
      "modern_only": true
    }
  },
  "output": {
    "format": "text",
    "sort_by": "frequency",
    "limit": 1000
  }
}
```

### Validation

Specifications are validated when loaded:

1. **Required fields**: `version`, `distribution`
2. **Distribution availability**: Filters must be available on selected distribution
3. **Coverage warnings**: Low-coverage filters generate warnings

The interactive builders handle validation automatically.

---

## Output Formats

### Plain Text (default)

```
apple
banana
castle
```

### JSON

```json
["apple", "banana", "castle"]
```

Or with metadata:

```json
[
  {
    "word": "apple",
    "pos": ["noun"],
    "frequency_tier": "top10k",
    "concreteness": "concrete"
  }
]
```

### CSV/TSV

```csv
word,frequency_tier,concreteness
apple,top10k,concrete
banana,top10k,concrete
```

### JSON Lines (JSONL)

```jsonl
{"word":"apple","pos":["noun"],"frequency_tier":"top10k"}
{"word":"banana","pos":["noun"],"frequency_tier":"top10k"}
```

---

## Advanced Usage

### Combining Multiple Filters

All filters use AND logic. To get nouns that are both concrete AND common:

```json
{
  "filters": {
    "pos": { "include": ["noun"] },
    "concreteness": { "values": ["concrete"] },
    "frequency": { "tiers": ["top1k", "top10k"] }
  }
}
```

### Excluding vs Including

For labels, you can include or exclude:

```json
{
  "filters": {
    "labels": {
      "register": {
        "exclude": ["vulgar", "offensive"]
      }
    }
  }
}
```

### Scoring and Sorting

Enable scoring to rank words:

```json
{
  "output": {
    "sort_by": "score",
    "limit": 100
  }
}
```

Scoring considers:
- Frequency (higher = better)
- Concreteness (concrete nouns get bonus)
- Length (very long words penalized)
- Domain (technical domains penalized)

### Requiring Metadata

To only include words with specific metadata:

```json
{
  "filters": {
    "pos": {
      "include": ["noun"],
      "require_pos": true
    },
    "concreteness": {
      "values": ["concrete"],
      "require_concreteness": true
    }
  }
}
```

This excludes words without POS or concreteness data.

---

## Programmatic Usage

### JavaScript (Node.js or Browser)

```javascript
const { SpecBuilder, helpers } = require('./spec-builder.js');

// Create builder
const builder = new SpecBuilder();

// Configure
builder
  .setDistribution('core')
  .setMetadata('My Word List', 'Custom filtering')
  .addFilter('character', 'exact_length', 5)
  .addFilter('frequency', 'tiers', ['top1k', 'top10k'])
  .setPolicyFilter('family_friendly', true)
  .setOutput({ format: 'json', limit: 100 });

// Build and validate
const { spec, validation } = builder.build();

// Check for warnings
if (validation.warnings.length > 0) {
  console.log('Warnings:', validation.warnings);
}

// Export
const json = builder.toJSON();
console.log(json);
```

### Python

```python
from openword.owlex import OwlexFilter

# Load specification
filter_engine = OwlexFilter(Path('wordlist-spec.json'))

# Run filter
filter_engine.run(output_path=Path('output.txt'), verbose=True)
```

---

## Troubleshooting

### "Distribution not built"

**Error**: `No input file found for distribution 'core'`

**Solution**: Build the distribution first:
```bash
make build-core  # or make build-plus
```

### "Low coverage warning"

**Warning**: `Filter 'concreteness' has low coverage (8.8%)`

**Explanation**: Not all words have this metadata. Use `require_*` flags to exclude words without the metadata, or accept the gaps.

### Empty Results

If your filter produces 0 results:
1. Check if filters are too restrictive
2. Remove `require_*` flags
3. Use broader frequency tiers
4. Check distribution has necessary metadata

### Validation Errors

**Error**: `Filter 'labels' is not available on 'core' distribution`

**Solution**: Switch to Plus distribution or remove label filters.

---

## Examples

### Example 1: Wordle Word List

```bash
# Create specification
cat > wordle-spec.json << 'EOF'
{
  "version": "1.0",
  "name": "Wordle Words",
  "distribution": "core",
  "filters": {
    "character": {
      "exact_length": 5,
      "pattern": "^[a-z]+$"
    },
    "phrase": { "max_words": 1 },
    "frequency": { "min_tier": "top10k" }
  },
  "output": {
    "sort_by": "frequency",
    "limit": 2315
  }
}
EOF

# Generate word list
make owlex-filter SPEC=wordle-spec.json > wordle-words.txt

# Review
head wordle-words.txt
```

### Example 2: Kids' Vocabulary

```bash
# Use example preset
make owlex-filter SPEC=examples/wordlist-specs/kids-nouns.json > kids-words.txt

# Or use web builder to create custom specification:
# make wordlist-builder-web
# Then select:
# - Distribution: core
# - Character: 3-10 length
# - Frequency: top1k, top10k
# - POS: noun
# - Concreteness: concrete
# - Policy: family_friendly, modern_only
```

### Example 3: Profanity Filter

```bash
# Create specification (requires Plus)
cat > profanity-spec.json << 'EOF'
{
  "version": "1.0",
  "name": "Profanity Blocklist",
  "distribution": "plus",
  "filters": {
    "labels": {
      "register": {
        "include": ["vulgar", "offensive", "derogatory"]
      }
    }
  }
}
EOF

# Build Plus distribution first
make build-plus

# Generate blocklist
make owlex-filter SPEC=profanity-spec.json > profanity-blocklist.txt
```

---

## Documentation

- **[FILTER_CAPABILITIES.md](../../docs/FILTER_CAPABILITIES.md)** - Complete filter reference
- **[wordlist_spec.schema.json](../../docs/schema/wordlist_spec.schema.json)** - JSON schema
- **[CAPABILITY_AUDIT.md](../../CAPABILITY_AUDIT.md)** - System capabilities audit

---

## Contributing

To add new filter types:

1. Update `spec-builder.js` CAPABILITIES
2. Update `owlex.py` filter methods
3. Update `wordlist_spec.schema.json`
4. Update documentation

To add new presets:

1. Add to `CAPABILITIES.presets` in `spec-builder.js`
2. Update this README

---

## License

The word list builder tools are part of the openword-lexicon project and follow the same license (Apache 2.0 for code).

Generated word lists follow the license of the source distribution:
- **Core**: Ultra-permissive (Public Domain, UKACD)
- **Plus**: CC BY-SA 4.0 (attribution required for Wiktionary content)

---

## Questions?

Open an issue at https://github.com/macshonle/openword-lexicon/issues
