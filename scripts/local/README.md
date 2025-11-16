# Local Processing Scripts

These scripts are designed to be run on your **local machine** (not in sandboxed/restricted environments) for tasks that require network access or heavy processing.

## Overview

Some data sources (like Wiktionary dumps) are very large (2-3GB) and may not be accessible from all environments. These scripts allow you to:

1. Download and process data on your local machine
2. Generate detailed reports
3. Transfer the processed data to your build environment

## Scripts

### 1. `process_wiktionary_local.sh`

**Purpose:** Download and process the Wiktionary dump locally.

**What it does:**
- Downloads the latest Wiktionary English dump (~2-3GB)
- Processes it with the scanner parser to extract:
  - Word entries
  - Syllable counts (hyphenation data)
  - POS tags
  - Labels (register, domain, region, temporal)
  - Lemmas
  - Phrases
- Generates a comprehensive report
- Tells you what to do next

**Usage:**
```bash
# On your local machine:
cd /path/to/openword-lexicon
bash scripts/local/process_wiktionary_local.sh
```

**Requirements:**
- 10GB+ free disk space
- Good internet connection (2-3GB download)
- 4-8GB RAM
- uv (Python package manager)
- 20-60 minutes processing time

**Output:**
- `data/raw/en/enwiktionary-latest-pages-articles.xml.bz2` (2-3GB)
- `data/intermediate/en/wikt.jsonl` (300-500MB)
- `reports/local/wiktionary_processing_report.md` (detailed report)
- `reports/local/processing.log` (processing output)

**After running:**

If on the same machine as your build environment:
```bash
make build-en
```

If on a different machine:
```bash
# Compress for transfer
gzip -c data/intermediate/en/wikt.jsonl > wikt.jsonl.gz

# Transfer to remote
scp wikt.jsonl.gz user@remote:/path/to/openword-lexicon/data/intermediate/en/

# On remote, decompress
cd /path/to/openword-lexicon
gunzip -c data/intermediate/en/wikt.jsonl.gz > data/intermediate/en/wikt.jsonl

# Verify and build
bash scripts/local/verify_wiktionary_ready.sh
make build-en
```

---

### 2. `verify_wiktionary_ready.sh`

**Purpose:** Verify that Wiktionary data is properly integrated and ready for building.

**What it does:**
- Checks if the processed file exists
- Validates entry count (should be 500k-800k)
- Validates JSON format
- Checks syllable data coverage (should be 30-50%)
- Checks label data coverage (should be 60-80%)
- Verifies entry structure
- Analyzes POS tag variety

**Usage:**
```bash
# After copying wikt.jsonl to your build environment:
bash scripts/local/verify_wiktionary_ready.sh
```

**Output:**
- ✓/✗ status for each check
- Summary of what's ready
- Instructions for next steps
- Exit code 0 if all passed, 1 if any failed

---

## Expected Improvements After Wiktionary Integration

### Before (ENABLE + EOWL only):
- **Total words:** 208,201
- **Syllable coverage:** 0%
- **Label coverage:** 0%
- **Multi-word phrases:** 0
- **POS coverage:** 52.5% (from WordNet only)

### After (ENABLE + EOWL + Wiktionary):
- **Total words:** 800,000 - 1,200,000
- **Syllable coverage:** 30-50% (~300k-500k words)
- **Label coverage:** 60-80% (register, domain, region)
- **Multi-word phrases:** 100k+ compound terms and idioms
- **POS coverage:** 90%+ (Wiktionary provides excellent POS tags)

### New Capabilities:
- ✅ Syllable-based filtering (e.g., 1-2 syllable words for children's games)
- ✅ Register filtering (formal, informal, slang, vulgar, etc.)
- ✅ Domain filtering (medicine, law, sports, etc.)
- ✅ Regional filtering (en-US, en-GB, en-AU, etc.)
- ✅ Multi-word phrases (idioms, compound words)
- ✅ Temporal filtering (archaic, obsolete, dated)

---

## Troubleshooting

### "No space left on device"
You need at least 10GB free:
- Wiktionary dump: 2-3GB
- Decompressed XML: 4-5GB (temporary)
- Processed JSONL: 300-500MB
- Headroom: 1-2GB

### "Connection timeout" during download
Use `wget --continue` or `curl -C -` to resume:
```bash
wget --continue -O data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
  https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2
```

### "Out of memory" during processing
The scanner parser needs 4-8GB RAM. Try:
- Close other applications
- Use a machine with more RAM
- Process in chunks (not currently supported, but possible to add)

### "Low syllable coverage" (< 20%)
This suggests the scanner parser isn't extracting syllables correctly:
- Check that you're using the latest version
- Look at sample entries in the report
- File an issue if the parser needs fixing

### "Entry count too low" (< 100k)
The processing may have failed partway through:
- Check `reports/local/processing.log` for errors
- Re-download the dump (it may be corrupted)
- Try again with more disk space/RAM

---

## File Transfer Methods

### Same filesystem
If scripts/local is on the same machine as your build:
```bash
# Nothing to do! Files are already in place.
make build-en
```

### SCP (Secure Copy)
```bash
# From local to remote
scp data/intermediate/en/wikt.jsonl user@remote:/path/to/project/data/intermediate/en/

# Or compressed (recommended for slow connections)
gzip -c data/intermediate/en/wikt.jsonl | ssh user@remote "gunzip > /path/to/project/data/intermediate/en/wikt.jsonl"
```

### rsync (Incremental transfer)
```bash
rsync -avz --progress data/intermediate/en/wikt.jsonl user@remote:/path/to/project/data/intermediate/en/
```

### Cloud storage
```bash
# Upload to S3, GCS, etc.
aws s3 cp data/intermediate/en/wikt.jsonl s3://your-bucket/
gcloud storage cp data/intermediate/en/wikt.jsonl gs://your-bucket/

# Download on remote
aws s3 cp s3://your-bucket/wikt.jsonl data/intermediate/en/
gcloud storage cp gs://your-bucket/wikt.jsonl data/intermediate/en/
```

---

## Tips

1. **Process once, use many times:** The processed `wikt.jsonl` file is stable. You can process once and reuse it across environments.

2. **Keep the dump:** The Wiktionary dump doesn't change often. Keep `enwiktionary-latest-pages-articles.xml.bz2` so you don't have to re-download.

3. **Automate with cron:** Set up a monthly job to update Wiktionary data:
   ```bash
   # Run on the 1st of each month at 2am
   0 2 1 * * cd /path/to/openword-lexicon && bash scripts/local/process_wiktionary_local.sh
   ```

4. **Check the report first:** Always review `reports/local/wiktionary_processing_report.md` before transferring files. It contains quality checks and next steps.

---

## Support

If you encounter issues:

1. Check `reports/local/processing.log` for detailed error messages
2. Review the quality checks in `reports/local/wiktionary_processing_report.md`
3. Run `bash scripts/local/verify_wiktionary_ready.sh` to diagnose integration issues
4. File an issue at https://github.com/anthropics/claude-code/issues with:
   - Your OS and version
   - Available RAM and disk space
   - Relevant log excerpts
   - The processing report
