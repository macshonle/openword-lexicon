# Openword Lexicon: Label Taxonomy

This document defines the **controlled vocabulary** for lexical entry labels. All entries follow Unicode **NFKC normalization** for consistent representation.

---

## Label Categories

### 1. Part of Speech (`pos`)

Standard parts of speech. May be empty if unknown; enrichment passes backfill where possible.

| Value | Description | Example |
|-------|-------------|---------|
| `noun` | Noun | *castle*, *freedom* |
| `verb` | Verb | *run*, *think* |
| `adjective` | Adjective | *red*, *happy* |
| `adverb` | Adverb | *quickly*, *very* |
| `pronoun` | Pronoun | *she*, *they* |
| `preposition` | Preposition | *in*, *under* |
| `conjunction` | Conjunction | *and*, *but* |
| `interjection` | Interjection | *wow*, *ouch* |
| `determiner` | Determiner | *the*, *a* |
| `particle` | Particle | *up* (in *give up*) |
| `auxiliary` | Auxiliary verb | *is*, *have* |

---

### 2. Register Labels (`labels.register`)

Sociolinguistic register and stylistic markers.

| Value | Description | Example |
|-------|-------------|---------|
| `formal` | Formal/elevated register | *consequently*, *endeavor* |
| `informal` | Casual/conversational | *gonna*, *wanna* |
| `colloquial` | Everyday spoken usage | *cop* (police officer) |
| `slang` | Non-standard, ephemeral | *rad*, *sick* (cool) |
| `vulgar` | Coarse or crude | *asshole*, *damn* |
| `offensive` | Potentially insulting/hurtful | *bitch*, *retard* |
| `derogatory` | Belittling or demeaning | *hick*, *loser* |
| `euphemistic` | Indirect or softened | *pass away*, *restroom* |
| `humorous` | Playful/jocular intent | *thingy*, *thingamajig* |
| `literary` | Poetic or archaic literary | *forsooth*, *whence* |

---

### 3. Regional Labels (`labels.region`)

Dialect or regional variant markers. Uses BCP 47 language subtags (`en-XX`).

| Value | Description | Example |
|-------|-------------|---------|
| `en-GB` | British English | *colour*, *lorry* |
| `en-US` | American English | *color*, *truck* |
| `en-CA` | Canadian English | *toque* |
| `en-AU` | Australian English | *arvo*, *ute* |
| `en-NZ` | New Zealand English | *bach* |
| `en-IE` | Irish English | *craic* |
| `en-ZA` | South African English | *braai* |
| `en-IN` | Indian English | *prepone* |

---

### 4. Temporal Labels (`labels.temporal`)

Historical usage status.

| Value | Description | Example |
|-------|-------------|---------|
| `archaic` | No longer in active use; understood historically | *thou*, *thee* |
| `obsolete` | Completely out of use; may be incomprehensible | *forsooth* |
| `dated` | Old-fashioned but still understood | *icebox*, *gramophone* |
| `historical` | Refers to historical concepts/objects | *moat*, *castle* (in medieval context) |
| `modern` | Recent coinage or contemporary | *selfie*, *emoji* |

---

### 5. Domain Labels (`labels.domain`)

Specialized subject fields or technical areas.

| Value | Description | Example |
|-------|-------------|---------|
| `medical` | Medicine/healthcare | *cardiomyopathy* |
| `legal` | Law and jurisprudence | *subpoena*, *tort* |
| `technical` | Engineering/technology | *torque*, *actuator* |
| `scientific` | General science | *hypothesis*, *osmosis* |
| `military` | Armed forces | *infantry*, *battalion* |
| `nautical` | Maritime/naval | *starboard*, *bilge* |
| `botanical` | Plant sciences | *pistil*, *stamen* |
| `zoological` | Animal sciences | *carapace*, *thorax* |
| `computing` | Computer science/IT | *algorithm*, *bytecode* |
| `mathematics` | Math terminology | *hypotenuse*, *coefficient* |
| `music` | Musical terminology | *staccato*, *allegro* |
| `art` | Visual/performing arts | *chiaroscuro*, *sfumato* |
| `religion` | Religious terminology | *liturgy*, *ecclesiastical* |
| `culinary` | Cooking/cuisine | *julienne*, *sauté* |
| `sports` | Sports terminology | *offside*, *dribble* |
| `business` | Business/commerce | *amortization*, *stakeholder* |
| `finance` | Financial terminology | *equity*, *liquidity* |

---

## Concreteness (`concreteness`)

Applied to nouns via WordNet enrichment (Phase 7).

| Value | Description | Example |
|-------|-------------|---------|
| `concrete` | Physical, tangible objects | *castle*, *apple* |
| `abstract` | Ideas, qualities, concepts | *freedom*, *justice* |
| `mixed` | Both concrete and abstract senses | *paper* (material vs. document) |

---

## Frequency Tiers (`frequency_tier`)

Coarse ranking buckets based on corpus frequency (Phase 8).

| Value | Description | Rank Range | Example |
|-------|-------------|------------|---------|
| `top10` | Ultra-frequent | 1–10 | *the*, *and* |
| `top100` | Very frequent | 11–100 | *would*, *there* |
| `top1k` | Frequent | 101–1,000 | *important*, *someone* |
| `top10k` | Common | 1,001–10,000 | *castle*, *umbrella* |
| `top100k` | Known | 10,001–100,000 | *protozoa*, *osmosis* |
| `rare` | Rare/specialized | >100,000 | *zugzwang*, *quixotic* |

---

## Multi-word Phrases (`is_phrase`)

Boolean flag indicating whether the entry spans multiple tokens.

- **`true`**: *give up*, *in front of*, *break the ice*
- **`false`**: single-token words (default)

---

## Lemmatization (`lemma`)

If the entry is an inflected form, this field points to the base form.

- `lemma: "run"` for *running*, *ran*, *runs*
- `lemma: "good"` for *better*, *best*
- `null` if the entry itself is the lemma

---

## Sources (`sources`)

Provenance array. Each entry must list at least one source identifier.

| Source ID | Description | Distribution |
|-----------|-------------|--------------|
| `enable` | ENABLE word list (PD) | core |
| `eowl` | English Open Word List | core |
| `wikt` | Wiktionary (via Wiktextract) | plus |
| `wordnet` | Princeton WordNet | plus |
| `frequency` | Frequency corpus | plus |

**Example:**
```json
{
  "word": "colour",
  "sources": ["eowl", "wikt"]
}
```

---

## Validation

Entries are validated against `docs/schema/entry.schema.json` (JSON Schema Draft 7). Use `jq` or a JSON Schema validator:

```bash
# Validate a single entry
echo '{"word":"test","sources":["enable"]}' | jq -s '.[0]' > /tmp/entry.json
# (Full validation requires a JSON Schema validator like ajv-cli)
```

---

## Unicode Normalization

All `word` fields MUST be in **Unicode NFKC** (Normalization Form KC) to ensure consistent representation:

- Decomposes and recomposes characters
- Applies compatibility equivalences
- Example: `é` (U+00E9) → `é` (U+0065 U+0301 → U+00E9)

Python normalization:
```python
import unicodedata
normalized = unicodedata.normalize('NFKC', word)
```

---

## Policy Notes

1. **Empty POS arrays**: Acceptable for core sources without linguistic markup. Enrichment passes backfill where confident.
2. **Label unions**: When merging entries from multiple sources, union all labels (no duplicates).
3. **Family-friendly filtering**: Policy filters can exclude entries with `vulgar`, `offensive`, or `derogatory` labels.
4. **Ambiguity**: When in doubt, prefer not labeling over incorrect labeling. Conservative annotation is preferred.

---

## Changelog

- **2025-11-07**: Initial taxonomy for Phases 4–9 (normalization, ingest, enrichment, merging).
