# Scanner Parser Refactoring & Enhancement Plan

## Executive Summary

We've achieved near-fixed-point (4 remaining edge cases) with the scanner parser. Time to consolidate, remove obsolete code, and enhance filtering capabilities for specialized word lists.

## Current State Analysis

### Parsers
1. **wiktionary_scanner_parser.py** ✅ KEEP
   - String scanning (no XML parsing overhead)
   - 10-100x faster than wiktextract
   - Comprehensive POS and label extraction
   - Near-fixed-point: 4/10,200,775 pages fail (0.00004% failure rate)
   - Outputs: 1,326,838 entries

2. **wiktionary_simple_parser.py** ❌ OBSOLETE
   - Uses ET.iterparse() (slower XML parsing)
   - Same output format as scanner
   - Superseded by scanner parser

### Makefile Targets
1. **fetch-post-process-plus** ❌ REMOVE
   - Uses wiktextract (wiktwords command)
   - External dependency we're eliminating
   - Slower and less comprehensive

2. **fetch-simple** ❌ REMOVE
   - Uses simple parser
   - Superseded by fetch-scanner

3. **fetch-scanner** ✅ RENAME → **build-wiktionary-json**
   - Uses scanner parser
   - Should be primary method
   - Name should reflect it builds WIKTIONARY_JSON target

## Recommended Changes

### 1. Remove Obsolete Code

#### pyproject.toml
```toml
# REMOVE these dependencies:
# wiktextract @ git+...
# wikitextprocessor @ git+...
```

#### Makefile
```makefile
# REMOVE these targets:
.PHONY: fetch-post-process-plus fetch-simple

# RENAME:
fetch-scanner → build-wiktionary-json

# UPDATE build-plus dependency:
build-plus: fetch-plus build-wiktionary-json
```

#### Remove files:
- tools/prototypes/wiktionary_simple_parser.py

### 2. Current JSONL Schema

```json
{
    "word": "example",
    "pos": ["noun", "verb"],
    "labels": {
        "register": ["informal"],
        "temporal": ["archaic"],
        "domain": ["computing"],
        "region": ["en-US"],
        "categories": ["English nouns", "English verbs"]
    },
    "is_phrase": false,
    "sources": ["wikt"]
}
```

**Available for filtering:**
- ✅ POS types: noun, verb, adjective, adverb, pronoun, etc.
- ✅ Phrases: is_phrase boolean
- ✅ Affixes: prefix, suffix, infix, circumfix, interfix
- ✅ Vulgar/offensive: labels.register includes 'vulgar', 'offensive', 'derogatory'
- ✅ Temporal: archaic, obsolete, dated
- ✅ Regional variants: en-US, en-GB, etc.
- ✅ Domains: computing, mathematics, medicine, etc.
- ✅ Categories: Full category names from Wiktionary

### 3. Gap Analysis for Advanced Filtering

#### ✅ Already Supported

**Vulgar word blocklist:**
```bash
# Filter entries with vulgar register
jq -c 'select(.labels.register | contains(["vulgar", "offensive", "derogatory"]))' wikt.jsonl
```

**Phrase categorization:**
```bash
# Get idioms
jq -c 'select(.pos | contains(["phrase"]) and (.labels.categories | any(contains("idiom"))))' wikt.jsonl

# Get prepositional phrases
jq -c 'select(.labels.categories | any(contains("prepositional phrases")))' wikt.jsonl
```

**Game words (basic):**
```bash
# Single words, common POS, no special characters
jq -c 'select(
    .is_phrase == false and
    (.pos | contains(["noun", "verb", "adjective", "adverb"])) and
    (.word | test("^[a-z]+$"))
)' wikt.jsonl
```

#### ❌ Not Yet Supported (Requires Enhancement)

**Simple concrete nouns for kids:**
- **Missing**: Concrete vs. abstract distinction
- **Missing**: Frequency/commonality data
- **Missing**: Age-appropriateness indicators
- **Workaround**: Use category hints like "English animal nouns", "English food nouns"

**Word frequency/commonality:**
- **Missing**: No frequency data from Wiktionary
- **Solution**: Could integrate external frequency lists (Google n-grams, SUBTLEXus, etc.)

**Complexity metrics:**
- **Missing**: Syllable count, letter count
- **Solution**: Add to output or compute during filtering

### 4. Proposed Makefile Structure

```makefile
# =============================
# Wiktionary Data Pipeline
# =============================

# Step 1: Fetch raw Wiktionary dump
fetch-plus:
	# Downloads enwiktionary-latest-pages-articles.xml.bz2

# Step 2: Parse into JSONL (primary target)
build-wiktionary-json: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@echo "→ Parsing Wiktionary with scanner parser..."
	@mkdir -p "$(dir $(WIKTIONARY_JSON))"
	$(UV) run python tools/prototypes/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		"$(WIKTIONARY_JSON)"

# Step 3: Build specialized word lists
build-wordlists: build-wiktionary-json
	@$(MAKE) export-wordlist-game
	@$(MAKE) export-wordlist-vulgar-blocklist
	@$(MAKE) export-wordlist-kids-nouns
	@$(MAKE) export-wordlist-phrases

# =============================
# Specialized Word Lists
# =============================

export-wordlist-game: build-wiktionary-json
	@echo "→ Building game word list..."
	@mkdir -p data/wordlists
	jq -r 'select(
		.is_phrase == false and
		(.pos | contains(["noun", "verb", "adjective", "adverb"])) and
		(.word | test("^[a-z]+$$")) and
		(.word | length >= 3) and
		(.labels.temporal | length == 0)
	) | .word' "$(WIKTIONARY_JSON)" | sort -u > data/wordlists/game-words.txt
	@echo "✓ Game words: $$(wc -l < data/wordlists/game-words.txt) entries"

export-wordlist-vulgar-blocklist: build-wiktionary-json
	@echo "→ Building vulgar/offensive blocklist..."
	@mkdir -p data/wordlists
	jq -r 'select(
		.labels.register |
		contains(["vulgar"]) or contains(["offensive"]) or contains(["derogatory"])
	) | .word' "$(WIKTIONARY_JSON)" | sort -u > data/wordlists/vulgar-blocklist.txt
	@echo "✓ Blocklist: $$(wc -l < data/wordlists/vulgar-blocklist.txt) entries"

export-wordlist-kids-nouns: build-wiktionary-json
	@echo "→ Building kids' noun list (simple concrete nouns)..."
	@mkdir -p data/wordlists
	jq -r 'select(
		(.pos | contains(["noun"])) and
		.is_phrase == false and
		(.word | test("^[a-z]+$$")) and
		(.word | length >= 3 and length <= 10) and
		(.labels.categories | any(
			test("animal|food|plant|toy|color|body|furniture|tool|vehicle|clothing")
		))
	) | .word' "$(WIKTIONARY_JSON)" | sort -u > data/wordlists/kids-nouns.txt
	@echo "✓ Kids nouns: $$(wc -l < data/wordlists/kids-nouns.txt) entries"

export-wordlist-phrases: build-wiktionary-json
	@echo "→ Extracting phrase types..."
	@mkdir -p data/wordlists
	jq -r 'select(.pos | contains(["phrase"])) | .word' "$(WIKTIONARY_JSON)" \
		| sort -u > data/wordlists/all-phrases.txt
	jq -r 'select(.labels.categories | any(contains("idiom"))) | .word' "$(WIKTIONARY_JSON)" \
		| sort -u > data/wordlists/idioms.txt
	jq -r 'select(.labels.categories | any(contains("prepositional phrases"))) | .word' "$(WIKTIONARY_JSON)" \
		| sort -u > data/wordlists/prepositional-phrases.txt
	@echo "✓ All phrases: $$(wc -l < data/wordlists/all-phrases.txt) entries"
	@echo "✓ Idioms: $$(wc -l < data/wordlists/idioms.txt) entries"
	@echo "✓ Prep phrases: $$(wc -l < data/wordlists/prepositional-phrases.txt) entries"

# =============================
# Diagnostic Tools
# =============================

diagnose-scanner: deps
	@if [ ! -f "$(WIKTIONARY_DUMP)" ]; then \
		echo "✗ Missing $(WIKTIONARY_DUMP). Run 'make fetch-plus' first."; \
		exit 1; \
	fi
	@mkdir -p reports
	@echo "→ Running diagnostic scan..."
	$(UV) run python tools/prototypes/wiktionary_scanner_parser.py \
		"$(WIKTIONARY_DUMP)" \
		/tmp/scanner_diagnostic.jsonl \
		--diagnostic reports/scanner_diagnostic.txt
	@echo ""
	@echo "✓ Report saved to: reports/scanner_diagnostic.txt"
```

### 5. Enhanced Filtering Infrastructure

#### Option A: Add metadata to scanner parser output

**Add to JSONL schema:**
```python
{
    "word": "example",
    "pos": ["noun"],
    "labels": {...},
    "is_phrase": false,
    "sources": ["wikt"],
    # NEW FIELDS:
    "complexity": {
        "length": 7,
        "syllables": 3,  # Estimate
        "has_special_chars": false
    },
    "categories_matched": [
        "animal",  # Simplified category tags
        "concrete"
    ]
}
```

**Implementation:**
```python
def estimate_syllables(word: str) -> int:
    """Rough syllable count based on vowel groups."""
    vowels = 'aeiouy'
    word = word.lower()
    count = 0
    prev_was_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    return max(1, count)

def categorize_noun_type(categories: List[str]) -> List[str]:
    """Extract semantic category tags from Wiktionary categories."""
    tags = []
    category_patterns = {
        'animal': r'animals?|mammals?|birds?|fish|insects?',
        'food': r'foods?|fruits?|vegetables?|meat',
        'plant': r'plants?|flowers?|trees?',
        'concrete': r'physical objects|tangible',
        'abstract': r'abstract|concepts?',
    }
    for tag, pattern in category_patterns.items():
        if any(re.search(pattern, cat, re.I) for cat in categories):
            tags.append(tag)
    return tags
```

#### Option B: Post-processing script

Create `tools/enrich_wiktionary_json.py`:
```python
#!/usr/bin/env python3
"""
Enrich Wiktionary JSONL with additional metadata for filtering.
"""
# Read wikt.jsonl
# Add complexity metrics
# Add simplified category tags
# Optionally merge frequency data from external source
# Write enriched JSONL
```

### 6. Integration with Existing Tooling

**Update build-core to use scanner:**
```makefile
build-core: deps fetch-core build-wiktionary-json
	# ... rest of build-core
```

**Update references:**
- Any scripts or docs mentioning `fetch-post-process-plus` → `build-wiktionary-json`
- Any scripts using simple parser → scanner parser

## Implementation Priority

### Phase 1: Cleanup (Immediate)
1. ✅ Remove wiktextract dependencies from pyproject.toml
2. ✅ Remove fetch-post-process-plus target
3. ✅ Remove fetch-simple target
4. ✅ Rename fetch-scanner → build-wiktionary-json
5. ✅ Delete wiktionary_simple_parser.py
6. ✅ Update build-plus dependencies

### Phase 2: Basic Filtering (Short-term)
1. ✅ Add export-wordlist-vulgar-blocklist target
2. ✅ Add export-wordlist-phrases target
3. ✅ Add export-wordlist-game target
4. ✅ Test filtering with existing schema

### Phase 3: Enhanced Metadata (Medium-term)
1. ⏳ Add complexity metrics to scanner parser
2. ⏳ Add simplified category tagging
3. ⏳ Add export-wordlist-kids-nouns target
4. ⏳ Test semantic category filtering

### Phase 4: External Data Integration (Long-term)
1. ⏳ Research frequency data sources
2. ⏳ Create frequency data pipeline
3. ⏳ Merge frequency with Wiktionary data
4. ⏳ Add frequency-based filtering

## Success Metrics

- ✅ Scanner parser at fixed point (0 diagnostic samples)
- ✅ wiktextract completely removed
- ✅ Build time < 15 minutes for full Wiktionary
- ✅ Can generate vulgar blocklist
- ✅ Can generate kids' noun list
- ✅ Can generate phrase lists by type
- ✅ Can generate game word lists with various constraints

## Questions for Decision

1. **Enrichment approach**: Option A (add to scanner) or Option B (post-process)?
   - Recommendation: Option A for basic metrics (length, syllables)
   - Option B for external data (frequency)

2. **Frequency data source**: Which dataset?
   - Google n-grams (large, comprehensive)
   - SUBTLEXus (based on subtitles, more conversational)
   - COCA (Corpus of Contemporary American English)

3. **Kids' word criteria**: How to define "kid-appropriate"?
   - Category-based (animals, toys, colors) ✅ Feasible now
   - Frequency-based (top 5000 most common) ⏳ Needs frequency data
   - Complexity-based (short, simple syllables) ✅ Can add now
