#!/usr/bin/env bash
# fetch_frequency.sh — Download word frequency list
# Source: FrequencyWords - OpenSubtitles 2018 (CC BY-SA 4.0)

set -euo pipefail

# Configuration
readonly FREQ_REPO="https://github.com/hermitdave/FrequencyWords.git"
readonly LANG="${LEXICON_LANG:-en}"
readonly OUTPUT_DIR="data/raw/${LANG}"
readonly TEMP_DIR="${OUTPUT_DIR}/freq_temp"
readonly OUTPUT_FILE="${OUTPUT_DIR}/${LANG}_50k.txt"
readonly SOURCE_FILE="${OUTPUT_DIR}/frequency.SOURCE.json"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Fetching word frequency list (OpenSubtitles 2018)..."
echo "  Repository: $FREQ_REPO"

# Check if file already exists
if [[ -f "$OUTPUT_FILE" ]] && [[ -f "$SOURCE_FILE" ]]; then
    echo "  ℹ Frequency list already exists"
    echo "  Skipping download (delete $OUTPUT_FILE to re-download)"
    echo "✓ Using existing frequency data"
    exit 0
fi

# Clone repository (shallow clone to save bandwidth)
if [[ -d "$TEMP_DIR" ]]; then
    echo "  Removing stale temp directory..."
    rm -rf "$TEMP_DIR"
fi

echo "  Cloning repository..."
# Use --progress to show download progress (helpful for debugging hangs)
if ! git clone --depth 1 --progress "$FREQ_REPO" "$TEMP_DIR"; then
    echo "Error: git clone failed"
    echo "  This may be due to network issues or the repository being unavailable."
    echo "  Cleaning up..."
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo "  Clone completed successfully."

# Find the English frequency file
# Try different possible paths
FREQ_FILE=""
for path in \
    "$TEMP_DIR/content/2018/en/en_50k.txt" \
    "$TEMP_DIR/content/2016/en/en_50k.txt" \
    "$TEMP_DIR/en_50k.txt" \
    "$TEMP_DIR/en/en_50k.txt"; do
    if [[ -f "$path" ]]; then
        FREQ_FILE="$path"
        break
    fi
done

# If not found, try to find any en_*.txt file
if [[ -z "$FREQ_FILE" ]]; then
    FREQ_FILE=$(find "$TEMP_DIR" -name "en_*.txt" -type f | head -n 1)
fi

if [[ -z "$FREQ_FILE" ]] || [[ ! -f "$FREQ_FILE" ]]; then
    echo "Error: Could not find English frequency list in repository"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Copy to output location
cp "$FREQ_FILE" "$OUTPUT_FILE"

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

# Count entries (each line has word + frequency)
ENTRY_COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')

# Get git commit hash for provenance
cd "$TEMP_DIR"
GIT_COMMIT=$(git rev-parse HEAD)
cd - > /dev/null

# Get file size
FILE_SIZE=$(stat -c %s "$OUTPUT_FILE" 2>/dev/null || stat -f %z "$OUTPUT_FILE" 2>/dev/null || echo 0)
FILE_SIZE_KB=$(( FILE_SIZE / 1024 ))

# Cleanup temp directory
rm -rf "$TEMP_DIR"

# Create SOURCE.json with metadata
cat > "$SOURCE_FILE" <<EOF
{
  "name": "FrequencyWords",
  "title": "OpenSubtitles 2018 English Word Frequency List",
  "author": "Hermit Dave (compiled from OpenSubtitles.org data)",
  "url": "$FREQ_REPO",
  "git_commit": "$GIT_COMMIT",
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
  "attribution": "Word frequency data compiled from OpenSubtitles.org (https://www.opensubtitles.org/). Licensed under CC BY-SA 4.0.",
  "sha256": "$CHECKSUM",
  "entry_count": $ENTRY_COUNT,
  "file_size_bytes": $FILE_SIZE,
  "format": "text/plain",
  "encoding": "UTF-8",
  "notes": "Each line contains: word<space>frequency. Based on movie/TV subtitles corpus.",
  "downloaded_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "✓ Frequency list fetched: $ENTRY_COUNT entries (${FILE_SIZE_KB} KB)"
echo "  File: $OUTPUT_FILE"
echo "  SHA256: $CHECKSUM"
