# Schema Roadmap

Future explorations and potential enhancements for the Configuration-Driven Architecture (CDA).

## Future Tag Sets to Explore

### Grammatical Features

**Purpose**: Test CDA flexibility by adding verb transitivity and noun countability labels.

**Potential codes**:

| Code | Name | Description |
|------|------|-------------|
| `VTRN` | Transitive | Verb takes a direct object |
| `VITR` | Intransitive | Verb does not take a direct object |
| `VAMB` | Ambitransitive | Verb can be either transitive or intransitive |
| `NCNT` | Countable | Noun can be pluralized (a cat, two cats) |
| `NUNC` | Uncountable | Mass noun (water, information) |
| `NBTH` | Both | Noun can be either depending on context |

**Use cases**:
- Grammar checking (flag incorrect object usage)
- Sentence generation (ensure proper argument structure)
- ESL/language learning tools
- NLP parsing improvements
- Determiner agreement (much vs many)

**Implementation notes**:
- These would form a new `grammatical` tag set in `schema/core/tag_sets.yaml`
- Wiktionary labels: `transitive`, `intransitive`, `ambitransitive`, `countable`, `uncountable`
- Labels appear in `{{lb|en|...}}` templates on definitions
- Would require bindings in `schema/bindings/en-wikt.tag_sets.yaml`

**Questions to answer**:
- How consistently are these labels applied in Wiktionary?
- Should they be flags (boolean) or tags (categorical)?
- Do they belong at sense level or entry level?

## Potential Schema Enhancements

### Senseid / Wikidata Integration

**Status**: Implemented in v2 scanner output (Dec 2024)

The `{{senseid|en|value}}` template provides stable identifiers for senses:
- **QIDs** (e.g., `Q617085`, `Q302`) link to Wikidata knowledge graph
- **Semantic labels** (e.g., `"grammar"`, `"music"`, `"transitive"`) disambiguate polysemous words

From full dump statistics:
- 14,235 unique senseid values
- 5,436 Wikidata QIDs detected

The `senseid` field is now included in entry output when present.

Potential uses:
- Wikidata enrichment (images, translations, related concepts)
- Sense disambiguation in NLP applications
- Cross-lingual linking
- Semantic clustering

### Etymology Source Tracking

**Status**: Collected in statistics, future YAML extension planned

Statistics show 1,282 unique etymology source languages. Top sources:
| Code | Language | Count |
|------|----------|-------|
| `enm` | Middle English | 20,121 |
| `la` | Latin | 18,637 |
| `ang` | Old English | 10,354 |
| `grc` | Ancient Greek | 9,446 |
| `fr` | French | 8,137 |

**Proposed YAML Extension**:

```yaml
# schema/core/etymology.yaml
etymology_sources:
  - code: enm
    name: Middle English
    iso639: enm

  - code: la
    name: Latin
    iso639: lat

  # etc.
```

This would allow:
- Etymology-based word groupings
- Language of origin filters
- Historical linguistics features
- Loan word analysis

### Output Mode Variants

**Status**: Planned

Fork the JSONL generation to support different output profiles:

| Mode | Description | Use Case |
|------|-------------|----------|
| `full` | All entries: phrases, proper nouns, all senseids and glosses | Complete lexicon, NLP training |
| `words` | Single words only: no phrases (wc>1), no proper nouns (NAM) | Word games, vocabulary apps |

The `words` mode filters before downstream processing, allowing game-specific
rules to be applied later without needing lexicon regeneration.

**Implementation**: Add `--mode full|words` flag to scanner.

## Statistics-Driven Priorities

Run `make build-wikt-json-v2` to generate `en-wikt-v2-stats.json` with:
- Unmapped label frequencies (candidates for new bindings)
- Domain tag coverage
- Senseid/QID prevalence
- Unknown header frequencies

Use these stats to prioritize which features would have the most impact.

### Recent Statistics Highlights (Dec 2024)

From full Wiktionary dump (1.84M entries):

**High-impact unmapped labels** (candidates for grammatical features):
| Label | Count |
|-------|-------|
| transitive | 33,842 |
| intransitive | 13,441 |
| countable | 8,731 |
| uncountable | 8,179 |
| ambitransitive | 1,853 |

**Coverage metrics**:
- Syllable coverage: 25.35% (649,722 entries)
- Lemma extraction: 663,710 entries
- Morphology extraction: 641,156 entries

## WordNet Semantic Categories

**Status**: Planned

### Motivation

WordNet (english-wordnet-2024) organizes its ~160k synsets into 45 **lexnames**
(semantic categories) by part-of-speech:

| POS | Count | Examples |
|-----|-------|----------|
| Noun | 26 | noun.animal, noun.body, noun.food, noun.artifact |
| Verb | 15 | verb.motion, verb.cognition, verb.creation |
| Adjective | 3 | adj.all, adj.pert, adj.ppl |
| Adverb | 1 | adv.all |

These categories answer a different question than Wiktionary domain labels:
- **Wiktionary domains (DXXXX)**: "What field uses this term?" (medicine, computing, law)
- **WordNet categories (CXXXX)**: "What kind of thing is this?" (animal, artifact, event)

### Proposed Implementation

**Core interface** (`schema/core/semantic_categories.yaml`):
```yaml
semantic_categories:
  - code: CANIM
    name: animal
    pos: NOU
    description: Nouns denoting animals

  - code: CBODY
    name: body
    pos: NOU
    description: Nouns denoting body parts

  - code: CMOTN
    name: motion
    pos: VRB
    description: Verbs of walking, flying, swimming
```

**WordNet bindings** (`schema/bindings/wordnet.semantic_categories.yaml`):
```yaml
semantic_category_bindings:
  - code: CANIM
    from_lexnames:
      - noun.animal
    from_synset_patterns:
      - "*.n.01"  # First noun sense often canonical

  - code: CBODY
    from_lexnames:
      - noun.body
```

### 5-Letter Code Convention

Semantic category codes use 5 letters starting with `C`:

| Code | WordNet Lexname | Description |
|------|-----------------|-------------|
| CANIM | noun.animal | Animals |
| CBODY | noun.body | Body parts |
| CFOOD | noun.food | Foods and drinks |
| CARTF | noun.artifact | Man-made objects |
| CEVNT | noun.event | Events and happenings |
| CMOTN | verb.motion | Motion verbs |
| CCOGN | verb.cognition | Mental verbs |
| CCOMM | verb.communication | Communication verbs |

This keeps them distinct from domain codes (DXXXX) while maintaining the 5-letter
length for consistency.

### Use Cases

- **Semantic filtering**: Find all animal-related words vs all zoology terminology
- **Ontological enrichment**: Add "what kind of thing" to lexicon entries
- **Cross-source alignment**: Map Wiktionary entries to WordNet semantic space
- **Downstream disambiguation**: Use both domain AND category for precise filtering

### Sense Alignment Strategy

A key goal is aligning Wiktionary senses with WordNet synsets to enable cross-resource
enrichment. Potential alignment signals:

**Primary filters:**
- **POS match**: WordNet lexnames are POS-specific (noun.animal only matches NOU entries)
- **Headword overlap**: Same spelling in both resources narrows candidates
- **Word count**: Single words (wc=1) align better than phrases

**Secondary signals:**
- **Gloss similarity**: Compare Wiktionary definitions with WordNet glosses
- **Senseid/QID**: When present, Wikidata QIDs may link directly to WordNet synsets
- **Domain overlap**: Wiktionary DXXXX codes may correlate with WordNet lexnames
  (e.g., DZOOL ↔ noun.animal, DMEDI ↔ noun.body)
- **Hypernym chains**: WordNet's IS-A hierarchy could validate category assignments

**Analysis tasks:**
1. Generate word overlap statistics (headwords in both Wiktionary and WordNet)
2. Build POS-filtered candidate sets for alignment
3. Explore gloss embedding similarity (e.g., using sentence transformers)
4. Map domain codes to lexnames empirically (which DXXXX codes co-occur with which lexnames?)
5. Evaluate alignment confidence by sense count (monosemous words are easier)

**Output:**
- `wikt_sense_id` → `wordnet_synset_id` mapping table
- Confidence scores per alignment
- Unmatched senses flagged for manual review

### Questions to Answer

- Should categories be exclusive (one per sense) or non-exclusive (like domains)?
- How to handle WordNet's catch-all categories (adj.all, adv.all)?
- Should we expose the full 45-category system or collapse similar ones?
- What similarity threshold yields acceptable alignment precision/recall?
- How to handle Wiktionary senses with no WordNet equivalent (neologisms, slang)?
