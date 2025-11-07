#!/usr/bin/env bash
# fetch_eowl.sh — Download English Open Word List (EOWL)
# Source: EOWL by Ken Loge, derived from UKACD by J. Ross Beresford

set -euo pipefail

# Configuration
readonly EOWL_REPO="https://github.com/kloge/The-English-Open-Word-List.git"
readonly OUTPUT_DIR="data/raw/core"
readonly TEMP_DIR="${OUTPUT_DIR}/eowl_temp"
readonly OUTPUT_FILE="${OUTPUT_DIR}/eowl.txt"
readonly SOURCE_FILE="${OUTPUT_DIR}/eowl.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "→ Fetching EOWL (English Open Word List)..."
echo "  Repository: $EOWL_REPO"

# Clone repository (shallow clone to save bandwidth)
if [[ -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
fi

git clone --depth 1 --quiet "$EOWL_REPO" "$TEMP_DIR"

# The word lists are split by letter in subdirectories
# Concatenate all letter files from "EOWL LF Delimited Format" directory
EOWL_DIR="$TEMP_DIR/EOWL LF Delimited Format"

if [[ ! -d "$EOWL_DIR" ]]; then
    echo "Error: Could not find EOWL directory at $EOWL_DIR"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Concatenate all letter files (A Words.txt, B Words.txt, etc.)
cat "$EOWL_DIR/"*" Words.txt" > "$OUTPUT_FILE"

# Verify file was created
if [[ ! -s "$OUTPUT_FILE" ]]; then
    echo "Error: Output file is empty"
    rm -rf "$TEMP_DIR"
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

# Count words
WORD_COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')

# Get git commit hash for provenance
cd "$TEMP_DIR"
GIT_COMMIT=$(git rev-parse HEAD)
cd - > /dev/null

# Cleanup temp directory
rm -rf "$TEMP_DIR"

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "EOWL",
  "title": "English Open Word List",
  "author": "Ken Loge (derived from UK Advanced Cryptics Dictionary by J. Ross Beresford)",
  "url": "$EOWL_REPO",
  "git_commit": "$GIT_COMMIT",
  "license": "UKACD License",
  "license_text": "The UK Advanced Cryptics Dictionary (UKACD) is © J Ross Beresford 1993–1999. Permission is granted to use this list for any purpose provided this notice is retained. No warranty is given.",
  "license_url": "https://github.com/kloge/The-English-Open-Word-List/blob/master/README.md",
  "sha256": "$CHECKSUM",
  "word_count": $WORD_COUNT,
  "format": "text/plain",
  "encoding": "UTF-8",
  "notes": "Words up to 10 letters, no proper nouns, no hyphens, diacritics removed",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ EOWL fetched: $WORD_COUNT words"
echo "  File: $OUTPUT_FILE"
echo "  SHA256: $CHECKSUM"
