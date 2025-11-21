#!/usr/bin/env bash
# fetch_brysbaert.sh — Download Brysbaert concreteness ratings
# Source: Brysbaert, Warriner, & Kuperman (2014)
# Citation: Concreteness ratings for 40 thousand generally known English word lemmas
#           Behavior Research Methods, 46, 904-911
# Note: Data shared for research purposes via GitHub (ArtsEngine/concreteness)

set -euo pipefail

# Configuration
readonly BRYSBAERT_URL="https://raw.githubusercontent.com/ArtsEngine/concreteness/master/Concreteness_ratings_Brysbaert_et_al_BRM.txt"
readonly LANG="${LEXICON_LANG:-en}"
readonly OUTPUT_DIR="data/raw/${LANG}"
readonly OUTPUT_FILE="${OUTPUT_DIR}/brysbaert_concreteness.txt"
readonly SOURCE_FILE="${OUTPUT_DIR}/brysbaert.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Fetching Brysbaert concreteness ratings..."
echo "  URL: $BRYSBAERT_URL"

# Download with wget or curl
if command -v wget &> /dev/null; then
    wget -q --show-progress -O "$OUTPUT_FILE" "$BRYSBAERT_URL"
elif command -v curl &> /dev/null; then
    curl -fsSL -o "$OUTPUT_FILE" "$BRYSBAERT_URL"
else
    echo "Error: neither wget nor curl found"
    exit 1
fi

# Verify file was downloaded
if [[ ! -s "$OUTPUT_FILE" ]]; then
    echo "Error: Downloaded file is empty"
    exit 1
fi

# Calculate SHA256
if command -v sha256sum &> /dev/null; then
    CHECKSUM=$(sha256sum "$OUTPUT_FILE" | awk '{print $1}')
elif command -v shasum &> /dev/null; then
    CHECKSUM=$(shasum -a 256 "$OUTPUT_FILE" | awk '{print $1}')
else
    echo "Warning: No SHA256 tool found, skipping checksum"
    CHECKSUM="unavailable"
fi

# Count entries (subtract header line)
ENTRY_COUNT=$(($(wc -l < "$OUTPUT_FILE" | tr -d ' ') - 1))

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "Brysbaert Concreteness",
  "title": "Concreteness ratings for 40 thousand generally known English word lemmas",
  "authors": "Marc Brysbaert, Amy Beth Warriner, Victor Kuperman",
  "year": 2014,
  "journal": "Behavior Research Methods",
  "volume": 46,
  "pages": "904-911",
  "doi": "10.3758/s13428-013-0403-5",
  "url": "$BRYSBAERT_URL",
  "license": "Research/Educational use (shared by authors)",
  "license_note": "Data made available for research purposes. For commercial use, verify terms with authors.",
  "sha256": "$CHECKSUM",
  "entry_count": $ENTRY_COUNT,
  "format": "tab-separated values",
  "encoding": "UTF-8",
  "notes": "Concreteness ratings from crowdsourcing (5-point scale: 1=abstract, 5=concrete). Covers ~40k English lemmas.",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ Brysbaert concreteness ratings fetched: $ENTRY_COUNT entries"
echo "  File: $OUTPUT_FILE"
echo "  SHA256: $CHECKSUM"
