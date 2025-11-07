#!/usr/bin/env bash
# fetch_wordnet.sh — Download Open English WordNet
# Source: Global WordNet Association (CC BY 4.0)

set -euo pipefail

# Configuration
readonly WORDNET_REPO="https://github.com/globalwordnet/english-wordnet.git"
readonly WORDNET_TAG="2024"  # Use 2024 Edition
readonly OUTPUT_DIR="data/raw/plus"
readonly TEMP_DIR="${OUTPUT_DIR}/wordnet_temp"
readonly OUTPUT_ARCHIVE="${OUTPUT_DIR}/english-wordnet-2024.tar.gz"
readonly SOURCE_FILE="${OUTPUT_DIR}/wordnet.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "→ Fetching Open English WordNet (2024 Edition)..."
echo "  Repository: $WORDNET_REPO"

# Check if archive already exists
if [[ -f "$OUTPUT_ARCHIVE" ]] && [[ -f "$SOURCE_FILE" ]]; then
    echo "  ℹ WordNet archive already exists"
    echo "  Skipping download (delete $OUTPUT_ARCHIVE to re-download)"
    echo "✓ Using existing WordNet data"
    exit 0
fi

# Clone repository (shallow clone for specific tag/release)
if [[ -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
fi

echo "  Cloning repository..."
git clone --depth 1 --branch "$WORDNET_TAG" --quiet "$WORDNET_REPO" "$TEMP_DIR" || \
git clone --depth 1 --quiet "$WORDNET_REPO" "$TEMP_DIR"

# Get git commit hash for provenance
cd "$TEMP_DIR"
GIT_COMMIT=$(git rev-parse HEAD)
GIT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "main")
cd - > /dev/null

# Create archive of the data files
echo "  Creating archive..."
tar -czf "$OUTPUT_ARCHIVE" -C "$TEMP_DIR" .

# Verify archive was created
if [[ ! -s "$OUTPUT_ARCHIVE" ]]; then
    echo "Error: Archive creation failed"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Calculate SHA256
if command -v sha256sum &> /dev/null; then
    CHECKSUM=$(sha256sum "$OUTPUT_ARCHIVE" | awk '{print $1}')
elif command -v shasum &> /dev/null; then
    CHECKSUM=$(shasum -a 256 "$OUTPUT_ARCHIVE" | awk '{print $1}')
else
    echo "Warning: No SHA256 tool found, skipping checksum"
    CHECKSUM="unavailable"
fi

# Get file size
FILE_SIZE=$(stat -c %s "$OUTPUT_ARCHIVE" 2>/dev/null || stat -f %z "$OUTPUT_ARCHIVE" 2>/dev/null || echo 0)
FILE_SIZE_MB=$(( FILE_SIZE / 1024 / 1024 ))

# Cleanup temp directory
rm -rf "$TEMP_DIR"

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "Open English WordNet",
  "title": "Open English WordNet 2024 Edition",
  "author": "Global WordNet Association",
  "url": "$WORDNET_REPO",
  "git_commit": "$GIT_COMMIT",
  "git_tag": "$GIT_TAG",
  "license": "CC BY 4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "citation": "McCrae, J. P., Rademaker, A., Rudnicka, E., & Bond, F. (2020). English WordNet 2020: Improving and Extending a WordNet for English using an Open-Source Methodology. In Proceedings of the LREC 2020 Workshop on Multimodal Wordnets (MMW2020)",
  "sha256": "$CHECKSUM",
  "file_size_bytes": $FILE_SIZE,
  "format": "application/gzip",
  "encoding": "UTF-8",
  "notes": "Community-maintained WordNet with semantic relationships, updated 2024",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ WordNet fetched: ${FILE_SIZE_MB} MB"
echo "  File: $OUTPUT_ARCHIVE"
echo "  SHA256: $CHECKSUM"
