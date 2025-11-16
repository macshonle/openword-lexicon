# Filtering Examples

This directory contains practical examples demonstrating how to filter and extract specialized word lists from the openword-lexicon.

---

## Available Examples

### 1. `filter_kids_vocabulary.sh`
**Extract age-appropriate vocabulary for children's apps/games**

Filters for:
- Concrete nouns (physical objects)
- Common words (top 1k-10k frequency)
- Short words (3-10 characters)
- Family-friendly (no profanity)
- Modern language (not archaic)

**Usage**:
```bash
# Build lexicon first
make build-core

# Run filter
./examples/filter_kids_vocabulary.sh

# Output: kids_vocabulary.txt
```

**Example output**:
```
animal
apple
ball
bicycle
bird
book
...
```

---

### 2. `create_profanity_blocklist.sh`
**Generate a profanity filter blocklist from Wiktionary labels**

Extracts words labeled as:
- Vulgar
- Offensive
- Derogatory

**Usage**:
```bash
# Build Wiktionary data
make build-wiktionary-json

# Run filter
./examples/create_profanity_blocklist.sh

# Output: profanity_blocklist.txt
```

**Important notes**:
- Label coverage is ~11.2% (some words may not be labeled)
- Context matters - manual review recommended
- Consider combining with external blocklists

---

### 3. `filter_by_semantic_category.sh`
**Extract words from specific WordNet semantic categories**

Available categories:
- **Concrete**: animal, artifact, body, food, plant, substance, object
- **Abstract**: cognition, feeling, attribute, act, time, etc.

**Usage**:
```bash
# Build lexicon first
make build-core

# Filter by category
./examples/filter_by_semantic_category.sh noun.animal
./examples/filter_by_semantic_category.sh noun.food

# Outputs: noun_animal_words.txt, noun_food_words.txt
```

**Note**: Currently uses broad concreteness classification (concrete vs abstract). For precise category filtering, the `wordnet_lexname` field would need to be added to the enrichment pipeline.

---

## Requirements

All examples require:
- **jq**: JSON processor for filtering
  - Install: `sudo apt-get install jq` (Ubuntu/Debian)
  - Install: `brew install jq` (macOS)
- **Built lexicon**: Run `make build-core` or `make build-plus` first

Individual requirements:
- Examples 1 & 3: Core distribution (`make build-core`)
- Example 2: Wiktionary JSONL (`make build-wiktionary-json`)

---

## Adapting the Examples

These scripts are templates - feel free to modify the filtering criteria:

### Adjust Age Appropriateness
Edit `filter_kids_vocabulary.sh`:
```bash
# For younger children (top 1k only, shorter words)
(.frequency_tier == "top1k") and
(.word | length >= 3 and length <= 6) and

# For older children (include up to top 50k, longer words)
(.frequency_tier == "top1k" or
 .frequency_tier == "top3k" or
 .frequency_tier == "top10k" or
 .frequency_tier == "top25k" or
 .frequency_tier == "top50k") and
(.word | length >= 3 and length <= 15) and
```

### Include Verbs or Adjectives
```bash
# Add to kids vocabulary filter
(.pos | contains(["noun", "verb", "adjective"])) and
```

### Adjust Blocklist Strictness
Edit `create_profanity_blocklist.sh`:
```bash
# More strict: include slang
(contains(["vulgar"]) or
 contains(["offensive"]) or
 contains(["derogatory"]) or
 contains(["slang"]))

# Less strict: only truly offensive
(contains(["vulgar"]) or contains(["offensive"]))
```

### Filter by Word Length
```bash
# Only short words (e.g., for mobile UI)
(.word | length >= 3 and length <= 8) and

# Only long words (e.g., for advanced puzzles)
(.word | length >= 10) and
```

### Filter by Frequency Tier
```bash
# Ultra-common (top 1000)
.frequency_tier == "top1k"

# Common to somewhat rare (top 3k to 50k)
(.frequency_tier == "top3k" or .frequency_tier == "top10k" or .frequency_tier == "top25k" or .frequency_tier == "top50k")

# Include rare words for crosswords
.frequency_tier == "rare"
```

---

## Common Filtering Patterns

### Combine Multiple Filters
```bash
# Extract animals from kids vocabulary
jq -r 'select(
    (.pos | contains(["noun"])) and
    .concreteness == "concrete" and
    (.frequency_tier == "top1k" or .frequency_tier == "top10k") and
    (.word | length >= 3 and length <= 10) and
    .is_phrase == false
    # TODO: and .wordnet_lexname == "noun.animal"
) | .word' data/intermediate/core/core_entries_enriched.jsonl
```

### Exclude Words from Another List
```bash
# Create family-friendly word list
./examples/filter_kids_vocabulary.sh

# Create blocklist
./examples/create_profanity_blocklist.sh

# Combine (exclude profanity from kids list)
grep -vFxf profanity_blocklist.txt kids_vocabulary.txt > safe_kids_vocabulary.txt
```

### Merge Multiple Lists
```bash
# Create themed word sets
./examples/filter_by_semantic_category.sh noun.animal > animals.txt
./examples/filter_by_semantic_category.sh noun.food > food.txt
./examples/filter_by_semantic_category.sh noun.plant > plants.txt

# Combine into nature-themed list
cat animals.txt food.txt plants.txt | sort -u > nature_words.txt
```

---

## Advanced Usage

### Export with Metadata
Instead of just words, include scores or other metadata:

```bash
# Export with frequency tier
jq -r 'select(
    (.pos | contains(["noun"])) and
    .concreteness == "concrete"
) | "\(.word)\t\(.frequency_tier)"' \
  data/intermediate/core/core_entries_enriched.jsonl > words_with_frequency.tsv

# Export with multiple fields
jq -r 'select(
    (.pos | contains(["noun"]))
) | "\(.word)\t\(.concreteness)\t\(.frequency_tier)\t\(.pos | join(","))"' \
  data/intermediate/core/core_entries_enriched.jsonl > words_metadata.tsv
```

### Count by Category
```bash
# Count words by concreteness
jq -r '.concreteness' data/intermediate/core/core_entries_enriched.jsonl \
  | sort | uniq -c | sort -rn

# Count words by frequency tier
jq -r '.frequency_tier' data/intermediate/core/core_entries_enriched.jsonl \
  | sort | uniq -c | sort -rn

# Count by POS
jq -r '.pos[]' data/intermediate/core/core_entries_enriched.jsonl \
  | sort | uniq -c | sort -rn
```

### Sample Random Words
```bash
# Get 100 random words from a category
./examples/filter_kids_vocabulary.sh
shuf -n 100 kids_vocabulary.txt > random_kids_words.txt
```

---

## Creating Your Own Filters

### Template Script
```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT="data/intermediate/core/core_entries_enriched.jsonl"
OUTPUT="my_wordlist.txt"

jq -r 'select(
    # Add your filters here
    (.pos | contains(["noun"])) and
    .concreteness == "concrete"
    # ... more conditions
) | .word' "$INPUT" | sort -u > "$OUTPUT"

echo "✓ Generated $OUTPUT ($(wc -l < "$OUTPUT") words)"
```

### Available Fields for Filtering

From `core_entries_enriched.jsonl`:
- `word` - The word itself
- `pos` - Part of speech tags (array): `["noun"]`, `["verb"]`, etc.
- `concreteness` - Concrete/abstract/mixed classification
- `frequency_tier` - top10, top100, top300, top500, top1k, top3k, top10k, top25k, top50k, rare
- `is_phrase` - Boolean: true for multi-word phrases
- `labels` - Object with subcategories:
  - `labels.register` - formal, informal, slang, vulgar, offensive, etc.
  - `labels.region` - en-GB, en-US, etc.
  - `labels.temporal` - archaic, obsolete, dated, etc.
  - `labels.domain` - medicine, law, computing, etc.
- `sources` - Array of source datasets: `["enable"]`, `["wikt"]`, etc.

### JQ Tips

**Check if field exists**:
```bash
select(has("concreteness"))
```

**Check array contains value**:
```bash
(.pos | contains(["noun"]))
```

**Check label present**:
```bash
((.labels.register // []) | contains(["vulgar"]))
```

**Combine conditions with OR**:
```bash
(.frequency_tier == "top1k" or .frequency_tier == "top10k")
```

**Negate condition**:
```bash
((.labels.register // []) | contains(["vulgar"]) | not)
```

**Regex matching**:
```bash
(.word | test("^[a-z]+$"))  # Only lowercase letters
(.word | test("ing$"))       # Ends with "ing"
```

---

## Troubleshooting

### "Input file not found"
**Problem**: Lexicon not built

**Solution**: Build first
```bash
make build-core  # or make build-plus
```

### "jq: command not found"
**Problem**: jq not installed

**Solution**: Install jq
```bash
# Ubuntu/Debian
sudo apt-get install jq

# macOS
brew install jq
```

### Empty output files
**Problem**: Filters too strict

**Solution**: Relax some criteria
```bash
# Check what's available
jq -r '.concreteness' data/intermediate/core/core_entries_enriched.jsonl | sort | uniq -c

# Adjust filters accordingly
```

### Scripts not executable
**Problem**: Missing execute permission

**Solution**: Make executable
```bash
chmod +x examples/*.sh
```

---

## See Also

- **[FILTERING.md](../docs/FILTERING.md)** - Comprehensive filtering documentation
- **[ANALYSIS_WORKFLOW.md](../docs/ANALYSIS_WORKFLOW.md)** - Analysis command guide
- **[GAME_WORDS.md](../docs/GAME_WORDS.md)** - Game word filtering
- **[SCHEMA.md](../docs/SCHEMA.md)** - Entry schema reference

---

## Contributing Examples

Have a useful filtering pattern? Contributions welcome!

1. Create a new `.sh` script in `examples/`
2. Follow the existing script structure
3. Include usage examples and clear comments
4. Update this README
5. Submit a pull request

---

**Questions?** Open an issue at https://github.com/macshonle/openword-lexicon/issues
