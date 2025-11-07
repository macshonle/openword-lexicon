#!/usr/bin/env bash
# fetch_enable.sh — Download ENABLE word list (public domain)
# Source: Enhanced North American Benchmark LExicon by Alan Beale

set -euo pipefail

# Configuration
readonly ENABLE_URL="https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
readonly OUTPUT_DIR="data/raw/core"
readonly OUTPUT_FILE="${OUTPUT_DIR}/enable1.txt"
readonly SOURCE_FILE="${OUTPUT_DIR}/enable1.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "→ Fetching ENABLE word list..."
echo "  URL: $ENABLE_URL"

# Download with wget or curl
if command -v wget &> /dev/null; then
    wget -q --show-progress -O "$OUTPUT_FILE" "$ENABLE_URL"
elif command -v curl &> /dev/null; then
    curl -fsSL -o "$OUTPUT_FILE" "$ENABLE_URL"
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

# Count words
WORD_COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "ENABLE",
  "title": "Enhanced North American Benchmark LExicon",
  "author": "Alan Beale et al.",
  "url": "$ENABLE_URL",
  "license": "Public Domain",
  "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "sha256": "$CHECKSUM",
  "word_count": $WORD_COUNT,
  "format": "text/plain",
  "encoding": "UTF-8",
  "notes": "Public domain word list for word games and NLP applications",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ ENABLE fetched: $WORD_COUNT words"
echo "  File: $OUTPUT_FILE"
echo "  SHA256: $CHECKSUM"
