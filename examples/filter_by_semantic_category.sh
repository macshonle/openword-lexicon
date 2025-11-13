#!/usr/bin/env bash
# Example: Filter words by WordNet semantic category
#
# This script demonstrates how to extract words from specific semantic
# categories (e.g., all animal words, all food words) using WordNet
# concreteness classification.
#
# Note: This requires adding wordnet_lexname to the enrichment pipeline
# (not yet implemented). For now, this shows the intended approach.
#
# Requirements:
# - Built core distribution with WordNet enrichment
# - jq (JSON processor)

set -euo pipefail

# Configuration
ENRICHED_JSONL="data/intermediate/core/core_entries_enriched.jsonl"

# Available semantic categories from WordNet:
# - noun.animal: Animals
# - noun.artifact: Man-made objects
# - noun.body: Body parts
# - noun.food: Food and drink
# - noun.plant: Plants
# - noun.substance: Substances and materials
# - noun.object: Natural objects
# Plus 15+ abstract categories

CATEGORY="${1:-}"

if [[ -z "$CATEGORY" ]]; then
    echo "Usage: $0 <category>"
    echo ""
    echo "Available categories:"
    echo "  Concrete (good for kids):"
    echo "    noun.animal     - Animals (e.g., cat, dog, elephant)"
    echo "    noun.artifact   - Objects (e.g., table, car, toy)"
    echo "    noun.body       - Body parts (e.g., hand, eye, head)"
    echo "    noun.food       - Food/drink (e.g., apple, milk, bread)"
    echo "    noun.plant      - Plants (e.g., tree, flower, grass)"
    echo "    noun.substance  - Materials (e.g., water, wood, metal)"
    echo "    noun.object     - Natural objects (e.g., rock, star, cloud)"
    echo ""
    echo "  Abstract:"
    echo "    noun.cognition  - Mental concepts (e.g., idea, thought, theory)"
    echo "    noun.feeling    - Emotions (e.g., love, anger, joy)"
    echo "    noun.attribute  - Properties (e.g., size, color, speed)"
    echo "    noun.act        - Actions (e.g., movement, creation)"
    echo "    noun.time       - Time concepts (e.g., hour, year, moment)"
    echo ""
    echo "Example: $0 noun.animal"
    exit 1
fi

OUTPUT_FILE="${CATEGORY//./_}_words.txt"

echo "Filtering words in category: $CATEGORY"
echo ""

# Check if input file exists
if [[ ! -f "$ENRICHED_JSONL" ]]; then
    echo "Error: Input file not found: $ENRICHED_JSONL"
    echo "Please run 'make build-core' first."
    exit 1
fi

# NOTE: This assumes wordnet_lexname field exists in entries
# Currently NOT implemented - would need to add to wordnet_enrich.py

# Check if wordnet_lexname field exists
if ! jq -e 'select(has("wordnet_lexname"))' "$ENRICHED_JSONL" | head -1 > /dev/null 2>&1; then
    echo "⚠️  WARNING: wordnet_lexname field not found in entries"
    echo ""
    echo "This field is not yet implemented. To add it:"
    echo ""
    echo "1. Update src/openword/wordnet_enrich.py to add wordnet_lexname field"
    echo "2. Rebuild the lexicon: make clean-build && make build-core"
    echo ""
    echo "For now, using concreteness field as a fallback..."
    echo "(This is less precise but shows concrete vs abstract filtering)"
    echo ""

    # Fallback: Use concreteness field
    if [[ "$CATEGORY" =~ ^noun\.(animal|artifact|body|food|plant|substance|object)$ ]]; then
        echo "Filtering concrete nouns (approximate category match)..."
        jq -r 'select(
            (.pos | contains(["noun"])) and
            .concreteness == "concrete" and
            .is_phrase == false
        ) | .word' "$ENRICHED_JSONL" | sort -u > "$OUTPUT_FILE"
    else
        echo "Filtering abstract nouns (approximate category match)..."
        jq -r 'select(
            (.pos | contains(["noun"])) and
            .concreteness == "abstract" and
            .is_phrase == false
        ) | .word' "$ENRICHED_JSONL" | sort -u > "$OUTPUT_FILE"
    fi

    WORD_COUNT=$(wc -l < "$OUTPUT_FILE")
    echo "✓ Filtered $WORD_COUNT words (approximate)"
    echo "✓ Output: $OUTPUT_FILE"
    echo ""
    echo "Note: This is using broad concreteness classification."
    echo "      For precise category filtering, implement wordnet_lexname field."
    exit 0
fi

# If wordnet_lexname exists, use it for precise filtering
echo "Filtering words with lexname: $CATEGORY"
jq -r "select(
    .wordnet_lexname == \"$CATEGORY\" and
    .is_phrase == false
) | .word" "$ENRICHED_JSONL" | sort -u > "$OUTPUT_FILE"

WORD_COUNT=$(wc -l < "$OUTPUT_FILE")

echo "✓ Filtered $WORD_COUNT words"
echo "✓ Output: $OUTPUT_FILE"
echo ""
echo "Sample words:"
head -20 "$OUTPUT_FILE"

echo ""
echo "---"
echo "To review all words: cat $OUTPUT_FILE"
echo ""
echo "To combine multiple categories:"
echo "  ./$(basename "$0") noun.animal > animals.txt"
echo "  ./$(basename "$0") noun.food > food.txt"
echo "  cat animals.txt food.txt | sort -u > animals_and_food.txt"
