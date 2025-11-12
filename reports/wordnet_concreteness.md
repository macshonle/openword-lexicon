# WordNet Concreteness Analysis

## Overview

- **Total synsets**: 0
- **Total categories**: 0
- **Concrete categories**: 0
- **Kids-suitable categories**: 0
- **Abstract categories**: 0

## Concrete Noun Categories

These categories contain physical, tangible nouns suitable for kids' games:

| Category | Description | Synsets | Unique Words |
|----------|-------------|---------|--------------|

## Kids-Appropriate Categories

Recommended categories for children's vocabulary:

## Abstract Categories (Exclude from Kids' Lists)

These categories contain abstract concepts less suitable for kids:

| Category | Description | Synsets | Unique Words |
|----------|-------------|---------|--------------|

## All Categories

Complete list of all noun categories in WordNet:


## Integration Strategy

### For Kids' Concrete Nouns List

1. **Extract words from kids-appropriate categories**
   - noun.animal (animals)
   - noun.artifact (toys, objects)
   - noun.body (body parts)
   - noun.food (food and drink)
   - noun.plant (plants, flowers)

2. **Combine with Wiktionary categories**
   - Use both WordNet lexicographer files AND Wiktionary categories
   - WordNet provides semantic grouping
   - Wiktionary provides additional coverage

3. **Apply additional filters**
   - Word length: 3-10 characters
   - Frequency: Top 10,000 most common
   - Exclude vulgar/offensive
   - Exclude archaic/obsolete

### Implementation

**Option A: Pre-process WordNet into category lists**
```bash
# Extract concrete nouns from WordNet
make extract-wordnet-categories
# Output: data/wordlists/wordnet-concrete-nouns.txt
```

**Option B: Enrich Wiktionary JSONL with WordNet categories**
```python
# Add WordNet lexfile to Wiktionary entries
{
  "word": "cat",
  "pos": ["noun"],
  "wordnet_categories": ["noun.animal"],  // NEW
  "labels": {...}
}
```

**Recommended: Option A** (simpler, faster filtering)

### Enhanced Kids' Nouns Filter

```bash
# Combine Wiktionary + WordNet + Frequency
jq -r 'select(
  (.pos | contains(["noun"])) and
  .is_phrase == false and
  (.word | test("^[a-z]+$")) and
  (.word | length >= 3 and length <= 10)
) | .word' wikt.jsonl \
  | grep -Fx -f data/wordlists/wordnet-concrete-nouns.txt \
  | grep -Fx -f data/wordlists/frequency-top-10k.txt \
  | grep -vFx -f data/wordlists/vulgar-blocklist.txt \
  > data/wordlists/kids-concrete-nouns-enhanced.txt
```
