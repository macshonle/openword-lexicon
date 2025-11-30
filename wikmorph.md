# wiktmorph (working title)

Wiktionary-derived morphology for Python, intended as a richer alternative and companion to traditional stemmer and lemmatizer libraries.

Instead of mapping a token to a single “stem” or “lemma” string, `wiktmorph` exposes a small morphological lexicon built from Wiktionary:

- inflectional relations (tense, number, person, degree, etc.)
- derivational relations (prefixes, suffixes, compounding)
- optional root/family groupings

This lets you choose, per task, whether to:

- normalize across **inflection** only (like a lemmatizer)
- normalize across **derivation** (root/family level)
- keep **full morphosyntactic feature bundles** for later use

---

## Why Wiktionary morphology instead of only stems/lemmas?

Traditional tools:

- **Stemmers** (Porter, Snowball, etc.)  
  - Fast, heuristic, language-specific rules.  
  - No part-of-speech awareness, no tense/number/person, no derivation vs inflection distinction.

- **Lemmatizers** (WordNet, spaCy, Stanza, etc.)  
  - Map inflected forms to lemmas, often POS-aware.  
  - Usually stop at: `form → lemma` (+ sometimes coarse features).

`wiktmorph` starts from a different representation:

- Each surface form is linked to one or more **analyses**:
  - `lemma`: canonical form
  - `pos`: part of speech (noun, verb, adjective, …)
  - `features`: morphosyntactic bundle (tense, number, person, degree, etc.)
  - `derivational`: information about the morphological family (root, affixes, components)

From this, stems and lemmas become **projections** of a richer structure rather than the only outputs.

---

## Status

This repository is currently a design and prototype reference:

- The API is stable enough to experiment with.
- The underlying Wiktionary extraction is a work-in-progress.
- Expect incomplete coverage and rough edges.

---

## Installation

```bash
pip install wiktmorph   # placeholder; not published yet