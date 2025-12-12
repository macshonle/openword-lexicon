# Project Structure Reorganization Proposal

## Current Structure Analysis

```
openword-lexicon/
├── src/openword/              # Main Python package (pip-installable)
│   ├── owlex.py               # CLI entry point
│   ├── filters.py             # Filtering library
│   ├── *_enrich.py            # Enrichment modules
│   ├── v2_enrich.py           # Unified enrichment pipeline
│   └── ...
│
├── scripts/fetch/             # Isolated fetching tools
│   ├── fetch_sources.py       # Data source fetcher
│   └── sources.yaml           # Source definitions
│
├── tools/                     # Mixed purposes
│   ├── wiktionary_scanner_python/   # v1 scanner (importable package)
│   ├── wiktionary_scanner_v2/       # v2 scanner (importable package)
│   ├── wiktionary-scanner-rust/     # Rust scanner
│   ├── validate_*.py                # Validation scripts
│   ├── analyze_*.py                 # Analysis scripts
│   └── ...
│
├── schema/                    # Schema definitions
│   ├── core/                  # Core schemas (POS, flags, etc.)
│   ├── bindings/              # Language-specific bindings
│   └── enrichment/            # Enrichment field definitions (NEW)
│
└── tests/                     # Test suite
```

## Issues Identified

### 1. Inconsistent Module Location
- `wiktionary_scanner_v2` is in `tools/` but IS an importable package
- Tests import from `tools.wiktionary_scanner_v2`
- `scripts/fetch/` is isolated from the main package

### 2. Schema/Config Fragmentation
- Source definitions in `scripts/fetch/sources.yaml`
- Enrichment schemas in `schema/enrichment/`
- Both define source attribution for the same data sources
- POS schema in both `schema/pos.yaml` AND `schema/core/pos.yaml`

### 3. CLI Entry Points
- Only `owlex` is defined as an entry point in pyproject.toml
- Other tools run via `uv run python tools/...` or `python -m ...`

### 4. Rust Code Location
- `tools/wiktionary-scanner-rust/` is conventional but could be `crates/`

---

## Proposed Structure

### Option A: Full Consolidation Under `src/`

```
openword-lexicon/
├── src/openword/
│   ├── __init__.py
│   ├── cli/                      # CLI entry points
│   │   ├── __init__.py
│   │   ├── owlex.py              # Main lexicon CLI
│   │   └── fetch.py              # Data fetching CLI (moved from scripts/)
│   │
│   ├── scanner/                  # Scanner implementations
│   │   ├── __init__.py
│   │   ├── v1/                   # Moved from tools/wiktionary_scanner_python
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py
│   │   │   └── wikitext_parser.py
│   │   └── v2/                   # Moved from tools/wiktionary_scanner_v2
│   │       ├── __init__.py
│   │       ├── scanner.py
│   │       ├── rules.py
│   │       └── ...
│   │
│   ├── enrich/                   # Enrichment pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py           # Was v2_enrich.py
│   │   ├── frequency.py          # Was frequency_tiers.py
│   │   ├── concreteness.py       # Was brysbaert_enrich.py
│   │   └── aoa.py                # Was aoa_enrich.py
│   │
│   ├── filters.py
│   ├── trie.py                   # Was trie_build.py
│   └── ...
│
├── crates/                       # Rust implementations
│   └── wiktionary-scanner/       # Moved from tools/wiktionary-scanner-rust
│
├── tools/                        # Standalone dev/analysis scripts
│   ├── analyze_*.py              # Analysis tools
│   ├── validate_*.py             # Validation tools
│   ├── compare_*.py              # Comparison tools
│   └── ...
│
├── schema/
│   ├── core/                     # Core taxonomy schemas
│   ├── bindings/                 # Language-specific bindings
│   ├── enrichment/               # Enrichment field definitions
│   └── sources/                  # Data source definitions (moved from scripts/fetch/)
│       └── sources.yaml
│
└── tests/
```

### Option B: Minimal Migration (Less Disruption)

Keep most things in place but:
1. Move `scripts/fetch/sources.yaml` → `schema/sources/sources.yaml`
2. Move scanner packages under `src/openword/scanner/`
3. Keep analysis scripts in `tools/`

---

## Schema Consolidation

### Current Overlap

**`scripts/fetch/sources.yaml`** defines:
```yaml
kuperman_aoa:
  name: Kuperman Age of Acquisition
  license: CC BY 4.0
  url: https://osf.io/download/vb9je/
  ...
```

**`schema/enrichment/aoa.yaml`** defines:
```yaml
source:
  id: kuperman_aoa
  name: Kuperman Age of Acquisition
  license: CC-BY-4.0
  url: https://osf.io/download/vb9je/
  ...
```

### Proposed: Single Source of Truth

Move all source definitions to `schema/sources/`:

```yaml
# schema/sources/kuperman_aoa.yaml
id: kuperman_aoa
name: Kuperman Age of Acquisition
title: Age-of-acquisition ratings for 30,000 English words

# Fetching configuration
fetch:
  method: http
  url: https://osf.io/download/vb9je/
  output: kuperman_aoa.xlsx
  post_process:
    type: xlsx_to_tsv
    columns: [Word, Rating.Mean, Rating.SD, Dunno, PoS]
    output: kuperman_aoa.txt

# Attribution for output
attribution:
  license: CC-BY-4.0
  license_url: https://creativecommons.org/licenses/by/4.0/
  citation: |
    Kuperman, V., Stadthagen-Gonzalez, H., & Brysbaert, M. (2012).
    Age-of-acquisition ratings for 30,000 English words.
    Behavior Research Methods, 44, 978-990.

metadata:
  authors: Victor Kuperman, Hans Stadthagen-Gonzalez, Marc Brysbaert
  year: 2012
  journal: Behavior Research Methods
  doi: "10.3758/s13428-012-0210-4"
```

Then `schema/enrichment/aoa.yaml` references it:
```yaml
source: kuperman_aoa  # Reference to schema/sources/kuperman_aoa.yaml
```

---

## pyproject.toml Entry Points

```toml
[project.scripts]
owlex = "openword.cli.owlex:main"
owfetch = "openword.cli.fetch:main"
owscan = "openword.scanner.v2:main"

[tool.setuptools.packages.find]
where = ["src"]
```

---

## Migration Path

### Phase 1: Schema Consolidation (Low Risk)
1. Create `schema/sources/` directory
2. Migrate source definitions from `scripts/fetch/sources.yaml`
3. Update `fetch_sources.py` to read from new location
4. Update enrichment schemas to reference sources by ID

### Phase 2: Scanner Migration (Medium Risk)
1. Move `tools/wiktionary_scanner_v2/` → `src/openword/scanner/v2/`
2. Update all imports
3. Update Makefile commands
4. Add entry point for scanner CLI

### Phase 3: Fetch Script Migration (Low Risk)
1. Move `scripts/fetch/fetch_sources.py` → `src/openword/cli/fetch.py`
2. Add `owfetch` entry point
3. Remove empty `scripts/` directory

### Phase 4: Enrichment Module Reorganization (Optional)
1. Create `src/openword/enrich/` subdirectory
2. Move enrichment modules there
3. Rename for clarity (brysbaert_enrich.py → concreteness.py)

---

## Benefits

1. **Importability**: All scanner code is part of the installed package
2. **Single Source of Truth**: Source definitions in one place
3. **CLI Discoverability**: Named entry points (`owlex`, `owfetch`, `owscan`)
4. **Cleaner tools/**: Only contains analysis/debug scripts, not production code
5. **Standard Layout**: Follows Python packaging best practices

## Questions for Decision

1. Should we do full consolidation (Option A) or minimal (Option B)?
2. Should Rust code move to `crates/` or stay in `tools/`?
3. Should we add more CLI entry points beyond `owlex`?
4. How much backward compatibility do we need for existing Makefile targets?
