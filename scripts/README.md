# Scripts Directory

This directory contains utility scripts for the Openword Lexicon build pipeline.

## Directory Structure

```
scripts/
└── fetch/        # Data source fetch scripts
```

## Fetch Scripts (`fetch/`)

All fetch scripts follow a common pattern:
1. Download source data
2. Verify download succeeded
3. Calculate SHA256 checksum
4. Create `*.SOURCE.json` metadata file with TASL (Title, Author, Source, License)

### Core Distribution (Public Domain / Permissive)

#### `fetch_enable.sh`
- **Source:** ENABLE word list (Alan Beale)
- **License:** Public Domain (CC0-compatible)
- **Output:** `data/raw/core/enable1.txt` (~173K words)
- **Metadata:** `enable1.SOURCE.json`

#### `fetch_eowl.sh`
- **Source:** English Open Word List (Ken Loge / J. Ross Beresford)
- **License:** UKACD License (unrestricted use with attribution)
- **Output:** `data/raw/core/eowl.txt` (~129K words, max 10 letters)
- **Metadata:** `eowl.SOURCE.json`

### Plus Distribution (CC-BY-SA Enhanced)

#### `fetch_wiktionary.sh`
- **Source:** English Wiktionary dump (Wikimedia)
- **License:** CC BY-SA 4.0
- **Output:** `data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2` (~2-3 GB)
- **Metadata:** `wiktionary.SOURCE.json`
- **Notes:**
  - Large download; includes resume support
  - Rate-limited to 10 MB/s to be nice to Wikimedia servers
  - Cached for 30 days (skips re-download if recent)
  - Requires XML parsing in later pipeline stages

#### `fetch_wordnet.sh`
- **Source:** Open English WordNet 2024 (Global WordNet Association)
- **License:** CC BY 4.0
- **Output:** `data/raw/plus/english-wordnet-2024.tar.gz` (~22 MB)
- **Metadata:** `wordnet.SOURCE.json`
- **Notes:** Community-maintained semantic lexicon

#### `fetch_frequency.sh`
- **Source:** FrequencyWords / OpenSubtitles 2018 (Hermit Dave)
- **License:** CC BY-SA 4.0
- **Output:** `data/raw/plus/en_50k.txt` (~50K entries, 608 KB)
- **Metadata:** `frequency.SOURCE.json`
- **Format:** Each line: `word<space>frequency`

## Running Fetches

Via Makefile (recommended):
```bash
make fetch-core    # Download ENABLE + EOWL
make fetch-plus    # Download Wiktionary + WordNet + Frequency
make check-limits  # Verify constraints
```

Direct execution:
```bash
bash scripts/fetch/fetch_enable.sh
bash scripts/fetch/fetch_eowl.sh
# ... etc
```

## SOURCE.json Format

Each downloaded source gets a metadata file:

```json
{
  "name": "ENABLE",
  "title": "Enhanced North American Benchmark LExicon",
  "author": "Alan Beale et al.",
  "url": "https://...",
  "license": "Public Domain",
  "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "sha256": "3f16130220645692ed49c7134e24a18504c2ca55b3c012f7290e3e77c63b1a89",
  "word_count": 172823,
  "format": "text/plain",
  "encoding": "UTF-8",
  "notes": "...",
  "downloaded_at": "2025-11-06T22:14:36Z"
}
```

This metadata flows into:
- `ATTRIBUTION.md` (human-readable)
- `MANIFEST.json` (machine-readable release manifest)
- `data/LICENSE` (distribution-specific)

## Error Handling

All fetch scripts:
- Exit with non-zero status on critical failures
- Create SOURCE.json even for cached/skipped downloads
- Include checksums for reproducibility
- Log download timestamps for audit trail

Network-dependent scripts (Wiktionary) gracefully skip on access failures during testing, logging a warning instead of blocking the build.
