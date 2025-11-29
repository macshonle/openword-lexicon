#!/usr/bin/env bash
# Example: Filter kids-appropriate vocabulary from the lexicon
#
# This script demonstrates how to create a word list suitable for
# children's educational apps or games by combining multiple filters.
#
# Requirements:
# - Built lexicon (make build-en)
# - jq (JSON processor)

set -euo pipefail

# Configuration
ENRICHED_JSONL="data/intermediate/en-lexemes-enriched.jsonl"
OUTPUT_FILE="kids_vocabulary.txt"

# Filtering criteria for kids' vocabulary:
# - Only nouns (easier to visualize/understand)
# - Concrete (physical objects)
# - Common words (frequency tier ≤ G, roughly top ~5,000)
# - Short words (3-10 characters, easier to read/spell)
# - No phrases (single words only)
# - Family-friendly (no vulgar/offensive labels)
# - Not archaic or obsolete

echo "Filtering kids-appropriate vocabulary..."
echo ""
echo "Criteria:"
echo "  - Part of speech: noun"
echo "  - Concreteness: concrete"
echo "  - Frequency tier: A-G (top ~5,000 words)"
echo "  - Word length: 3-10 characters"
echo "  - Single words only (no phrases)"
echo "  - Family-friendly (no vulgar/offensive)"
echo "  - Modern (not archaic/obsolete)"
echo ""

# Check if input file exists
if [[ ! -f "$ENRICHED_JSONL" ]]; then
    echo "Error: Input file not found: $ENRICHED_JSONL"
    echo "Please run 'make build-en' first to generate enriched entries."
    exit 1
fi

# Filter using jq
# Frequency tiers: A (ranks 1-20) → B (21-100) → ... → G (3001-5000) → ... → L → Y → Z
# String comparison works: "A" < "B" < ... < "G" < ... < "Z"
# Tier G covers up to approximately rank 5,000 - good for children's vocabulary
jq -r 'select(
    # Must be a noun (check senses or pos field)
    ((.pos // []) | any(. == "noun")) and

    # Must be concrete (not abstract)
    .concreteness == "concrete" and

    # Must be in common frequency range (A through G, where A is most common)
    ((.frequency_tier // "Z") <= "G") and

    # Single word only (no phrases)
    (.is_phrase // false) == false and

    # Only alphabetic characters (no numbers, hyphens, apostrophes)
    (.word | test("^[a-z]+$")) and

    # Word length 3-10 characters
    (.word | length >= 3 and length <= 10) and

    # No vulgar/offensive labels
    ((.labels.register // []) | any(. == "vulgar" or . == "offensive") | not) and

    # No archaic/obsolete labels
    ((.labels.temporal // []) | any(. == "archaic" or . == "obsolete") | not)
) | .word' "$ENRICHED_JSONL" | sort -u > "$OUTPUT_FILE"

# Count results
WORD_COUNT=$(wc -l < "$OUTPUT_FILE")

echo "✓ Filtered $WORD_COUNT words"
echo "✓ Output: $OUTPUT_FILE"
echo ""
echo "Sample words:"
head -20 "$OUTPUT_FILE"

echo ""
echo "---"
echo "To review all words: cat $OUTPUT_FILE"
echo "To count by length: awk '{print length}' $OUTPUT_FILE | sort -n | uniq -c"
