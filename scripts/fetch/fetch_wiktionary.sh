#!/usr/bin/env bash
# fetch_wiktionary.sh — Download Wiktionary English dump
# Source: Wikimedia dumps (CC BY-SA 4.0)

set -euo pipefail

# Configuration
readonly WIKTIONARY_BASE="https://dumps.wikimedia.org/enwiktionary"
readonly LANG="${LEXICON_LANG:-en}"
readonly OUTPUT_DIR="data/raw/${LANG}"
readonly DUMP_FILE="enwiktionary-latest-pages-articles.xml.bz2"
readonly OUTPUT_FILE="${OUTPUT_DIR}/${DUMP_FILE}"
readonly SOURCE_FILE="${OUTPUT_DIR}/wiktionary.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Fetching Wiktionary English dump..."
echo "  Note: This is a large file (~1.5 GB compressed)"
echo "  URL: ${WIKTIONARY_BASE}/latest/${DUMP_FILE}"

# Check if file already exists and is recent (less than 30 days old)
if [[ -f "$OUTPUT_FILE" ]]; then
    FILE_AGE_DAYS=$(( ($(date +%s) - $(stat -c %Y "$OUTPUT_FILE" 2>/dev/null || stat -f %m "$OUTPUT_FILE" 2>/dev/null || echo 0)) / 86400 ))
    if [[ $FILE_AGE_DAYS -lt 30 ]]; then
        echo "  ℹ Wiktionary dump already exists and is less than 30 days old"
        echo "  Skipping download (delete $OUTPUT_FILE to re-download)"

        # Still create/update SOURCE.json if it doesn't exist
        if [[ ! -f "$SOURCE_FILE" ]]; then
            # Calculate checksum for existing file
            if command -v sha256sum &> /dev/null; then
                CHECKSUM=$(sha256sum "$OUTPUT_FILE" | awk '{print $1}')
            elif command -v shasum &> /dev/null; then
                CHECKSUM=$(shasum -a 256 "$OUTPUT_FILE" | awk '{print $1}')
            else
                CHECKSUM="unavailable"
            fi

            FILE_SIZE=$(stat -c %s "$OUTPUT_FILE" 2>/dev/null || stat -f %z "$OUTPUT_FILE" 2>/dev/null || echo 0)

            cat > "$SOURCE_FILE" <<EOF
{
  "name": "Wiktionary",
  "title": "English Wiktionary pages-articles dump",
  "author": "Wiktionary contributors",
  "url": "${WIKTIONARY_BASE}/latest/${DUMP_FILE}",
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
  "attribution": "This dataset includes material from Wiktionary (https://www.wiktionary.org/), available under the Creative Commons Attribution-ShareAlike License (CC BY-SA 4.0). See individual page histories for authorship.",
  "sha256": "$CHECKSUM",
  "file_size_bytes": $FILE_SIZE,
  "format": "application/xml+bzip2",
  "encoding": "UTF-8",
  "notes": "Full English Wiktionary dump - requires XML parsing to extract entries",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
        fi

        echo "✓ Using existing Wiktionary dump"
        exit 0
    fi
fi

# Download with wget or curl (with resume support)
echo "  Starting download (this may take several minutes)..."

DOWNLOAD_SUCCESS=false

if command -v wget &> /dev/null; then
    # wget with resume, progress, and rate limiting to be nice to servers
    if wget -c --show-progress --limit-rate=10M \
         -O "$OUTPUT_FILE" \
         "${WIKTIONARY_BASE}/latest/${DUMP_FILE}"; then
        DOWNLOAD_SUCCESS=true
    fi
elif command -v curl &> /dev/null; then
    # curl with resume support
    if curl -fSL -C - --limit-rate 10M \
         -o "$OUTPUT_FILE" \
         "${WIKTIONARY_BASE}/latest/${DUMP_FILE}"; then
        DOWNLOAD_SUCCESS=true
    fi
else
    echo "Error: neither wget nor curl found"
    exit 1
fi

# Check if download succeeded
if [[ "$DOWNLOAD_SUCCESS" == false ]]; then
    echo "⚠ Warning: Wiktionary download failed (network/access issue)"
    echo "  This is optional for testing. Skipping Wiktionary dump."
    echo "  In production, ensure network access to dumps.wikimedia.org"

    # Remove partial/empty file
    rm -f "$OUTPUT_FILE"

    # Exit successfully (don't block the build)
    exit 0
fi

# Verify file was downloaded
if [[ ! -s "$OUTPUT_FILE" ]]; then
    echo "⚠ Warning: Downloaded file is empty"
    rm -f "$OUTPUT_FILE"
    echo "  Skipping Wiktionary (can retry later)"
    exit 0
fi

echo "  Computing checksum (this may take a minute)..."

# Calculate SHA256
if command -v sha256sum &> /dev/null; then
    CHECKSUM=$(sha256sum "$OUTPUT_FILE" | awk '{print $1}')
elif command -v shasum &> /dev/null; then
    CHECKSUM=$(shasum -a 256 "$OUTPUT_FILE" | awk '{print $1}')
else
    echo "Warning: No SHA256 tool found, skipping checksum"
    CHECKSUM="unavailable"
fi

# Get file size
FILE_SIZE=$(stat -c %s "$OUTPUT_FILE" 2>/dev/null || stat -f %z "$OUTPUT_FILE" 2>/dev/null || echo 0)
FILE_SIZE_MB=$(( FILE_SIZE / 1024 / 1024 ))

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "Wiktionary",
  "title": "English Wiktionary pages-articles dump",
  "author": "Wiktionary contributors",
  "url": "${WIKTIONARY_BASE}/latest/${DUMP_FILE}",
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
  "attribution": "This dataset includes material from Wiktionary (https://www.wiktionary.org/), available under the Creative Commons Attribution-ShareAlike License (CC BY-SA 4.0). See individual page histories for authorship.",
  "sha256": "$CHECKSUM",
  "file_size_bytes": $FILE_SIZE,
  "format": "application/xml+bzip2",
  "encoding": "UTF-8",
  "notes": "Full English Wiktionary dump - requires XML parsing to extract entries",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ Wiktionary fetched: ${FILE_SIZE_MB} MB"
echo "  File: $OUTPUT_FILE"
echo "  SHA256: $CHECKSUM"
