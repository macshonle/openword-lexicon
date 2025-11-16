#!/usr/bin/env bash
# Example: Create a profanity blocklist from Wiktionary labels
#
# This script demonstrates how to extract words flagged as vulgar,
# offensive, or derogatory for use in content filtering systems.
#
# Requirements:
# - Built plus distribution (make build-plus) OR
# - Extracted Wiktionary JSONL (make build-wiktionary-json)
# - jq (JSON processor)

set -euo pipefail

# Configuration
WIKT_JSONL="data/intermediate/plus/wikt_entries.jsonl"
OUTPUT_FILE="profanity_blocklist.txt"

echo "Creating profanity blocklist from Wiktionary labels..."
echo ""
echo "Extracting words with labels:"
echo "  - register: vulgar"
echo "  - register: offensive"
echo "  - register: derogatory"
echo ""

# Check if input file exists
if [[ ! -f "$WIKT_JSONL" ]]; then
    echo "Error: Input file not found: $WIKT_JSONL"
    echo ""
    echo "Please run one of:"
    echo "  make build-plus              # Full build (slower)"
    echo "  make build-wiktionary-json   # Just extract Wiktionary"
    exit 1
fi

# Extract words with problematic register labels
jq -r 'select(
    (.labels.register // []) |
    (contains(["vulgar"]) or contains(["offensive"]) or contains(["derogatory"]))
) | .word' "$WIKT_JSONL" | sort -u > "$OUTPUT_FILE"

# Count results
WORD_COUNT=$(wc -l < "$OUTPUT_FILE")

echo "✓ Extracted $WORD_COUNT words"
echo "✓ Output: $OUTPUT_FILE"
echo ""

# Show breakdown by label type
echo "Breakdown by label type:"
echo ""

echo -n "Vulgar:     "
jq -r 'select((.labels.register // []) | contains(["vulgar"])) | .word' "$WIKT_JSONL" | wc -l

echo -n "Offensive:  "
jq -r 'select((.labels.register // []) | contains(["offensive"])) | .word' "$WIKT_JSONL" | wc -l

echo -n "Derogatory: "
jq -r 'select((.labels.register // []) | contains(["derogatory"])) | .word' "$WIKT_JSONL" | wc -l

echo ""
echo "Sample words (first 10):"
head -10 "$OUTPUT_FILE"

echo ""
echo "---"
echo "⚠️  IMPORTANT NOTES:"
echo ""
echo "1. Label coverage is ~11.2% of Wiktionary entries"
echo "   Some inappropriate words may not be labeled"
echo ""
echo "2. Context matters - some words are offensive in some uses but not others"
echo "   Manual review is recommended for high-sensitivity applications"
echo ""
echo "3. Consider combining with external blocklists for better coverage:"
echo "   - List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words"
echo "   - Google's banned words list"
echo "   - Your own custom additions"
echo ""
echo "4. To create a more comprehensive blocklist:"
echo "   cat profanity_blocklist.txt external_blocklist.txt | sort -u > combined_blocklist.txt"
echo ""
echo "To review all words: cat $OUTPUT_FILE"
