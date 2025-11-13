# Analysis Workflow Guide

This guide documents all available analysis and reporting commands in the openword-lexicon project, organized by use case and workflow.

---

## Quick Reference

### Most Common Commands

```bash
# Run all analysis reports (comprehensive audit)
make analyze-all-reports

# Run enhanced metadata analysis only
make analyze-enhanced-metadata

# Run standard inspection reports
make reports

# Analyze game word filtering potential
make analyze-game-metadata
```

### Individual Report Commands

```bash
# Frequency tier analysis
make report-frequency-analysis

# Syllable data availability (requires Wiktionary dump)
make report-syllable-analysis

# WordNet concreteness categories
make report-wordnet-concreteness

# Wiktionary label statistics (requires Wiktionary JSONL)
make report-labels
```

---

## Complete Command Reference

### 1. Enhanced Metadata Analysis

These commands analyze metadata availability and structure in source datasets.

#### `make analyze-enhanced-metadata`
**What it does**: Runs all enhanced metadata analysis tools
- Frequency tier analysis
- Syllable data availability analysis
- WordNet concreteness category analysis

**Dependencies**:
- Frequency data (`data/raw/plus/en_50k.txt`)
- Wiktionary dump (`data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2`)
- NLTK WordNet (downloads automatically if needed)

**Outputs**:
- `reports/frequency_analysis.md`
- `reports/syllable_analysis.md`
- `reports/wordnet_concreteness.md`

**When to use**: After fetching data, before building pipeline, to understand what metadata will be available.

**Runtime**: ~2-5 minutes

**Example**:
```bash
# Fetch data first
make fetch-plus

# Run analysis
make analyze-enhanced-metadata

# Review reports
ls -lh reports/frequency_analysis.md \
         reports/syllable_analysis.md \
         reports/wordnet_concreteness.md
```

---

#### `make report-frequency-analysis`
**What it does**: Analyzes OpenSubtitles frequency data structure and tier distributions

**Dependencies**: `data/raw/plus/en_50k.txt`

**Outputs**: `reports/frequency_analysis.md`

**Key insights**:
- Frequency tier boundaries and coverage
- Sample words at each tier (top10, top100, top1k, top10k, top100k)
- Recommended tiers for different use cases (kids, games, education)

**Runtime**: < 1 minute

**Example**:
```bash
make report-frequency-analysis

# View tier distribution
cat reports/frequency_analysis.md
```

---

#### `make report-syllable-analysis`
**What it does**: Analyzes syllable data availability in Wiktionary

**Dependencies**: `data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2`

**Outputs**: `reports/syllable_analysis.md`

**Key insights**:
- Percentage of entries with hyphenation templates (~18.79%)
- Percentage with IPA syllable markers (~38.63%)
- Syllable count distribution
- Example words with syllable breakdowns
- Recommended extraction strategy for implementation

**Runtime**: ~1-2 minutes (samples 10,000 pages)

**Example**:
```bash
# Fetch Wiktionary first (large download)
make fetch-plus

# Analyze syllable data
make report-syllable-analysis

# Review coverage
grep "Pages with" reports/syllable_analysis.md
```

---

#### `make report-wordnet-concreteness`
**What it does**: Analyzes WordNet semantic categories for concrete/abstract classification

**Dependencies**: NLTK WordNet (downloads automatically if not present)

**Outputs**: `reports/wordnet_concreteness.md`

**Key insights**:
- All 26 WordNet lexicographer files (categories)
- 7 concrete categories (animals, artifacts, body, food, objects, plants, substances)
- 5 kids-appropriate categories with word counts
- 15 abstract categories
- Sample words and definitions for each category
- Integration strategy with existing pipeline

**Runtime**: ~5-10 seconds

**Example**:
```bash
# No data fetch required (uses NLTK)
make report-wordnet-concreteness

# View kids-appropriate categories
grep -A 30 "Kids-Appropriate Categories" reports/wordnet_concreteness.md
```

---

### 2. Standard Inspection Reports

These commands inspect the built lexicon and pipeline stages.

#### `make reports`
**What it does**: Generates all standard inspection reports via master script

**Dependencies**: Built lexicon (`make build-core` or `make build-plus`)

**Outputs**:
- `reports/raw_data_inspection.md`
- `reports/pipeline_inspection_core.md`
- `reports/pipeline_inspection_plus.md`
- `reports/trie_inspection_core.md`
- `reports/trie_inspection_plus.md`
- `reports/metadata_exploration_core.md`
- `reports/metadata_exploration_plus.md`
- `reports/distribution_comparison.md`

**When to use**: After building distributions, to verify pipeline stages and output quality.

**Runtime**: ~1-2 minutes

**Example**:
```bash
# Build lexicon first
make build-core

# Generate all inspection reports
make reports

# Review outputs
ls -lh reports/
```

---

#### Individual Report Commands

##### `make report-raw`
Inspects raw source datasets (ENABLE, EOWL, Wiktionary)

##### `make report-pipeline`
Inspects pipeline stages (core and plus)

##### `make report-trie`
Analyzes trie structure and size (core and plus)

##### `make report-metadata`
Analyzes metadata coverage (core and plus)

##### `make report-compare`
Compares core vs plus distributions

---

### 3. Game Word Filtering Analysis

These commands analyze metadata for game word filtering potential.

#### `make analyze-game-metadata`
**What it does**: Analyzes metadata coverage for game word filtering

**Dependencies**: Built lexicon with metadata

**Outputs**:
- `reports/game_metadata_analysis_core.md`
- `reports/game_metadata_analysis_plus.md`

**Key insights**:
- Field coverage percentages (POS, concreteness, frequency, labels)
- Noun analysis (concrete vs abstract distribution)
- Frequency distribution for nouns
- Label type usage
- Recommendations for filtering

**Runtime**: < 1 minute

**Example**:
```bash
# Build lexicon first
make build-core

# Analyze game metadata
make analyze-game-metadata

# Review coverage
cat reports/game_metadata_analysis_core.md
```

---

#### `make game-words`
**What it does**: Generates filtered game word lists using scoring algorithm

**Dependencies**: Built lexicon with metadata

**Outputs**:
- `data/game_words/words_core.txt` - Plain word list
- `data/game_words/words_scored_core.txt` - Words with scores
- `data/game_words/review_core.md` - Manual review report

**Scoring criteria**:
- Frequency (0-100 points)
- Concreteness (+20 bonus)
- Jargon penalty (-30)
- Length penalty (-10 to -20)

**When to use**: After building lexicon, to generate word banks for games like 20 Questions, Pictionary, etc.

**Runtime**: < 1 minute

**Example**:
```bash
# Generate game words
make game-words

# Review top candidates
head -20 data/game_words/words_scored_core.txt

# Read full review
cat data/game_words/review_core.md
```

---

### 4. Wiktionary-Specific Analysis

These commands analyze extracted Wiktionary data.

#### `make report-labels`
**What it does**: Analyzes Wiktionary label coverage and distribution

**Dependencies**: Extracted Wiktionary JSONL (`data/intermediate/plus/wikt.jsonl`)

**Outputs**:
- `reports/label_statistics.md`
- `reports/label_examples.json`

**Key insights**:
- Overall label coverage (~11.2%)
- Regional label distribution (en-GB, en-US, etc.)
- Register label distribution (vulgar, slang, formal, etc.)
- Temporal label distribution (archaic, obsolete, dated)
- Domain label distribution (medicine, law, computing, etc.)
- Part-of-speech distribution
- Label combinations
- Filtering feasibility for various use cases

**When to use**: After extracting Wiktionary data, before applying policy filters.

**Runtime**: ~2-3 minutes

**Example**:
```bash
# Extract Wiktionary first (long-running)
make build-wiktionary-json

# Analyze labels
make report-labels

# Check vulgar word count
grep "vulgar" reports/label_statistics.md
```

---

#### `make build-wiktionary-json`
**What it does**: Extracts Wiktionary dump to JSONL using fast scanner parser

**Dependencies**: Wiktionary dump

**Outputs**: `data/intermediate/plus/wikt.jsonl`

**When to use**: After fetching Wiktionary dump, before analyzing labels or building plus distribution.

**Runtime**: ~30-60 minutes (for full dump)

**Example**:
```bash
# Fetch dump first
make fetch-plus

# Extract (long-running)
make build-wiktionary-json

# Check output
wc -l data/intermediate/plus/wikt.jsonl
```

---

### 5. Comprehensive Analysis

#### `make analyze-all-reports`
**What it does**: Runs ALL available analysis and reporting commands in sequence

**Runs (in order)**:
1. Enhanced metadata analysis (frequency, syllable, WordNet)
2. Standard inspection reports (raw, pipeline, trie, metadata, comparison)
3. Game metadata analysis
4. Distribution comparison

**Dependencies**:
- Frequency data
- Wiktionary dump
- Built lexicon (core and/or plus)

**Outputs**: All reports in `reports/` directory

**When to use**:
- After major data updates
- For complete capability audits
- Before releases
- To generate comprehensive documentation

**Runtime**: ~5-10 minutes (depends on what's cached)

**Example**:
```bash
# Ensure data is fetched and built
make fetch-plus
make build-core

# Run comprehensive analysis
make analyze-all-reports

# Review all reports
ls -lh reports/*.md
```

---

## Workflow Examples

### Scenario 1: Initial Project Setup & Analysis

**Goal**: Understand project capabilities before building

```bash
# 1. Bootstrap environment
make bootstrap

# 2. Fetch all data
make fetch-plus

# 3. Analyze what metadata is available
make analyze-enhanced-metadata

# 4. Review reports to understand coverage
cat reports/frequency_analysis.md
cat reports/syllable_analysis.md
cat reports/wordnet_concreteness.md
```

**Time**: ~15-20 minutes (mostly downloading)

---

### Scenario 2: Building & Validating Lexicon

**Goal**: Build lexicon and verify quality

```bash
# 1. Build core distribution
make build-core

# 2. Generate all inspection reports
make reports

# 3. Analyze game metadata coverage
make analyze-game-metadata

# 4. Review outputs
cat reports/trie_inspection_core.md
cat reports/metadata_exploration_core.md
cat reports/game_metadata_analysis_core.md
```

**Time**: ~10-15 minutes

---

### Scenario 3: Filtering for Specific Use Cases

**Goal**: Generate specialized word lists

```bash
# 1. Build lexicon
make build-core

# 2. Generate game word lists
make game-words

# 3. Review candidates
cat data/game_words/review_core.md
head -50 data/game_words/words_scored_core.txt

# 4. For custom filtering, see FILTERING.md
```

**Time**: ~5 minutes

---

### Scenario 4: Complete Capability Audit

**Goal**: Generate all reports for documentation/release

```bash
# 1. Ensure everything is built
make build-core
make build-plus

# 2. Run comprehensive analysis
make analyze-all-reports

# 3. Review all outputs
ls -lh reports/

# 4. Package for review
tar -czf reports-$(date +%Y%m%d).tar.gz reports/
```

**Time**: ~10-15 minutes

---

### Scenario 5: Analyzing Wiktionary Labels

**Goal**: Understand label coverage for filtering

```bash
# 1. Extract Wiktionary (if not done)
make build-wiktionary-json

# 2. Analyze labels
make report-labels

# 3. Review label coverage
cat reports/label_statistics.md

# 4. Check example words
jq '.register.vulgar[:10]' reports/label_examples.json
```

**Time**: ~30-60 minutes (mostly extraction)

---

## Understanding Report Outputs

### Frequency Analysis Report

**File**: `reports/frequency_analysis.md`

**Key sections**:
- **Proposed Frequency Tiers**: Tier boundaries and coverage percentages
- **Sample Words by Tier**: Examples at each tier for validation
- **Usage in Filtering**: Recommendations for different use cases

**How to use**:
- Check if frequency data covers your target vocabulary
- Verify tier boundaries make sense for your application
- Use tier recommendations for filtering (e.g., top1k-top10k for kids)

---

### Syllable Analysis Report

**File**: `reports/syllable_analysis.md`

**Key sections**:
- **Availability**: Percentage with hyphenation templates
- **Syllable Count Distribution**: How many words have each syllable count
- **Hyphenation Examples**: Sample words with breakdowns
- **Extraction Strategy**: Implementation guide for integration

**How to use**:
- Understand current syllable data limitations (~18.79% coverage)
- See examples of syllable extraction accuracy
- Reference implementation strategy if adding syllable support

---

### WordNet Concreteness Report

**File**: `reports/wordnet_concreteness.md`

**Key sections**:
- **Concrete Noun Categories**: Physical/tangible categories
- **Kids-Appropriate Categories**: Recommended for children's vocabulary
- **Abstract Categories**: Non-concrete concepts
- **All Categories**: Complete list of WordNet lexicographer files
- **Integration Strategy**: How to use with existing pipeline

**How to use**:
- Identify semantic categories for filtering (e.g., only animals)
- Generate kids-appropriate word lists using recommended categories
- Understand concrete vs abstract classification approach

---

### Game Metadata Analysis Report

**Files**: `reports/game_metadata_analysis_core.md`, `reports/game_metadata_analysis_plus.md`

**Key sections**:
- **Field Coverage**: Percentages for each metadata field
- **Noun Analysis**: Concrete vs abstract distribution
- **Frequency Distribution**: Tier breakdown for nouns
- **Label Types**: Usage counts for each label category
- **Recommendations**: Suggested filtering approaches

**How to use**:
- Check if you have enough metadata for your filtering needs
- Understand trade-offs (e.g., concreteness only 34.5% coverage)
- Identify which fields can be used for filtering

---

### Label Statistics Report

**File**: `reports/label_statistics.md`

**Key sections**:
- **Overall Coverage**: Percentage of entries with any labels
- **Regional/Register/Temporal/Domain Distribution**: Label type breakdowns
- **Label Combinations**: Most common label patterns
- **Game-Specific Filtering Feasibility**: Assessment for common use cases

**How to use**:
- Understand label coverage limitations
- Identify which labels are well-represented (e.g., 3,286 vulgar words)
- Plan filtering strategies based on available labels

---

## Tips & Best Practices

### 1. Run Analysis Before Building
Understand metadata availability before investing time in full builds:
```bash
make analyze-enhanced-metadata  # Quick, no build needed
```

### 2. Use Comprehensive Analysis for Audits
When documenting capabilities or preparing releases:
```bash
make analyze-all-reports  # Generates everything
```

### 3. Check Dependencies First
Many commands require data or builds:
```bash
# For Wiktionary analysis
make fetch-plus

# For inspection reports
make build-core
```

### 4. Review Reports in Order
1. Metadata analysis (what's available)
2. Inspection reports (what was built)
3. Game analysis (how to filter)

### 5. Generate Fresh Reports After Changes
If you modify data sources or pipeline:
```bash
make clean-build
make build-core
make analyze-all-reports
```

---

## Troubleshooting

### "File not found" errors
**Problem**: Missing dependencies

**Solution**: Check what data/builds are required
```bash
# For metadata analysis
make fetch-plus

# For inspection reports
make build-core
```

---

### Reports seem outdated
**Problem**: Cached data from old builds

**Solution**: Clean and rebuild
```bash
make clean-build
make build-core
make reports
```

---

### Syllable analysis fails
**Problem**: Wiktionary dump not downloaded

**Solution**: Fetch data first
```bash
make fetch-plus  # Downloads 2-3 GB
```

---

### WordNet analysis fails
**Problem**: NLTK data not installed (should auto-download)

**Solution**: Install manually
```bash
uv run python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

---

## Advanced Usage

### Custom Analysis Scripts

You can also run analysis tools directly with custom parameters:

```bash
# Analyze more Wiktionary pages for syllable data
uv run python tools/analyze_syllable_data.py \
  data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
  50000  # Analyze 50,000 pages instead of 10,000

# Generate game words with custom scoring
uv run python tools/filter_game_words.py \
  --distribution core \
  --min-score 80 \
  --max-words 500 \
  --output-wordlist custom-game-words.txt \
  --output-scored custom-game-words-scored.txt \
  --output-review custom-review.md
```

### Filtering Wiktionary JSONL Directly

For custom analysis:

```bash
# Count entries with syllable data (if implemented)
jq 'select(has("syllables"))' data/intermediate/plus/wikt.jsonl | wc -l

# Extract all concrete nouns
jq -r 'select(.concreteness == "concrete" and (.pos | contains(["noun"]))) | .word' \
  data/intermediate/core/core_entries_enriched.jsonl

# Get frequency distribution
jq -r '.frequency_tier' data/intermediate/core/core_entries_enriched.jsonl \
  | sort | uniq -c | sort -rn
```

---

## See Also

- **[FILTERING.md](FILTERING.md)**: Query filtering and wordlist generation
- **[GAME_WORDS.md](GAME_WORDS.md)**: Game-specific word list filtering
- **[LOCAL_ANALYSIS.md](LOCAL_ANALYSIS.md)**: Running analysis locally
- **[USAGE.md](USAGE.md)**: General CLI usage examples
- **[DESIGN.md](DESIGN.md)**: Architecture and design decisions

---

**Report Issues**: If analysis commands fail or produce unexpected results, please report at https://github.com/macshonle/openword-lexicon/issues
