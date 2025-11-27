#!/bin/bash
# fetch_profanity_lists.sh — Fetch profanity word lists for validation
#
# ⚠️  WARNING: Contains offensive and explicit content ⚠️
# These lists are for validation purposes only - not part of main lexicon build.
# They help verify that our lexicon's vulgar/offensive labels are comprehensive.
#
# Sources:
#   1. censor-text/profanity-list (open source, maintained)
#   2. dsojevic/profanity-list (severity ratings + metadata)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
RAW_DIR="$DATA_DIR/raw/validation"
PROFANITY_DIR="$RAW_DIR/profanity"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}⚠️  WARNING: PROFANITY WORD LISTS - EXPLICIT CONTENT  ⚠️${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}This script downloads word lists containing profanity, slurs, and${NC}"
echo -e "${YELLOW}offensive language. These are used ONLY for validation to ensure${NC}"
echo -e "${YELLOW}our lexicon properly labels vulgar/offensive terms.${NC}"
echo ""
echo -e "${YELLOW}These lists are NOT part of the main lexicon build.${NC}"
echo ""
if [ "${OPENWORD_CI:-}" = "1" ] || [ "${CI:-}" = "true" ]; then
    echo -e "${YELLOW}CI mode: Auto-confirming profanity list download${NC}"
else
    echo -e "${RED}Press Ctrl+C now to cancel, or Enter to continue...${NC}"
    read -r
fi

echo ""
echo "Creating validation directory..."
mkdir -p "$PROFANITY_DIR"

cd "$PROFANITY_DIR"

# Fetch censor-text/profanity-list
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fetching censor-text/profanity-list..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CENSOR_TEXT_URL="https://raw.githubusercontent.com/censor-text/profanity-list/main/list/en.txt"
CENSOR_TEXT_FILE="censor-text-profanity-list.txt"

if [ -f "$CENSOR_TEXT_FILE" ]; then
    echo "✓ Already exists: $CENSOR_TEXT_FILE"
else
    echo "Downloading from: $CENSOR_TEXT_URL"
    if curl -fSL "$CENSOR_TEXT_URL" -o "$CENSOR_TEXT_FILE"; then
        echo -e "${GREEN}✓ Downloaded: $CENSOR_TEXT_FILE${NC}"
        wc -l "$CENSOR_TEXT_FILE"
    else
        echo -e "${RED}✗ Failed to download censor-text list${NC}"
        echo "  Note: Repository was archived November 2024"
        echo "  URL may have changed or network issue"
    fi
fi

# Fetch dsojevic/profanity-list (JSON with severity ratings)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fetching dsojevic/profanity-list (severity ratings)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DSOJEVIC_URL="https://raw.githubusercontent.com/dsojevic/profanity-list/main/en.json"
DSOJEVIC_FILE="dsojevic-profanity-list.json"

if [ -f "$DSOJEVIC_FILE" ]; then
    echo "✓ Already exists: $DSOJEVIC_FILE"
else
    echo "Downloading from: $DSOJEVIC_URL"
    if curl -fSL "$DSOJEVIC_URL" -o "$DSOJEVIC_FILE"; then
        echo -e "${GREEN}✓ Downloaded: $DSOJEVIC_FILE${NC}"
        # Count entries in JSON (rough estimate)
        if command -v jq &> /dev/null; then
            echo "Entries: $(jq 'length' "$DSOJEVIC_FILE")"
        fi
    else
        echo -e "${RED}✗ Failed to download dsojevic list${NC}"
        echo "  URL may have changed or network issue"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✓ Profanity lists fetch complete${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Files saved to: $PROFANITY_DIR"
echo ""
echo "Next step: Run validation"
echo "  make validate-profanity"
echo ""
