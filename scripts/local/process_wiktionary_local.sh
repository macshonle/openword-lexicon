#!/usr/bin/env bash
# process_wiktionary_local.sh - Local Wiktionary download and processing script
#
# Run this on your local machine to download and process Wiktionary data.
# This script will:
# 1. Download the Wiktionary dump (~2-3GB)
# 2. Process it with the scanner parser
# 3. Generate a detailed report
# 4. Tell you what files to copy back to the project
#
# Usage:
#   bash scripts/local/process_wiktionary_local.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Wiktionary Local Processing Script                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
LANG="${LEXICON_LANG:-en}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RAW_DIR="${PROJECT_ROOT}/data/raw/${LANG}"
INTERMEDIATE_DIR="${PROJECT_ROOT}/data/intermediate/${LANG}"
REPORT_DIR="${PROJECT_ROOT}/reports/local"

DUMP_FILE="enwiktionary-latest-pages-articles.xml.bz2"
DUMP_URL="https://dumps.wikimedia.org/enwiktionary/latest/${DUMP_FILE}"
OUTPUT_FILE="${INTERMEDIATE_DIR}/wikt.jsonl"
REPORT_FILE="${REPORT_DIR}/wiktionary_processing_report.md"

# Create directories
mkdir -p "${RAW_DIR}"
mkdir -p "${INTERMEDIATE_DIR}"
mkdir -p "${REPORT_DIR}"

echo -e "${GREEN}Configuration:${NC}"
echo "  Project root: ${PROJECT_ROOT}"
echo "  Language: ${LANG}"
echo "  Raw data: ${RAW_DIR}"
echo "  Intermediate: ${INTERMEDIATE_DIR}"
echo "  Report: ${REPORT_FILE}"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: 'uv' not found.${NC}"
    echo "Please install uv first: https://docs.astral.sh/uv/"
    exit 1
fi

# Step 1: Download Wiktionary dump
echo -e "${YELLOW}Step 1: Downloading Wiktionary dump${NC}"
echo "  URL: ${DUMP_URL}"
echo "  Size: ~2-3 GB (this may take 10-30 minutes depending on connection)"
echo ""

DUMP_PATH="${RAW_DIR}/${DUMP_FILE}"

if [[ -f "${DUMP_PATH}" ]]; then
    echo -e "${GREEN}✓ Dump already exists: ${DUMP_PATH}${NC}"

    # Ask if user wants to re-download
    read -p "Re-download? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "  Skipping download, using existing file."
    else
        rm "${DUMP_PATH}"
        echo "  Downloading fresh copy..."

        if command -v wget &> /dev/null; then
            wget --continue --show-progress -O "${DUMP_PATH}" "${DUMP_URL}"
        elif command -v curl &> /dev/null; then
            curl -C - -o "${DUMP_PATH}" "${DUMP_URL}"
        else
            echo -e "${RED}Error: neither wget nor curl found${NC}"
            exit 1
        fi
    fi
else
    echo "  Downloading..."

    if command -v wget &> /dev/null; then
        wget --continue --show-progress -O "${DUMP_PATH}" "${DUMP_URL}"
    elif command -v curl &> /dev/null; then
        curl -C - -o "${DUMP_PATH}" "${DUMP_URL}"
    else
        echo -e "${RED}Error: neither wget nor curl found${NC}"
        exit 1
    fi
fi

# Verify download
if [[ ! -s "${DUMP_PATH}" ]]; then
    echo -e "${RED}Error: Downloaded file is empty or missing${NC}"
    exit 1
fi

DUMP_SIZE=$(du -h "${DUMP_PATH}" | cut -f1)
echo -e "${GREEN}✓ Download complete: ${DUMP_SIZE}${NC}"
echo ""

# Step 2: Process with scanner parser
echo -e "${YELLOW}Step 2: Processing Wiktionary dump${NC}"
echo "  Input: ${DUMP_PATH}"
echo "  Output: ${OUTPUT_FILE}"
echo "  Note: This may take 20-60 minutes depending on CPU speed"
echo ""

START_TIME=$(date +%s)

cd "${PROJECT_ROOT}"
uv run python tools/wiktionary_scanner_parser.py \
    "${DUMP_PATH}" \
    "${OUTPUT_FILE}" 2>&1 | tee "${REPORT_DIR}/processing.log"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo -e "${GREEN}✓ Processing complete (${MINUTES}m ${SECONDS}s)${NC}"
echo ""

# Step 3: Analyze output and generate report
echo -e "${YELLOW}Step 3: Generating analysis report${NC}"
echo ""

# Count entries
ENTRY_COUNT=$(wc -l < "${OUTPUT_FILE}" | tr -d ' ')

# Sample entries
SAMPLE_SIZE=10
SAMPLES=$(head -n ${SAMPLE_SIZE} "${OUTPUT_FILE}")

# Count entries with syllables
SYLLABLE_COUNT=$(grep -c '"syllables"' "${OUTPUT_FILE}" || true)

# Count entries with labels
LABEL_COUNT=$(grep -c '"labels"' "${OUTPUT_FILE}" || true)

# Count POS tags
POS_STATS=$(jq -r '.pos[]' "${OUTPUT_FILE}" 2>/dev/null | sort | uniq -c | sort -rn | head -20 || echo "Unable to parse POS stats")

# File sizes
OUTPUT_SIZE=$(du -h "${OUTPUT_FILE}" | cut -f1)
DUMP_SIZE=$(du -h "${DUMP_PATH}" | cut -f1)

# Generate markdown report
cat > "${REPORT_FILE}" <<EOF
# Wiktionary Processing Report

**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Language:** ${LANG}
**Processing time:** ${MINUTES}m ${SECONDS}s

---

## Summary

| Metric | Value |
|--------|------:|
| **Total entries extracted** | ${ENTRY_COUNT} |
| **Entries with syllable data** | ${SYLLABLE_COUNT} |
| **Entries with labels** | ${LABEL_COUNT} |
| **Syllable coverage** | $((SYLLABLE_COUNT * 100 / ENTRY_COUNT))% |
| **Label coverage** | $((LABEL_COUNT * 100 / ENTRY_COUNT))% |

---

## Files Generated

### Input
- **Wiktionary dump:** \`${DUMP_PATH}\`
  - Size: ${DUMP_SIZE}
  - Download time: See processing.log

### Output
- **Processed JSONL:** \`${OUTPUT_FILE}\`
  - Size: ${OUTPUT_SIZE}
  - Entries: ${ENTRY_COUNT}
  - Format: One JSON object per line

---

## Quality Checks

### Syllable Data
$(if [[ ${SYLLABLE_COUNT} -gt 0 ]]; then
    echo "✅ **PASS** - Syllable data found (${SYLLABLE_COUNT} entries, $((SYLLABLE_COUNT * 100 / ENTRY_COUNT))% coverage)"
    echo ""
    echo "Expected coverage: 30-50% based on Wiktionary's hyphenation template usage."
else
    echo "⚠️  **WARNING** - No syllable data found"
    echo ""
    echo "This is unexpected. Check that the scanner parser is extracting syllables correctly."
fi)

### Label Data
$(if [[ ${LABEL_COUNT} -gt 0 ]]; then
    echo "✅ **PASS** - Label data found (${LABEL_COUNT} entries, $((LABEL_COUNT * 100 / ENTRY_COUNT))% coverage)"
else
    echo "⚠️  **WARNING** - No label data found"
fi)

### Entry Count
$(if [[ ${ENTRY_COUNT} -gt 100000 ]]; then
    echo "✅ **PASS** - Entry count looks reasonable (${ENTRY_COUNT} entries)"
    echo ""
    echo "Expected: 500k-800k English words/phrases from Wiktionary."
else
    echo "⚠️  **WARNING** - Entry count seems low (${ENTRY_COUNT} entries)"
    echo ""
    echo "Expected at least 100k entries. The extraction may have failed partway through."
fi)

---

## Sample Entries

First ${SAMPLE_SIZE} entries from the output file:

\`\`\`json
${SAMPLES}
\`\`\`

---

## POS Tag Distribution

Top 20 most common POS tags:

\`\`\`
${POS_STATS}
\`\`\`

---

## Next Steps

### If processing succeeded:

1. **Copy the processed file to your remote environment:**
   \`\`\`bash
   # On your local machine, compress the file for transfer:
   gzip -c "${OUTPUT_FILE}" > wikt.jsonl.gz

   # Transfer to remote (adjust path as needed):
   scp wikt.jsonl.gz remote:/path/to/openword-lexicon/data/intermediate/en/

   # On remote, decompress:
   gunzip -c wikt.jsonl.gz > data/intermediate/en/wikt.jsonl
   \`\`\`

2. **Or, if using the same filesystem, the file is already in place!**
   Just continue with the build:
   \`\`\`bash
   make build-en
   \`\`\`

3. **Expected improvements after rebuild:**
   - Syllable coverage: 0% → 30-50% (~60k-100k words)
   - Label coverage: 0% → 60-80% (register, domain, region tags)
   - Total words: 208k → 800k-1.2M (ENABLE+EOWL+Wiktionary)
   - Multi-word phrases: many more compound terms and idioms

### If processing failed:

Check the log file for errors:
\`\`\`bash
cat "${REPORT_DIR}/processing.log"
\`\`\`

Common issues:
- Corrupted download: Re-download with \`rm ${DUMP_PATH}\` and run again
- Parser errors: Check Python version (requires 3.11+)
- Out of memory: Processing requires ~4-8GB RAM
- Disk space: Ensure ~10GB free space

---

## File Locations

All files are in the project directory structure:

\`\`\`
data/
├── raw/en/
│   └── enwiktionary-latest-pages-articles.xml.bz2  (${DUMP_SIZE})
└── intermediate/en/
    └── wikt.jsonl  (${OUTPUT_SIZE}, ${ENTRY_COUNT} entries)

reports/local/
├── wiktionary_processing_report.md  (this file)
└── processing.log  (detailed processing output)
\`\`\`

---

## Integration Status

After copying this file to your build environment:

- [ ] Run \`uv run python src/openword/wikt_ingest.py\`
- [ ] Run \`uv run python src/openword/merge_all.py\`
- [ ] Run \`uv run python src/openword/wordnet_enrich.py --unified\`
- [ ] Run \`uv run python src/openword/brysbaert_enrich.py --unified\`
- [ ] Run \`uv run python src/openword/frequency_tiers.py --unified\`
- [ ] Run \`uv run python src/openword/trie_build.py --unified\`
- [ ] Run \`uv run python tools/analyze_metadata.py en\`
- [ ] Verify syllable coverage in report: \`grep "Syllables" reports/metadata_analysis_en.md\`

EOF

# Display report
echo -e "${GREEN}✓ Report generated: ${REPORT_FILE}${NC}"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
cat "${REPORT_FILE}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Processing Complete!                                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Quick Summary:${NC}"
echo "  ✓ Downloaded: ${DUMP_SIZE}"
echo "  ✓ Processed: ${ENTRY_COUNT} entries"
echo "  ✓ Syllables: ${SYLLABLE_COUNT} entries ($((SYLLABLE_COUNT * 100 / ENTRY_COUNT))%)"
echo "  ✓ Output: ${OUTPUT_FILE} (${OUTPUT_SIZE})"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review the report: ${REPORT_FILE}"
echo "  2. If on same machine: Run 'make build-en' to rebuild with Wiktionary data"
echo "  3. If remote: Copy ${OUTPUT_FILE} to your remote environment"
echo ""
echo -e "${BLUE}Full report saved to: ${REPORT_FILE}${NC}"
echo ""
