# Local Analysis Workflow

This document describes how to run comprehensive analysis tools locally (where you have full network access and the complete Wiktionary dump), then commit the generated reports to version control for review.

## Overview

The build environment may have network restrictions that prevent downloading the 2-3 GB Wiktionary dump. You can run analysis locally, generate reports, and commit them for validation.

## Workflow

### 1. Download Wiktionary Dump Locally

```bash
# Download the latest English Wiktionary dump (~2-3 GB)
bash scripts/fetch/fetch_wiktionary.sh

# This downloads to: data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
```

**Time:** ~5-10 minutes depending on connection

### 2. Audit Wiktionary Extraction Approach

Before running the full extraction, validate the approach on a sample:

```bash
# Audit 10,000 sample pages from the dump
chmod +x tools/audit_wiktionary_extraction.py
uv run python tools/audit_wiktionary_extraction.py \
  data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
  --sample-size 10000
```

**Time:** ~2-5 minutes

**Generates:**
- `reports/wiktionary_audit.md` - Comprehensive audit report
- `reports/wiktionary_samples.json` - Sample entries for review

**What it validates:**
- ✓ Are we correctly identifying English words?
- ✓ What percentage of pages have English sections?
- ✓ What label coverage can we expect?
- ✓ Is the simple parser approach valid?

**Key questions answered:**
- Does "English Wiktionary" contain mostly English words or non-English words with English glosses?
- Can we extract regional labels (British, US, etc.)?
- Can we extract register labels (vulgar, informal, etc.)?
- Is Lua evaluation really necessary?

### 3. Run Simple Parser on Full Dump

Extract all English entries with labels:

```bash
# Run streaming parser (10-30 minutes for full dump)
uv run python tools/wiktionary_scanner_parser.py \
  data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
  data/intermediate/plus/wikt.jsonl
```

**Time:** ~10-30 minutes (streaming with real-time progress)

**What you'll see:**
```
Parsing: data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
Output: data/intermediate/plus/wikt.jsonl

  Processed: 5,000 | Written: 3,245 | Skipped: 1,755
  Processed: 10,000 | Written: 6,832 | Skipped: 3,168
  Processed: 15,000 | Written: 10,421 | Skipped: 4,579
  ...
```

**Output:**
- `data/intermediate/plus/wikt.jsonl` - Extracted entries with labels

**Note:** The parser:
- Streams from compressed archive (no temporary extraction)
- Uses fixed memory buffer (handles arbitrary file sizes)
- Writes entries immediately (visible progress)
- Includes contractions (don't, won't, can't)

### 4. Generate Label Statistics Report

Analyze what labels were actually extracted:

```bash
# Generate comprehensive statistics
chmod +x tools/report_label_statistics.py
uv run python tools/report_label_statistics.py \
  data/intermediate/plus/wikt.jsonl
```

**Time:** ~1-2 minutes

**Generates:**
- `reports/label_statistics.md` - Label coverage analysis
- `reports/label_examples.json` - Example words for each label

**Shows:**
- Regional label coverage (en-GB: 5,234 words, en-US: 3,123 words, ...)
- Register label coverage (vulgar: 1,234 words, informal: 5,678 words, ...)
- Temporal label coverage (archaic: 2,345 words, obsolete: 1,234 words, ...)
- Domain label coverage (medical: 3,456 words, legal: 1,234 words, ...)
- Filtering feasibility for each game type

### 5. Commit Reports to Version Control

```bash
# Add generated reports
git add reports/wiktionary_audit.md
git add reports/wiktionary_samples.json
git add reports/label_statistics.md
git add reports/label_examples.json

# Commit with descriptive message
git commit -m "Add Wiktionary extraction analysis reports

Audit reports validate simple parser approach and show label coverage:
- 10,000 sample pages analyzed
- X% have English sections
- Y% have regional labels (en-GB, en-US, etc.)
- Z% have register labels (vulgar, informal, etc.)

Results show simple parser is viable alternative to wiktextract,
with 10-100x performance improvement and no Lua dependencies.
"

# Push to branch
git push
```

**Why commit reports:**
- ✓ Validates extraction approach without needing full data in CI
- ✓ Provides audit trail for filtering decisions
- ✓ Allows review of label coverage before building distributions
- ✓ Documents what's actually in the Wiktionary dump

### 6. Build Plus Distribution with Labels

```bash
# Run full build pipeline
make build-plus
```

**What it does:**
1. Ingests wikt.jsonl (already extracted)
2. Enriches with WordNet data
3. Adds frequency tiers
4. Merges with core distribution
5. Applies policy filters
6. Builds trie and metadata

**Output:**
- `data/build/plus/plus.trie` - MARISA trie for fast lookups
- `data/build/plus/plus.meta.json` - Metadata with labels

### 7. Test Game-Specific Filters

```bash
# Test Wordle filter (5 letters, exclude British English)
uv run python tools/filter_words.py \
  --use-case wordle \
  --distribution plus \
  --max-words 500

# Output: data/filtered_words/wordle_plus.txt

# Test 20 Questions filter (concrete nouns, age-appropriate)
uv run python tools/filter_words.py \
  --use-case 20q \
  --distribution plus \
  --max-words 500

# Test custom filter
uv run python tools/filter_words.py \
  --distribution plus \
  --exact-length 5 \
  --exclude-regional \
  --exclude-offensive \
  --min-frequency top10k \
  --max-words 1000
```

## Comparison with wiktextract

If you want to compare the scanner parser with wiktextract:

```bash
# Run wiktextract (slow, several hours)
make fetch-post-process-plus

# Then manually compare the outputs from:
# - data/intermediate/plus/wikt.jsonl (scanner parser)
# - data/intermediate/plus/wikt_entries.jsonl (wiktextract)
```

## File Structure

```
data/raw/plus/
  enwiktionary-latest-pages-articles.xml.bz2  # Downloaded dump (2-3 GB)
  wiktionary.SOURCE.json                       # Metadata

data/intermediate/plus/
  wikt.jsonl                                   # Simple parser output
  wikt_entries.jsonl                           # wiktextract output (if run)

reports/
  wiktionary_audit.md                          # Audit report (commit this)
  wiktionary_samples.json                      # Sample entries (commit this)
  label_statistics.md                          # Label stats (commit this)
  label_examples.json                          # Examples (commit this)

data/build/plus/
  plus.trie                                    # Built trie (.gitignored)
  plus.meta.json                               # Metadata with labels (.gitignored)

data/filtered_words/
  wordle_plus.txt                              # Filtered word lists (.gitignored)
  20q_plus.txt
  ...
```

## What Gets Committed vs Ignored

### Commit to Git:
- ✓ `reports/wiktionary_audit.md` - Audit findings
- ✓ `reports/wiktionary_samples.json` - Sample entries
- ✓ `reports/label_statistics.md` - Label coverage
- ✓ `reports/label_examples.json` - Example words
- ✓ Analysis tools (`tools/audit_*.py`, `tools/report_*.py`)

### Ignored (.gitignore):
- ✗ `data/raw/` - Source dumps (too large, downloadable)
- ✗ `data/intermediate/` - Extracted data (reproducible)
- ✗ `data/build/` - Built artifacts (reproducible)
- ✗ `data/filtered_words/` - Generated word lists (reproducible)
- ✗ `data/wordlists/` - Specialized word lists (reproducible via make build-wordlists)
- ✗ `data/game_words/` - Game-filtered word lists (reproducible via make game-words)

## CI/CD Integration

In the CI environment (with network restrictions):

1. Reports are already committed, so validation is visible
2. Test data (31 entries) is used for pipeline testing
3. Full extraction runs locally, reports show it's valid
4. CI tests the build process, not the extraction

## Timeline

Total time for full local analysis: **~15-45 minutes**

| Task | Time | Network |
|------|------|---------|
| Download dump | 5-10 min | Required |
| Audit sample | 2-5 min | No |
| Run simple parser | 10-30 min | No |
| Generate statistics | 1-2 min | No |
| Build distribution | 2-5 min | No |
| Test filters | <1 min | No |

## Troubleshooting

### Download fails with 403 Forbidden

The CI environment has network restrictions. Run locally or:
```bash
# Download manually from:
# https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2

# Place in:
# data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2
```

### Parser runs out of memory

The streaming parser should use constant memory (~100-500 MB). If you see issues:
- Check `elem.clear()` is being called
- Reduce progress reporting interval
- Use `--limit` to process fewer entries

### No labels extracted

Check the audit report:
- Are pages actually English? (Look at language distribution)
- Do pages have `{{lb|en|...}}` templates? (Check samples)
- Are we parsing the right XML structure?

## Example Session

```bash
# Full local analysis workflow
cd /path/to/openword-lexicon

# 1. Download
bash scripts/fetch/fetch_wiktionary.sh

# 2. Audit
uv run python tools/audit_wiktionary_extraction.py \
  data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
  --sample-size 10000

# 3. Review audit
less reports/wiktionary_audit.md

# 4. Extract (if audit looks good)
uv run python tools/wiktionary_scanner_parser.py \
  data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
  data/intermediate/plus/wikt.jsonl

# 5. Statistics
uv run python tools/report_label_statistics.py \
  data/intermediate/plus/wikt.jsonl

# 6. Review statistics
less reports/label_statistics.md

# 7. Commit reports
git add reports/*.md reports/*.json
git commit -m "Add Wiktionary analysis reports"
git push

# 8. Build and test
make build-plus
uv run python tools/filter_words.py --use-case wordle --distribution plus
```

## Next Steps

After committing reports:
1. Review with team: Do the audit findings validate the approach?
2. Check label coverage: Is it sufficient for your game filtering needs?
3. Compare with wiktextract: Is the simple parser missing anything critical?
4. Test filters: Do the generated word lists meet quality expectations?
5. Iterate: Enhance parser if needed, update reports

## Questions?

See the audit and statistics reports for:
- What percentage of pages have English sections?
- What label coverage do we have?
- Are there enough regional labels for Wordle filtering?
- Are there enough register labels for content filtering?
- What label combinations exist?
