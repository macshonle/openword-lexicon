# Game Word Filtering Guide

Tools for generating word lists suitable for games like 20 Questions.

## Goal

Generate lists of concrete, common, age-appropriate nouns for use in word games:
- ✅ Concrete nouns (chair, dog, car)
- ✅ Common/familiar words
- ✅ Family-friendly (no adult content)
- ❌ Abstract concepts (love, freedom, democracy)
- ❌ Adult content (sexual, drugs, violence)
- ❌ Jargon (technical/specialized terms)

## Tools

### 1. Metadata Analysis (`tools/analyze_game_metadata.py`)

Analyzes what metadata we have for filtering:

```bash
# Analyze both distributions
make analyze-game-metadata

# Or individually
uv run python tools/analyze_game_metadata.py core
uv run python tools/analyze_game_metadata.py plus
```

**Output:** `reports/game_metadata_analysis_{core,plus}.md`

**Shows:**
- Field coverage (POS, concreteness, frequency, labels)
- Noun analysis (total, concrete, abstract, mixed)
- Frequency distribution
- Label type usage
- Recommendations for improvement

### 2. Word Filter (`tools/filter_game_words.py`)

Filters and scores words based on multiple criteria:

```bash
# Generate game word lists
make game-words

# Or with custom parameters
uv run python tools/filter_game_words.py \
  --distribution core \
  --min-score 70 \
  --max-words 1000 \
  --output-dir data/game_words
```

**Output:**
- `data/game_words/review_{dist}.md` - Manual review report
- `data/game_words/words_{dist}.txt` - Plain word list
- `data/game_words/words_scored_{dist}.txt` - Words with scores

## Current Metadata Coverage (Core)

From analysis report:

| Field | Coverage |
|-------|----------|
| POS tags | 52.5% |
| Concreteness | 34.5% |
| Frequency | 100% |
| Labels | 0% |

**Nouns:**
- Total: 71,862
- Concrete: 20,670 (28.8%)
- Abstract: 25,782 (35.9%)
- Mixed: 25,408 (35.4%)

**Frequency (nouns only):**
- top10k: 5,474
- top100k: 15,053
- rare: 50,680

## Scoring Algorithm

Words are scored on multiple dimensions (0-100+):

### Frequency Score (0-100)
- top10: 100
- top100: 90
- top1k: 80
- top10k: 70
- top100k: 50
- rare: 10

### Bonuses
- Concrete noun: +20
- Medium length (5-12 chars): +0
- Common word (top10k): inherent in frequency score

### Penalties
- Jargon domain: -30
- Archaic/obsolete: -20
- Too long (>12 chars): -10 to -20
- Multi-word phrase: excluded

### Hard Filters (excluded entirely)
- Not a noun
- Not age-appropriate
- Adult content domains
- Offensive/vulgar labels
- Multi-word phrases

## Known Issues & Improvements Needed

### 1. POS Tag Ambiguity

**Problem:** Many words have multiple POS tags including noun:
- "have" → ['noun', 'verb']
- "me" → ['noun'] (wrong!)
- "see" → ['verb', 'noun']

**Solution:** Filter words that are *primarily* nouns:
- Exclude common pronouns (I, me, you, we, they, etc.)
- Exclude common verbs that happen to have noun senses
- Require noun to be first/primary POS tag

### 2. Concreteness False Positives

**Problem:** Abstract words marked as concrete:
- "have" marked as concrete
- Verbs/pronouns shouldn't have concreteness

**Solution:**
- Only apply concreteness to actual nouns
- Add manual blocklist for known bad words
- Improve WordNet parsing to get primary sense

### 3. Missing Label Data

**Problem:** Core distribution has 0% label coverage (no register/domain/temporal labels)

**Why:** ENABLE/EOWL don't include this metadata

**Solution:**
- Use Plus distribution (has Wiktionary labels)
- Add manual categorization for common words
- Import domain data from external sources

### 4. Age-Appropriate Filtering

**Current:** Basic keyword blocking

**Needed:**
- Comprehensive adult content list
- Weapons/violence detection
- Alcohol/drugs detection
- Manual review and whitelist/blacklist

## Recommended Workflow

### Phase 1: Automated Filtering (done)
```bash
# Generate initial candidates
make game-words

# Review coverage
make analyze-game-metadata
```

### Phase 2: Improve Filters
1. Add exclusion list for pronouns/verbs
2. Fix concreteness false positives
3. Add manual adult content blocklist
4. Test on sample words

### Phase 3: Manual Review
1. Review top 500-1000 candidates
2. Create verified whitelist
3. Create blocklist of inappropriate words
4. Document edge cases

### Phase 4: Production List
1. Combine automated filter + manual review
2. Export final word list
3. Add metadata (difficulty level, categories)
4. Version and publish

## Manual Review Helper (TODO)

Need tool for efficient manual review:

```bash
# Interactive review
python tools/review_game_words.py \
  data/game_words/words_core.txt \
  --output data/game_words/reviewed_core.json

# Shows each word with:
# - Word
# - Score
# - Metadata (POS, frequency, concreteness)
# - Accept/Reject/Skip
# - Add notes/categories
```

## Example Improvements

### Add Common Exclusions

```python
# tools/filter_game_words.py

EXCLUDE_WORDS = {
    # Pronouns
    'i', 'me', 'you', 'he', 'she', 'it', 'we', 'they',
    'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'myself', 'yourself', 'himself', 'herself', 'itself',

    # Common verbs misclassified as nouns
    'have', 'has', 'had', 'do', 'does', 'did',
    'see', 'saw', 'seen', 'go', 'went', 'gone',
    'tell', 'told', 'say', 'said',

    # Abstract concepts
    'oh', 'ah', 'yes', 'no', 'maybe',
}
```

### Require Primary Noun

```python
def is_primarily_noun(entry: Dict) -> bool:
    """Check if word is primarily a noun."""
    pos_tags = entry.get('pos', [])

    # Must have noun tag
    if 'noun' not in pos_tags:
        return False

    # Noun should be first or only tag
    if pos_tags[0] != 'noun' and len(pos_tags) > 1:
        # Word has other POS as primary
        return False

    return True
```

## References

- Metadata schema: `docs/SCHEMA.md`
- Word filtering: `tools/filter_game_words.py`
- Metadata analysis: `tools/analyze_game_metadata.py`
- Current results: `data/game_words/`, `reports/game_metadata_analysis_*.md`

## Next Steps

1. Fix POS filtering (exclude misclassified words)
2. Add comprehensive exclusion lists
3. Build manual review tool
4. Generate validated word lists
5. Test with actual games
6. Iterate based on feedback
