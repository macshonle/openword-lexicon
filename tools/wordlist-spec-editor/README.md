# OpenWord Lexicon - Wordlist Spec Editor

A web UI for creating wordlist filter specifications (YAML/JSON) for the OpenWord Lexicon. Design filter specs visually, then use them with the `owlex` CLI to generate word lists for games, educational apps, language learning tools, and more.

This directory contains two web interfaces:
- **[index.html](index.html)** - Advanced builder with dynamic filters and source selection (recommended)
- **[web-builder.html](web-builder.html)** - Basic builder with form-based interface

---

## Quick Start (New Advanced Builder)

1. **Start the server**: Run `make spec-editor-web` from the project root
2. **Select sources**: Choose word sources in the left panel (EOWL + Wiktionary checked by default)
3. **Add filters**: Click filter type buttons to add filters dynamically
4. **Configure filters**: Set each filter to "Must Include" or "Must Not Include" mode
5. **Export**: View or download your JSON specification

```bash
# Start the web server (from project root)
make spec-editor-web

# Server will start at: http://localhost:8000
# Requires: pnpm (install with: npm install -g pnpm)
```

**Why a server?** The builder needs to fetch `build-statistics.json` via HTTP. Opening the HTML file directly (`file://`) causes CORS errors that prevent data loading.

## Features

- **Interactive Source Selection**: Choose from EOWL, Wiktionary, WordNet, Brysbaert, and Frequency data
- **Dynamic Filter System**: Add and remove filters on demand with include/exclude modes
- **Real-time Statistics**: See accurate word counts and metadata availability based on actual build data
- **Build Statistics Integration**: Uses `build-statistics.json` for precise estimates
- **Quick Start Demos**: Pre-configured templates for common use cases (Wordle, Kids Nouns, Scrabble, Profanity, British English)
- **JSON Export**: Generate specifications compatible with owlex filter tool
- **License Tracking**: Automatic license calculation based on selected sources

## Build Statistics

The advanced builder uses `build-statistics.json` to provide accurate, real-time estimates of word counts and metadata coverage. This file is generated from the build data.

### Generating Statistics

Statistics are automatically generated during the build process:

```bash
# Build the lexicon (statistics generated automatically)
make build-en
```

This creates/updates `tools/wordlist-spec-editor/build-statistics.json` with:
- **Total word counts** by source combination
- **License requirements** distribution
- **Metadata coverage** percentages (POS tags, labels, concreteness, etc.)
- **Source distributions** (how words are shared across sources)

### How Estimates Work

The builder uses actual source combination data to calculate precise estimates:

1. When you select "EOWL + Wiktionary", it sums:
   - Words in `eowl` only
   - Words in `wikt` only
   - Words in `eowl,wikt`
   - Any other combinations that include both

2. Example from actual data:
   ```
   Wiktionary only:        1,095,480 words
   EOWL + Wiktionary:      1,303,681 words (union of all combinations)
   ```

### Statistics File Format

```json
{
  "total_words": 1303681,
  "sources": {
    "eowl": 129037,
    "wikt": 1294779
  },
  "source_combinations": {
    "wikt": 1095480,
    "enable,eowl,wikt": 92899,
    "enable,wikt": 74274,
    ...
  },
  "metadata_coverage": {
    "pos_tags": { "count": 1282956, "percentage": 98.4 },
    "any_labels": { "count": 146589, "percentage": 11.2 },
    ...
  }
}
```

### Fallback Behavior

If `build-statistics.json` cannot be loaded (e.g., file not generated yet), the builder uses default estimates. Statistics are automatically generated during `make build-en`.

---

## Generating Word Lists

Once you have a specification file, use the `owlex` command to generate your word list:

```bash
# Using owlex directly
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
make spec-editor-web

# 3. Generate the word list
uv run python -m openword.owlex wordlist-spec.json > my-words.txt

# 4. Review results
head -20 my-words.txt
wc -l my-words.txt
```

---

## Word Sources (New Builder)

### Primary Sources

**EOWL (English Open Word List)** - 128,983 words
- British English, up to 10 letters
- No proper nouns, no hyphens
- License: UKACD License (attribution required)

**Wiktionary** - 1,294,779 words
- Comprehensive multilingual dictionary
- Rich metadata: POS tags, labels, regional variants, morphology
- License: CC BY-SA 4.0

### Enrichment Sources

**WordNet** - 90,931 enriched entries
- POS tags and concreteness classification
- License: WordNet License (permissive)

**Brysbaert Concreteness Ratings** - 39,558 rated words
- Empirical concreteness ratings on 1-5 scale
- Excellent for children's apps and accessibility tools
- License: Research/Educational Use

**Frequency Data** - 100% coverage
- 12-level tiers A-L (plus Y/Z for rare/unknown) from OpenSubtitles 2018
- Modern, conversational vocabulary
- License: CC BY-SA 4.0

## Filter Types (New Builder)

### Character Filter 🔤
Filter by word length, patterns, and character constraints.

**Options:**
- Minimum/maximum length
- Regular expression pattern
- Starts with, ends with, contains

**Example:** 5-letter words for Wordle, words starting with "un-"

### Phrase Filter 💬
Filter by word count (single words vs multi-word phrases).

**Options:**
- Multi-word phrases only / Single words only
- Minimum/maximum word count

**Example:** Single words for Scrabble, exclude multi-word entries

### Part of Speech Filter 📝
Filter by grammatical category (requires Wiktionary or WordNet).

**Options:** Nouns, verbs, adjectives, adverbs, pronouns, prepositions, etc.

**Example:** Concrete nouns for kids' games, action verbs for learning

### Frequency Filter 📊
Filter by word frequency tier (requires Frequency Data).

**Tiers:** A (ranks 1-20) → B (21-100) → ... → L (75k-100k) → Y (very rare) → Z (unknown)

**Example:** Common words (A-F, top ~3000) for beginners, broader vocabulary (A-I, top ~30k) for general use

### Region Filter 🌍
Filter by regional variants (requires Wiktionary).

**Options:** en-GB, en-US, en-AU, en-CA, en-NZ, en-ZA, en-IE, en-IN

**Example:** British English spelling, American English vocabulary

### Concreteness Filter 🎨
Filter by concreteness level (requires WordNet or Brysbaert).

**Options:** Concrete (tangible), Mixed, Abstract (intangible)

**Example:** Concrete nouns for children's games, abstract concepts for advanced learners

### Labels Filter 🏷️
Filter by usage labels and register (requires Wiktionary).

**Options:** vulgar, offensive, slang, informal, formal, archaic, obsolete, dated, rare, colloquial, dialectal, technical, literary, humorous, derogatory, euphemistic

**Examples:**
- **Include vulgar**: Build profanity blocklist
- **Exclude vulgar**: Family-friendly word games
- **Include archaic**: Historical fiction vocabulary

## Filter Modes

Each filter can operate in two modes:

### Must Include (Green Border)
**Only show words that match this filter**

Use for building specialized lists (e.g., only vulgar words for blocklist, only concrete nouns)

### Must Not Include (Red Border)
**Hide words that match this filter**

Use for filtering out unwanted categories (e.g., exclude vulgar words, exclude multi-word phrases)

## Demo Presets (New Builder)

The advanced builder includes five pre-configured presets accessible from the "Quick Start" dropdown:

### Wordle Words
5-letter words, common frequency, single words only.

**Sources:** EOWL, Wiktionary, WordNet, Frequency
**Filters:**
- Character: 5 letters exactly (Must Include)
- Frequency: Common words A-H (Must Include)
- Phrase: Single words only (Must Include)

### Kids Game (Concrete Nouns)
Concrete, tangible objects for children's educational apps.

**Sources:** EOWL, Wiktionary, WordNet, Brysbaert, Frequency
**Filters:**
- POS: Nouns only (Must Include)
- Concreteness: Concrete words, Brysbaert preferred (Must Include)
- Character: 3-10 letters (Must Include)
- Frequency: Common words A-G (Must Include)
- Labels: No vulgar/offensive/slang (Must Not Include)

### Scrabble Words
Valid single words for word games.

**Sources:** EOWL, Wiktionary, WordNet
**Filters:**
- Phrase: Single words only (Must Include)
- Character: 2-15 letters (Must Include)

### Profanity Blocklist
Words marked as vulgar or offensive.

**Sources:** Wiktionary only (for label data)
**Filters:**
- Labels: Vulgar or offensive (Must Include)

### British English Common Words
Common British English vocabulary.

**Sources:** EOWL, Wiktionary, Frequency
**Filters:**
- Region: British English (en-GB) (Must Include)
- Frequency: Common words A-E (Must Include)

---

## JSON Specification Format (New Builder)

The advanced builder generates JSON specifications with this structure:

```json
{
  "version": "1.0",
  "sources": ["eowl", "wiktionary", "wordnet", "frequency"],
  "filters": [
    {
      "type": "character",
      "mode": "include",
      "config": {
        "minLength": 5,
        "maxLength": 5
      }
    },
    {
      "type": "frequency",
      "mode": "include",
      "config": {
        "rarestAllowed": "H"
      }
    },
    {
      "type": "labels",
      "mode": "exclude",
      "config": {
        "labels": ["vulgar", "offensive"]
      }
    }
  ]
}
```

### Fields

- **version**: Specification format version (currently "1.0")
- **sources**: Array of source IDs to include (`eowl`, `wiktionary`, `wordnet`, `brysbaert`, `frequency`)
- **filters**: Array of filter objects, each with:
  - **type**: Filter type (`character`, `phrase`, `pos`, `frequency`, `region`, `concreteness`, `labels`)
  - **mode**: Filter mode (`include` or `exclude`)
  - **config**: Filter-specific configuration object

### License Calculation

The builder automatically determines the license based on selected sources:

- **CC BY-SA 4.0**: Wiktionary or Frequency Data included (ShareAlike required)
- **CC BY 4.0**: EOWL only, or EOWL + permissive enrichments (WordNet, Brysbaert)

### Metadata Coverage

Statistics shown in the builder:

- **POS Tags**: 98.8% coverage (from Wiktionary + WordNet)
- **Labels**: 11.3% coverage (from Wiktionary)
- **Concreteness**: 8.6% coverage (from WordNet + Brysbaert)
- **Regional Labels**: 1.9% coverage (from Wiktionary)

---

## Architecture

This directory contains two builder implementations:

### New Advanced Builder (index.html, styles.css, app.js)

**Features:**
- Pure vanilla JavaScript (~850 lines total logic)
- Client-side state management
- Dynamic filter add/remove system
- Real-time statistics updates
- Source-based dependency tracking
- Modern responsive design

**Files:**
- `index.html` - Main UI structure (~400 lines)
- `styles.css` - Complete styling (~600 lines)
- `app.js` - State management and logic (~850 lines)

**Browser Requirements:** ES6+ support (Chrome 60+, Firefox 60+, Safari 12+, Edge 79+)

### Basic Builder (web-builder.html, spec-builder.js)

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
- 12 tiers A-L with explicit boundaries, plus Y (very rare) and Z (unknown)
- A: ranks 1-20, B: 21-100, C: 101-300, D: 301-500, E: 501-1000
- F: 1001-3000, G: 3001-5000, H: 5001-10000, I: 10001-30000
- J: 30001-50000, K: 50001-75000, L: 75001-100000, Y: 100001+
- Based on OpenSubtitles 2018 corpus
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
      "rarest_allowed": "H"
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
    "frequency_tier": "H",
    "concreteness": "concrete"
  }
]
```

### CSV/TSV

```csv
word,frequency_tier,concreteness
apple,H,concrete
banana,H,concrete
```

### JSON Lines (JSONL)

```jsonl
{"word":"apple","pos":["noun"],"frequency_tier":"H"}
{"word":"banana","pos":["noun"],"frequency_tier":"H"}
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
    "frequency": { "rarest_allowed": "H" }
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
  .addFilter('frequency', 'rarest_allowed', 'H')
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
    "frequency": { "rarest_allowed": "H" }
  },
  "output": {
    "sort_by": "frequency",
    "limit": 2315
  }
}
EOF

# Generate word list
uv run python -m openword.owlex wordle-spec.json > wordle-words.txt

# Review
head wordle-words.txt
```

### Example 2: Kids' Vocabulary

```bash
# Use example preset
uv run python -m openword.owlex examples/wordlist-specs/kids-nouns.json > kids-words.txt

# Or use spec editor to create custom specification:
# make spec-editor-web
# Then select:
# - Distribution: core
# - Character: 3-10 length
# - Frequency: A-H (top ~10k)
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
uv run python -m openword.owlex profanity-spec.json > profanity-blocklist.txt
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

## Use Cases

### Educational Apps
- Children's vocabulary games (concrete nouns, common words)
- Language learning tools (frequency-based progression)
- Spelling bee word lists (length-based tiers)

### Word Games
- Wordle-style games (5-letter common words)
- Scrabble word lists (single words, no proper nouns)
- Crossword puzzle generators (frequency-filtered vocabulary)

### Content Filtering
- Profanity blocklists (vulgar/offensive labels)
- Family-friendly word lists (exclude inappropriate content)
- Age-appropriate vocabulary (frequency + concreteness)

### NLP & Research
- Concrete vs abstract word classification
- Regional dialect comparison
- Morphological analysis (word families)
- Frequency-based vocabulary sampling

---

## See Also

- **[DATASETS.md](../../docs/DATASETS.md)** - Detailed source dataset documentation
- **[SCHEMA.md](../../docs/SCHEMA.md)** - Entry schema and field descriptions
- **[labels.md](../../docs/labels.md)** - Complete label taxonomy
- **[ATTRIBUTION.md](../../ATTRIBUTION.md)** - Full source credits

---

## Questions?

Open an issue at https://github.com/macshonle/openword-lexicon/issues
