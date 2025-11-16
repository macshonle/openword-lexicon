# Unified Build Design - WordNet + Wiktionary Integration

**Date:** 2025-11-16
**Status:** Proposed

---

## Executive Summary

This document proposes a redesign from dual (Core/Plus) distributions to a **single unified build** that integrates all sources (ENABLE, EOWL, Wiktionary, WordNet) with per-source licensing tracking. This enables better data complementarity while supporting key filtering use cases through runtime filters with safe defaults.

### Key Changes

1. **Single unified build** - No more Core/Plus separation
2. **Per-source licensing** - Track license requirements by data source used
3. **Better integration** - WordNet enriches ALL entries (including Wiktionary)
4. **Runtime filtering** - Move from build-time policy to flexible runtime filters
5. **Safe defaults** - Missing metadata implies conservative assumptions

---

## Current Architecture (Dual Distribution)

### Problems Identified

From `docs/REPORT_ANALYSIS.md`:

1. **Core has 0% label coverage** → Cannot filter profanity, regions, etc.
2. **Plus has 90% missing concreteness** → Cannot filter by abstract/concrete
3. **Core contains offensive words** → Family-friendly filter ineffective
4. **Data doesn't complement** → Lowest-common-denominator approach loses value
5. **Forced upfront licensing choice** → Users can't see what they need first

### Current Pipeline

```
ENABLE/EOWL → core_ingest → core_entries.jsonl
                                    ↓
                            wordnet_enrich (core only)
                                    ↓
                            frequency_tiers
                                    ↓
                            merge_dedupe → entries_merged.jsonl (core)
                                    ↓
                            policy (family-friendly)
                                    ↓
                            trie_build → core.trie

Wiktionary → wikt_ingest → wikt_entries.jsonl
                                    ↓
                            frequency_tiers
                                    ↓
                            merge_dedupe → entries_merged.jsonl (plus)
                                    ↓
                            policy (family-friendly)
                                    ↓
                            trie_build → plus.trie
```

**Issue**: WordNet enrichment only applied to core sources, not Wiktionary.

---

## New Architecture (Unified Build)

### Design Principles

1. **Always use all available data** - No artificial separation
2. **Complement, don't restrict** - Let sources enhance each other
3. **Track, don't decide** - Record licensing requirements, let user choose
4. **Support key use cases** - Children's games, region filtering, profanity blocking
5. **Safe by default** - Missing metadata = conservative assumption

### New Pipeline

```
ENABLE/EOWL → core_ingest → core_entries.jsonl ──┐
                                                   │
Wiktionary → wikt_ingest → wikt_entries.jsonl ────┤
                                                   │
                                                   ↓
                                            merge_all.py
                                    (merge ALL sources, track licenses)
                                                   ↓
                                         entries_unified.jsonl
                                                   ↓
                                        wordnet_enrich_all.py
                                    (enrich ALL entries, not just core)
                                                   ↓
                                        frequency_tiers.py
                                                   ↓
                                         entries_enriched.jsonl
                                                   ↓
                                            trie_build.py
                                    (single trie with license metadata)
                                                   ↓
                                            unified.trie
                                            unified.meta.db

Runtime filtering (not build-time):
  - Children-safe filter
  - Region-specific filter
  - Profanity blocklist
  - Sensitivity filter
```

---

## Schema Changes

### Add `license_sources` Field

Track which sources contribute which licenses:

```json
{
  "word": "castle",
  "pos": ["noun", "verb"],
  "labels": {
    "register": []
  },
  "sources": ["enable", "eowl", "wikt"],
  "license_sources": {
    "CC0": ["enable"],
    "UKACD": ["eowl"],
    "CC-BY-SA-4.0": ["wikt"]
  },
  "concreteness": "concrete",
  "frequency_tier": "top10k"
}
```

### License Mapping

```python
SOURCE_LICENSES = {
    'enable': 'CC0',           # Public Domain
    'eowl': 'UKACD',           # Permissive
    'wikt': 'CC-BY-SA-4.0',    # Share-alike
    'wordnet': 'WordNet',      # Permissive (enrichment only)
    'frequency': 'CC-BY-4.0'   # OpenSubtitles
}
```

**User benefit**: Developer can see "this word requires CC-BY-SA" and make informed choice.

---

## Key Use Cases & Safe Defaults

### 1. Children-Appropriate Words

**Use case**: Games like 20 Questions, Pictionary, Charades for kids.

**Filter logic**:
```python
def is_child_safe(entry):
    # SAFE DEFAULT: If no register labels, assume NOT safe
    # (opposite of current behavior which assumes safe)
    register = entry.get('labels', {}).get('register', [])

    # Explicit unsafe markers
    if any(label in register for label in ['vulgar', 'offensive', 'derogatory']):
        return False

    # If Wiktionary source AND no register labels, be cautious
    # (Wiktionary words without labels might be technical/obscure)
    if 'wikt' in entry['sources'] and not register:
        # Check if also in core sources (ENABLE/EOWL = curated for games)
        if not any(src in entry['sources'] for src in ['enable', 'eowl']):
            return False  # Wikt-only with no labels = risky

    # Exclude archaic/obsolete (kids won't know them)
    temporal = entry.get('labels', {}).get('temporal', [])
    if any(label in temporal for label in ['archaic', 'obsolete']):
        return False

    return True
```

**Key insight**: Core sources (ENABLE/EOWL) are pre-curated for word games, so their presence is a positive signal even without labels.

### 2. Region-Specific Filtering

**Use case**: US-only word list for American spelling.

**Filter logic**:
```python
def matches_region(entry, preferred_region='en-US'):
    region_labels = entry.get('labels', {}).get('region', [])

    # No region labels = universal/unknown
    if not region_labels:
        return True  # Include by default

    # Has region labels - check if matches
    return preferred_region in region_labels
```

**Safe default**: Missing region label = universal (include it).

### 3. Profanity Filtering

**Use case**: Block offensive words.

**Filter logic**:
```python
PROFANITY_REGISTERS = {'vulgar', 'offensive', 'derogatory'}

def is_profanity(entry):
    register = entry.get('labels', {}).get('register', [])
    return bool(set(register) & PROFANITY_REGISTERS)
```

**Safe default**: Missing register labels = cannot confirm safe → exclude from children's lists.

### 4. Concrete Nouns for Games

**Use case**: 20 Questions needs concrete, visualizable objects.

**Filter logic**:
```python
def is_concrete_noun(entry):
    # Must be a noun
    if 'noun' not in entry.get('pos', []):
        return False

    concreteness = entry.get('concreteness')

    # SAFE DEFAULT: Missing concreteness = assume abstract/technical
    if not concreteness:
        # Exception: If from ENABLE/EOWL (game-curated), might be concrete
        # but unknown. Be conservative.
        return False

    return concreteness == 'concrete'
```

**Safe default**: Missing concreteness = too complex/technical → exclude.

---

## Implementation Plan

### Phase 1: Schema & Infrastructure

**Files to modify**:
- `docs/SCHEMA.md` - Add `license_sources` field
- `docs/schema/entry.schema.json` - Update JSON schema

### Phase 2: Unified Merge

**New file**: `src/openword/merge_all.py`
- Merge ENABLE + EOWL + Wiktionary in one pass
- Track source licenses per entry
- Output: `data/intermediate/unified/entries_merged.jsonl`

**Changes to**: `src/openword/merge_dedupe.py`
- Rename or repurpose for unified approach

### Phase 3: WordNet Enrichment for All

**Changes to**: `src/openword/wordnet_enrich.py`
- Remove distribution-specific logic
- Enrich ALL entries (core + Wiktionary)
- Use lemmatization to match Wiktionary entries to WordNet

**Expected improvement**: Concreteness coverage from 9.9% → ~40% on Wiktionary entries.

### Phase 4: Runtime Filtering

**Changes to**: `src/openword/policy.py`
- Rename to `src/openword/filters.py`
- Implement filter functions (not policy applications)
- Add child-safe, region, profanity, concreteness filters
- Safe defaults in filter logic

**New file**: `docs/FILTERING_GUIDE.md`
- Document filter functions
- Explain safe defaults
- Provide usage examples

### Phase 5: Build Pipeline

**Changes to**: `Makefile`
- Remove `build-core` and `build-plus` targets
- Add `build-unified` target
- Update pipeline order

**Changes to**: `src/openword/trie_build.py`
- Build single unified trie
- Include license metadata in sidecar DB

**Changes to**: `src/openword/attribution.py`
- Generate unified attribution file
- Group by license type

### Phase 6: Documentation

**Files to update**:
- `README.md` - Remove Core/Plus, explain unified build
- `docs/DESIGN.md` - Update architecture
- `docs/FILTERING.md` - Add safe defaults explanation
- `docs/GAME_WORDS.md` - Update for new filtering

**New files**:
- `docs/LICENSE_TRACKING.md` - Explain per-source licensing
- `docs/SAFE_DEFAULTS.md` - Document conservative assumptions

---

## Migration Strategy

### For Users

**Before** (forced upfront choice):
```bash
# Must choose: permissive-only OR comprehensive-with-restrictions
make build-core   # 208K words, no labels, has profanity
make build-plus   # 1.3M words, labels, no concreteness
```

**After** (informed runtime choice):
```bash
# Get everything, filter what you need
make build-unified   # 1.3M words, best of both

# Filter at runtime based on license tolerance
python -m openword.owlex filter \
  --max-restrictive-license=CC-BY-4.0 \
  --output=permissive-only.txt

# Or filter by use case
python -m openword.owlex filter \
  --child-safe \
  --concrete-nouns-only \
  --output=kids-game-words.txt
```

### Backward Compatibility

- Keep `core.trie` and `plus.trie` as symlinks to `unified.trie` for transition period
- Add deprecation warnings in build scripts
- Document migration path in README

---

## Expected Outcomes

### Data Quality

| Metric | Current (Plus) | Unified Build | Improvement |
|--------|---------------|---------------|-------------|
| **Concreteness coverage** | 9.9% | ~40% | 4x better |
| **Label coverage** | 10.6% | 10.6% | Same |
| **POS coverage** | 98.6% | 98.6% | Same |
| **Total words** | 1.3M | 1.3M | Same |
| **Offensive words in "safe" list** | 0 (Plus) / ~50 (Core) | 0 (with child-safe filter) | Fixed |

### Developer Experience

1. **No upfront licensing decision** - See what you need, then decide
2. **Better filtering** - Child-safe actually works
3. **More flexible** - Region, profanity, concreteness all supported
4. **Transparent** - Know exactly which sources/licenses you're using

### Performance

- **Build time**: Slightly longer (single enrichment pass on all data)
- **Trie size**: ~3 MB (same as Plus)
- **Runtime**: Same (filtering happens at query time)

---

## Risks & Mitigations

### Risk: Larger download size

**Mitigation**: Single 3MB trie is still small. Can add `--minimal` flag to skip Wiktionary-only words if needed.

### Risk: Slower enrichment

**Mitigation**: WordNet enrichment already cached. May take 2-3x longer but still under 10 minutes.

### Risk: License confusion

**Mitigation**: Clear documentation. ATTRIBUTION.md shows exactly which sources contribute which licenses.

### Risk: Breaking changes

**Mitigation**: Keep Core/Plus symlinks for compatibility. Add migration guide.

---

## Next Steps

1. **Review this design** with stakeholders
2. **Implement Phase 1-2** (schema + unified merge)
3. **Test concreteness improvement** on Wiktionary subset
4. **Implement Phase 3-4** (enrichment + filtering)
5. **Update documentation** (Phase 5-6)
6. **Generate comparison report** (old vs new)
7. **Deprecate Core/Plus** with migration guide

---

## References

- `docs/REPORT_ANALYSIS.md` - Identified problems with current approach
- `docs/SCHEMA.md` - Current schema definition
- `src/openword/merge_dedupe.py` - Current merge logic
- `src/openword/wordnet_enrich.py` - Current enrichment logic
- `src/openword/policy.py` - Current filtering approach
