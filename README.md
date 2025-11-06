# Openword Lexicon

Permissively usable English lexicon for any application (games, NLP, education). Two distributions and a fast trie enable configurable, high‑quality word lists with rich labels and frequency tiers.

## Distributions
- **core** — ultra‑permissive sources only (data: CC0 or CC BY 4.0)
- **plus** — enhanced coverage/labels incl. CC‑BY‑SA inputs (data: CC BY‑SA 4.0)  
**Code:** Apache‑2.0

## Constraints
- Total downloads ≤ **100 GB**
- Peak RAM per step ≤ **2 GB**

## Quickstart (uv)
```bash
brew install uv                         # one time
make bootstrap                          # create venv + install deps
make fetch-core && make build-core      # PD/permissive build
make fetch-plus && make build-plus      # enhanced build (larger)
# Example (once CLI exists)
uv run owlex search --pattern '^..a..$' --len 5 --family-friendly --rank-max top10k
```

## High‑level pipeline
1. **Fetch** sources (core | plus) with checksums & provenance.
2. **Normalize** entries to JSONL (schema, NFKC, controlled labels).
3. **Enrich** with WordNet (concreteness/POS); **Tier** by frequency.
4. **Merge & deduplicate** per distribution.
5. **Policy filters** (e.g., family‑friendly) for curated views.
6. **Trie build** (compressed radix/DAWG) + sidecar metadata.
7. **CLI & releases** (artifacts + ATTRIBUTION + data LICENSE).

## Primary artifacts
- `core.trie` / `plus.trie` and `*.meta.db`
- `entries_merged.jsonl` (intermediate)
- `ATTRIBUTION.md`, `data/LICENSE`
- Release archives: `*-core-<ver>.tar.zst` / `*-plus-<ver>.tar.zst`

## Status
Phase 0 focuses on repository scaffolding, `uv` workflow, and guardrails. Subsequent phases add ingestion, enrichment, trie build, CLI, tests, CI, and packaging.
