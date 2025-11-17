# Word, Phrase, Idiom, and Proverb Separation

## Overview

This document explains how the Wiktionary scanner distinguishes between different types of lexical entries, from simple words to complex multi-word expressions.

## Classification Hierarchy

### 1. **Words** (Single-word entries)

**Criterion**: `word_count == 1`

**Characteristics**:
- No spaces in the entry
- Examples: `cat`, `dictionary`, `run`, `beautiful`
- May have hyphens (`self-aware`) or apostrophes (`don't`) but count as one word

**Detection**:
```python
word_count = len(word.split())  # Split on spaces
if word_count == 1:
    # This is a word, not a phrase
```

---

### 2. **Phrases** (Generic multi-word entries)

**Criterion**: `word_count > 1` AND `phrase_type == None`

**Characteristics**:
- Multiple words separated by spaces
- No specific classification as idiom/proverb/etc.
- Examples: `Pope Julius`, `red car`, `go to`
- Default category for multi-word entries

**Detection**:
- Has spaces: `word_count > 1`
- No specific phrase type detected
- Falls back to generic `phrase` POS

---

### 3. **Idioms** (Non-literal expressions)

**Criterion**: `phrase_type == 'idiom'`

**Characteristics**:
- Non-literal, figurative meaning
- Meaning not derivable from individual words
- Cultural/linguistic expressions
- Examples: `kick the bucket`, `let the cat out of the bag`, `break the ice`

**Detection methods**:
1. Section header: `===Idiom===`
2. Template: `{{head|en|idiom}}`
3. Category: `[[Category:English idioms]]`

**Wiktionary markup example**:
```wikitext
===Idiom===
{{head|en|idiom}}

# {{lb|en|idiomatic}} To reveal a secret.

[[Category:English idioms]]
```

---

### 4. **Proverbs** (Wisdom/advice sayings)

**Criterion**: `phrase_type == 'proverb'`

**Characteristics**:
- Complete sentence expressing wisdom or advice
- Often metaphorical
- Traditional sayings passed down through culture
- Examples: `a stitch in time saves nine`, `don't count your chickens before they hatch`

**Detection methods**:
1. Section header: `===Proverb===`, `===Saying===`, `===Adage===`
2. Template: `{{head|en|proverb}}`
3. Category: `[[Category:English proverbs]]` or `[[Category:English sayings]]`

**Wiktionary markup example**:
```wikitext
===Proverb===
{{head|en|proverb}}

# A person who hesitates will lose opportunities.

[[Category:English proverbs]]
```

---

### 5. **Prepositional Phrases**

**Criterion**: `phrase_type == 'prepositional phrase'`

**Characteristics**:
- Starts with a preposition
- Functions as a modifier
- Examples: `at least`, `on hold`, `in spite of`, `by right`

**Detection methods**:
1. Section header: `===Prepositional phrase===`
2. Template: `{{en-prepphr}}`
3. Category: `[[Category:English prepositional phrases]]`

---

### 6. **Adverbial Phrases**

**Criterion**: `phrase_type == 'adverbial phrase'`

**Characteristics**:
- Functions as an adverb
- Modifies verbs, adjectives, or other adverbs
- Examples: `all of a sudden`, `step by step`, `little by little`

**Detection methods**:
1. Section header: `===Adverbial phrase===`
2. Template: `{{head|en|adverbial phrase}}`
3. Category: `[[Category:English adverbial phrases]]`

---

### 7. **Verb Phrases**

**Criterion**: `phrase_type == 'verb phrase'`

**Characteristics**:
- Multi-word verb expressions
- Often phrasal verbs with particles
- Examples: `give up`, `take over`, `put up with`, `look forward to`

**Detection methods**:
1. Section header: `===Verb phrase===`
2. Template: `{{head|en|verb phrase}}`
3. Category: `[[Category:English verb phrases]]`

---

### 8. **Noun Phrases**

**Criterion**: `phrase_type == 'noun phrase'`

**Characteristics**:
- Multi-word expressions functioning as nouns
- Named entities, compound nouns
- Examples: `red herring`, `sitting duck`, `white elephant`

**Detection methods**:
1. Section header: `===Noun phrase===`
2. Template: `{{head|en|noun phrase}}`
3. Category: `[[Category:English noun phrases]]`

---

## Implementation

### Data Structure

Each entry has:
```json
{
  "word": "kick the bucket",
  "pos": ["phrase"],        // Normalized POS from POS_MAP
  "word_count": 3,          // Always present
  "phrase_type": "idiom",   // Present for typed multi-word entries
  "sources": ["wikt"]
}
```

### Detection Priority

The `extract_phrase_type()` function checks in this order:

1. **Section headers** (===Idiom===, ===Proverb===, etc.)
   - Most reliable signal
   - Explicitly defined by Wiktionary editors

2. **Templates** ({{head|en|idiom}}, {{en-prepphr}})
   - Structured metadata
   - Often present even without section headers

3. **Categories** ([[Category:English idioms]])
   - Fallback signal
   - Applied automatically by templates

### Edge Cases

**Multi-word proper nouns**:
- `Pope Julius` - Has `===Noun===` header, word_count=2, phrase_type=None
- Classified as generic phrase, not idiom/proverb

**Compound words with spaces**:
- `attorney general` - May be treated as phrase despite functioning as single unit
- Depends on Wiktionary's classification

**Phrasal verbs**:
- `look up` (search) - verb phrase
- `look up` (glance upward) - literal, may be separate entry

## Filtering Implications

Applications can filter by:

**Single words only**:
```python
word_count == 1
```

**Exclude long proverbs**:
```python
phrase_type != 'proverb' or word_count <= 5
```

**Only idioms**:
```python
phrase_type == 'idiom'
```

**Phrases but not proverbs**:
```python
word_count > 1 and phrase_type != 'proverb'
```

---

## Examples from Wiktionary

### Idiom
```wikitext
==English==
===Idiom===
{{head|en|idiom}}

# {{lb|en|idiomatic}} To die.

[[Category:English idioms]]
```

### Proverb
```wikitext
==English==
===Proverb===
{{head|en|proverb}}

# {{lb|en}} Excessive enthusiasm can be counterproductive.

[[Category:English proverbs]]
```

### Prepositional Phrase
```wikitext
==English==
===Prepositional phrase===
{{en-prepphr}}

# Fairly; justifiably.

[[Category:English prepositional phrases]]
```

### Generic Phrase (Proper Noun)
```wikitext
==English==
===Noun===
{{en-noun|-}}

# A sixteenth-century gambling card game.
```
(No phrase_type - classified as generic multi-word phrase)

---

## Summary Table

| Type | word_count | phrase_type | Example |
|------|-----------|-------------|---------|
| Word | 1 | - | `cat` |
| Generic Phrase | >1 | None | `Pope Julius` |
| Idiom | >1 | `idiom` | `kick the bucket` |
| Proverb | >1 | `proverb` | `zeal without knowledge is a runaway horse` |
| Prep. Phrase | >1 | `prepositional phrase` | `by right` |
| Adv. Phrase | >1 | `adverbial phrase` | `all of a sudden` |
| Verb Phrase | >1 | `verb phrase` | `give up` |
| Noun Phrase | >1 | `noun phrase` | `red herring` |

---

## References

- Wiktionary POS categories: https://en.wiktionary.org/wiki/Category:English_parts_of_speech
- Phrase types: https://en.wiktionary.org/wiki/Category:English_phrases
- Idioms: https://en.wiktionary.org/wiki/Category:English_idioms
- Proverbs: https://en.wiktionary.org/wiki/Category:English_proverbs
