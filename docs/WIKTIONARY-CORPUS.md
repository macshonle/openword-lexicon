# English Wiktionary Corpus Analysis

This document captures key statistics and findings about the English Wiktionary dump.
It is a "living document" - regenerate by running `make corpus-stats`.

<!-- AUTO:last_updated -->
**Last updated:** 2025-12-04
<!-- /AUTO:last_updated -->
**Source dump:** `enwiktionary-latest-pages-articles.xml.bz2`

## Overview

<!-- AUTO:overview -->
| Metric | Value |
|--------|-------|
| Total pages scanned | 10,200,775 |
| English pages | 1,332,461 |
| Unique section headers | 142 |
| Unique template POS values | 88 |
<!-- /AUTO:overview -->

## Section Headers by Frequency

These are the raw `===Header===` values found in English sections, normalized to lowercase.

### Parts of Speech (POS-relevant)

<!-- AUTO:headers_pos -->
| Count | Header | Notes |
|------:|--------|-------|
| 799,128 | noun |  |
| 215,357 | verb |  |
| 181,831 | proper noun |  |
| 180,484 | adjective |  |
| 26,981 | adverb |  |
| 4,892 | phrase | Generic multi-word |
| 4,659 | interjection |  |
| 2,928 | prepositional phrase |  |
| 2,284 | prefix |  |
| 1,519 | proverb |  |
| 1,459 | suffix |  |
| 911 | pronoun |  |
| 860 | preposition |  |
| 851 | contraction |  |
| 477 | symbol |  |
| 452 | numeral |  |
| 370 | conjunction |  |
| 319 | determiner |  |
| 178 | letter |  |
| 103 | particle |  |
| 56 | punctuation mark |  |
| 53 | infix |  |
| 36 | interfix |  |
| 30 | participle |  |
| 27 | article |  |
| 14 | diacritical mark |  |
| 10 | idiom |  |
| 4 | circumfix |  |
| 4 | verb phrase |  |
| 3 | postposition |  |
| 3 | verb form | As section header (rare) |
| 1 | adverbial phrase | Only "on all fours" |
| 1 | affix |  |
<!-- /AUTO:headers_pos -->

### Non-POS Headers (Structural)

<!-- AUTO:headers_structural -->
| Count | Header |
|------:|--------|
| 490,542 | etymology (all) |
| 146,336 | pronunciation (all) |
| 242,637 | anagrams |
| 160,702 | translations |
| 96,143 | derived terms |
| 75,608 | alternative forms |
| 72,416 | references |
| 67,204 | related terms |
| 53,305 | see also |
| 53,218 | further reading |
| 49,687 | synonyms |
| 35,051 | statistics |
| 15,287 | usage notes |
| 9,609 | antonyms |
| 9,213 | coordinate terms |
| 5,189 | hypernyms |
| 4,927 | hyponyms |
| 3,879 | descendants |
| 2,014 | quotations |
| 539 | conjugation |
| 479 | meronyms |
| 338 | holonyms |
| 217 | collocations |
| 171 | notes |
| 79 | abbreviations |
| 70 | gallery |
| 49 | trivia |
| 45 | paronyms |
| 36 | external links |
| 12 | troponyms |
| 12 | citations |
| 7 | multiple parts of speech |
<!-- /AUTO:headers_structural -->

### Typos and Variants

These appear to be typos or non-standard headers in the corpus.
Page names use wiki link format for easy editing on Wiktionary.

<!-- AUTO:header_typos -->
| Count | Header | Likely Intended | Pages |
|------:|--------|-----------------|-------|
| 3 | pronounciation | pronunciation | [[fearology]], [[fearologist]], [[take a tinkle]] |
| 2 | pronuciation | pronunciation | [[rex]], [[Greatorex]] |
| 1 | alernative forms | alternative forms | [[Housty]] |
| 1 | alterative forms | alternative forms | [[ʔaq̓am]] |
| 1 | coordiante terms | coordinate terms | [[MFH]] |
| 1 | etymologyp | etymology | [[/p]] |
| 1 | eymology | etymology | [[blackula]] |
| 1 | hyopernyms | hypernyms | [[cronut]] |
| 1 | proerp noun | proper noun | [[Gros Ventre]] |
| 1 | pronuncation | pronunciation | [[Picardy]] |
| 1 | pronunciaation | pronunciation | [[qiran]] |
| 1 | relatd terms | related terms | [[broad brush]] |
| 1 | synoynms | synonyms | [[sponge down]] |
| 1 | tranlsations | translations | [[corroboree]] |
<!-- /AUTO:header_typos -->

## Template POS Values

These are POS values extracted from `{{head|en|...}}` templates.

<!-- AUTO:template_pos -->
| Count | Template POS | Notes |
|------:|--------------|-------|
| 318,619 | noun form | Plural/possessive forms |
| 156,245 | verb form | Conjugated forms |
| 36,137 | proper noun form |  |
| 5,291 | misspelling |  |
| 4,859 | phrase |  |
| 3,279 | noun | Lemma entries |
| 3,187 | superlative adjective |  |
| 2,917 | comparative adjective |  |
| 2,469 | adjective |  |
| 1,214 | proper noun |  |
| 875 | verb |  |
| 758 | verb forms | (plural variant) |
| 702 | proverb |  |
| 503 | adverb |  |
| 439 | prepositional phrase |  |
| 434 | numeral |  |
| 276 | interjection |  |
| 211 | prefix |  |
| 192 | symbol |  |
| 188 | contraction |  |
| 183 | pronoun |  |
| 137 | determiner |  |
| 126 | comparative adverb |  |
| 118 | letter |  |
| 111 | superlative adverb |  |
| 109 | suffix |  |
| 79 | preposition |  |
| 66 | conjunction |  |
| 64 | prefixes | (plural variant) |
| 63 | abbreviation |  |
| 60 | suffix form |  |
| 56 | punctuation mark |  |
| 52 | infix |  |
| 42 | proper nouns |  |
| 39 | suffixes |  |
| 37 | contractions |  |
| 34 | interfix |  |
| 31 | past participle |  |
| 22 | pronoun form |  |
| 21 | article |  |
| 18 | adj |  |
| 17 | particle |  |
| 15 | nouns |  |
| 14 | adjective form |  |
| 13 | symbols |  |
| 13 | idiom |  |
| 12 | noun forms |  |
| 10 | numeral form |  |
| 7 | adjectives |  |
| 7 | non-constituent |  |
| 6 | diacritical mark |  |
| 5 | articles |  |
| 5 | numerals |  |
| 5 | adverbs |  |
| 5 | adv |  |
| 5 | abbreviations |  |
| 4 | prepositions |  |
| 4 | pronouns |  |
| 4 | circumfix |  |
| 3 | particles |  |
| 3 | interjections |  |
| 3 | verbs |  |
| 3 | postposition |  |
| 3 | verb phrase form |  |
| 2 | numeral symbols |  |
| 2 | determiners |  |
| 2 | prop |  |
| 2 | int |  |
| 2 | phr |  |
| 2 | pn |  |
| 2 | n |  |
| 1 | letters |  |
| 1 | prefix form |  |
| 1 | conj |  |
| 1 | - |  |
| 1 | non-constituents |  |
| 1 | pronominal adverbs |  |
| 1 | suffix forms |  |
| 1 | prepositional phrases |  |
| 1 | alternative spelling |  |
| 1 | initialism |  |
| 1 | intj |  |
| 1 | noun-form |  |
| 1 | phrases |  |
| 1 | adverb form |  |
| 1 | plural noun |  |
| 1 | nf |  |
| 1 | combining form |  |
<!-- /AUTO:template_pos -->

## Categories

Note: Most categories are auto-generated by templates (like `{{en-noun}}`) at render time,
not stored in the raw dump. Only manually-added `[[Category:English X]]` tags appear here.

<!-- AUTO:categories -->
| Count | Category |
|------:|----------|
| 8 | eponyms |
| 2 | genericized trademarks |
| 1 | heteronyms |
| 1 | terms derived from Wade-Giles |
| 1 | second person pronouns |
| 1 | determiners |
| 1 | possessive determiners |
<!-- /AUTO:categories -->

## POS Analysis Details

### Pseudo-POS Only Entries

Entries with "pseudo-POS" headers (participle, contraction, letter) that have no real POS.
These indicate entries that may need additional analysis.

<!-- AUTO:pseudo_pos_analysis -->
Pages that have **only** pseudo-POS headers (no real POS like noun, verb, etc.):

| Pseudo-POS | Count | Sample Entries |
|------------|------:|----------------|
| contraction | 725 | he'd, I'd, we'd, she'd, you'd |
| letter | 92 | z, yi, è, æ, þ |
| participle | 28 | beflain, setten fire to, setten on fire, setten fire in, setten fire upon |
<!-- /AUTO:pseudo_pos_analysis -->

### Phrase Type Breakdown

Individual counts for phrase-type headers (kept separate for analysis):

<!-- AUTO:phrase_types -->
| Phrase Type | Count |
|-------------|------:|
| idiom | 10 |
| phrase | 4,892 |
| prepositional phrase | 2,928 |
| proverb | 1,519 |
<!-- /AUTO:phrase_types -->

### Aggregate POS Groupings

Shows what counts would look like if certain POS types were merged:

<!-- AUTO:aggregate_groups -->
Potential groupings for normalization:

| Grouping | Components | Total |
|----------|------------|------:|
| Affix | prefix, suffix, infix, interfix, circumfix, affix | 3,837 |
| Symbol | symbol, punctuation mark, diacritical mark | 547 |
| Determiner | determiner, article | 346 |
| Determiner/Numeral | determiner, article, numeral | 798 |
<!-- /AUTO:aggregate_groups -->

### Unknown POS Entries

Pages that have section headers but none match our known POS types:

<!-- AUTO:unknown_pos -->
Pages with section headers but no recognized POS: **34**

Sample entries: supposed to, sixty-eight, sixty-five, thirty-nine, forty-one, forty-three, forty-nine, fifty-one, fifty-two, fifty-three
<!-- /AUTO:unknown_pos -->

## Key Findings

### Dead Code: "adverbial phrase"

The POS type "adverbial phrase" appears exactly **once** in 1.33 million English pages:
- Page: **on all fours**
- Also found in Thesaurus namespace: **Thesaurus:God forbid**

References to `Category:English adverbial phrases` in the scanner code are dead code because:
1. The category doesn't exist on Wiktionary
2. Categories aren't stored in the dump (auto-generated by templates)

### Category Detection Limitation

The raw Wiktionary dump does not contain `[[Category:English X]]` tags for most entries.
Categories are dynamically generated by templates like `{{en-noun}}` at render time.
This means category-based POS detection in the scanners only works for the rare cases
where editors manually add category tags.

## Lua Module Analysis

Categories in Wiktionary are computed by Lua modules at render time. We've analyzed the
relevant modules to port category logic to our scanner.

### Key Modules (Lines of Code)

| Module | Lines | Purpose |
|--------|------:|---------|
| `Module:en-headword` | 1,648 | English-specific headword/inflection handling |
| `Module:headword` | 1,431 | Base category generation, all languages |
| `Module:languages` | 2,243 | Language data and metadata |
| `Module:labels/data` | 1,677 | Grammatical labels → category mappings |
| `Module:labels/data/lang/en` | 2,362 | English regional/dialect labels |
| `Module:labels` | 1,109 | Label processing |
| `Module:en-utilities` | 446 | English-specific utilities |
| **Total (key modules)** | ~10,900 | |

### How Categories Are Generated

From `Module:en-headword` (English-specific):
```lua
insert(data.categories, langname .. " " .. cat)           -- e.g., "English nouns"
insert(data.categories, langname .. " phrasal verbs")     -- detected from word patterns
insert(data.categories, langname .. ' phrasal verbs formed with "' .. adverb .. '"')
```

From `Module:headword` (all languages):
```lua
insert(data.categories, full_langname .. " " .. postype .. "s")     -- POS category
insert(data.categories, full_langname .. " multiword terms")        -- if has spaces
```

### Phrasal Verb Detection

Phrasal verbs are detected by checking if the headword matches the pattern:
`<single-word base verb> <phrasal adverbs and/or placeholders>`

**Phrasal adverbs** (44 total): aback, about, above, across, after, against, ahead, along, apart, around, as, aside, at, away, back, before, behind, below, between, beyond, by, down, for, forth, from, in, into, of, off, on, onto, out, over, past, round, through, to, together, towards, under, up, upon, with, without

**Placeholder words** (allowed but don't make a verb phrasal): it, one, oneself

**Note**: Words like `forward`, `low`, `adrift` are explicitly NOT in the list.

### Portability Assessment

| Aspect | Complexity | Portability |
|--------|------------|-------------|
| Basic POS categories | Low | ✅ **Ported** - string concatenation |
| Phrasal verb detection | Medium | ✅ **Ported** - see `tools/wiktionary_scanner_python/categories.py` |
| Multiword term detection | Low | ✅ **Ported** - check for spaces |
| Label → category mapping | Low | ✅ **Ported** - 30 labels with pos_categories |
| Adj/Adv comparability | Low | ✅ **Ported** - uncomparable/componly/suponly |
| Regional dialects | Low | ✅ **Ported** - 26 regional varieties |

**No major blockers**: No C library integration, no complex metatables, no MediaWiki-specific APIs.

## Adjective/Adverb Comparability

Analysis of `{{en-adj}}` and `{{en-adv}}` templates (200k page sample):

### Adjective Comparability

| Pattern | Count | Percentage | Category |
|---------|------:|-----------:|----------|
| Uncomparable (`-`) | 6,939 | 75.6% | `English uncomparable adjectives` |
| Comparable (suffix) | 1,247 | 13.6% | - |
| Comparable (more) | 73 | 0.8% | - |
| Comparative-only | 4 | <0.1% | `English comparative-only adjectives` |
| Superlative-only | 0 | 0% | `English superlative-only adjectives` |
| **Total templates** | 9,183 | 100% | |

### Adverb Comparability

| Pattern | Count | Percentage | Category |
|---------|------:|-----------:|----------|
| Uncomparable (`-`) | 1,449 | 86.0% | `English uncomparable adverbs` |
| Comparable (suffix) | 65 | 3.9% | - |
| Comparable (more) | 5 | 0.3% | - |
| Comparative-only | 1 | <0.1% | `English comparative-only adverbs` |
| Superlative-only | 0 | 0% | `English superlative-only adverbs` |
| **Total templates** | 1,685 | 100% | |

### Template Parameter Detection

From `Module:en-headword`, comparability is determined by:
- `-` as first param (alone) → uncomparable
- `componly=1` → comparative-only
- `suponly=1` → superlative-only

**Comparative-only examples** (rare):
- `faster-than-light` → `{{en-adj|componly=1}}`
- `larger-than-life` → `{{en-adj|componly=1}}`
- `FTL` → `{{en-adj|componly=1}}`

**Uncomparable examples** (common):
- `alphabetical` → `{{en-adj|-}}`
- `portmanteau` → `{{en-adj|-}}`
- `gratis` → `{{en-adj|-}}`

## Regional Dialect Categories

Analysis of regional labels in `{{lb|en|...}}` templates (200k page sample):

### Top Regional Labels

| Label | Count | Category |
|-------|------:|----------|
| US | 4,529 | American English |
| UK | 3,347 | British English |
| British | 1,484 | British English |
| Australia | 1,273 | Australian English |
| Scotland | 1,105 | Scottish English |
| Ireland | 815 | Irish English |
| Canada | 708 | Canadian English |
| Philippines | 464 | Philippine English |
| Northern England | 443 | Northern English |
| North America | 433 | North American English |
| New Zealand | 426 | New Zealand English |
| Irish | 415 | Irish English |
| South Africa | 337 | South African English |
| India | 315 | Indian English |
| Geordie | 199 | Geordie English |
| Singapore | 190 | Singapore English |

### Supported Regional Varieties (26 total)

**Major varieties**: US, UK, Australia, Canada, Ireland, Scotland, New Zealand, South Africa, India, Philippines, Singapore, Hong Kong, Malaysia, Jamaica, Nigeria, Pakistan, Caribbean

**Sub-regional varieties**: North America, Northern England, Southern US, Appalachia, New England, Geordie, Yorkshire, Cockney, RP

### Regional Label Aliases

Each regional label has aliases that map to the same category:
- `US` → `U.S.`, `USA`, `America`, `American`, `American English`
- `UK` → `United Kingdom`, `British`
- `Australia` → `Australian`, `AU`, `AuE`, `Aus`, `AusE`
- `Canada` → `Canadian`, `CA`, `CanE`

## Label Usage Statistics

Labels are grammatical annotations in `{{lb|en|...}}` templates. From a 200k page sample:

### Top Grammatical Labels (with category mappings)

| Label | Count | Category |
|-------|------:|----------|
| transitive | 17,759 | transitive verbs |
| intransitive | 8,697 | intransitive verbs |
| countable | 5,018 | countable nouns |
| uncountable | 4,685 | uncountable nouns |
| ambitransitive | 919 | transitive verbs, intransitive verbs |
| not comparable | 308 | (no category, display only) |
| reflexive | 250 | reflexive verbs |
| collective | 127 | collective nouns |
| ergative | 121 | ergative verbs |
| comparable | 104 | (no category, display only) |

### Register/Temporal Labels (display only, no categories)

| Label | Count |
|-------|------:|
| obsolete | 9,899 |
| slang | 8,811 |
| informal | 5,262 |
| archaic | 3,967 |
| historical | 3,445 |
| dated | 3,006 |
| rare | 2,976 |
| colloquial | 2,699 |

## Hyphenation Analysis

Hyphenation data in `{{hyphenation|en|...}}` templates (200k page sample):

### Coverage

| Metric | Value |
|--------|-------|
| Pages with hyphenation | 8,251 (8.4%) |
| Total templates | 8,501 |

### Syllable Count Distribution

| Syllables | Count | Percentage |
|----------:|------:|-----------:|
| 1 | 285 | 3.4% |
| 2 | 3,991 | 46.9% |
| 3 | 2,630 | 30.9% |
| 4 | 1,144 | 13.5% |
| 5 | 359 | 4.2% |
| 6+ | 91 | 1.1% |

### Data Quality Issues

**Incomplete entries** (260): Words with unseparated syllables:
- `about`, `year`, `cunt` - single syllable parts that should be broken up

**Potential typos to report to Wiktionary**:
| Word | Found | Expected |
|------|-------|----------|
| ablaut | `ab\|lowt` | `ab\|laut` |
| pamphlet | `panph\|let` | `pam\|phlet` |
| numeric | `mu\|mer\|ic` | `nu\|mer\|ic` |
| antediluvian | `an\|ti\|di\|luv\|i\|an` | `an\|te\|di\|luv\|i\|an` |
| temperate | `temp\|pe\|rate` | `tem\|per\|ate` |
| dishonest | `dis\|on\|est` | `dis\|hon\|est` |

**Multiword phrase handling**: Many multiword phrases have hyphenation spanning word boundaries,
which doesn't follow standard syllabification rules (e.g., `ice cream` → `ice cream` not `ice\|cream`).
This is intentional for pronunciation guidance but affects syllable counting.

---

*Regenerate this document: `make corpus-stats`*
