#!/bin/bash
# Benchmark script for comparing parallel processing strategies
#
# Usage: ./scripts/benchmark.sh [INPUT_FILE] [LIMIT]
#
# Examples:
#   ./scripts/benchmark.sh                    # Use default Wiktionary dump, 10000 entries
#   ./scripts/benchmark.sh input.xml.bz2      # Custom input, 10000 entries
#   ./scripts/benchmark.sh input.xml.bz2 5000 # Custom input and limit

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCANNER="${SCRIPT_DIR}/../target/release/wiktionary-rust"

# Default input file
DEFAULT_INPUT="${SCRIPT_DIR}/../../../data/raw/en/enwiktionary-latest-pages-articles.xml.bz2"
INPUT="${1:-$DEFAULT_INPUT}"
LIMIT="${2:-10000}"

# Output directory for test files
OUTPUT_DIR="/tmp/wikt-benchmark"
mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "Wiktionary Rust Scanner Benchmark"
echo "=============================================="
echo "Input: $INPUT"
echo "Limit: $LIMIT entries"
echo "Output dir: $OUTPUT_DIR"
echo ""

# Check if scanner exists
if [ ! -f "$SCANNER" ]; then
    echo "Error: Scanner not found at $SCANNER"
    echo "Run 'cargo build --release' first"
    exit 1
fi

# Check if input exists
if [ ! -f "$INPUT" ]; then
    echo "Error: Input file not found at $INPUT"
    exit 1
fi

STRATEGIES=("sequential" "batch-parallel" "channel-pipeline" "two-phase")

echo "Running benchmarks..."
echo ""

for strategy in "${STRATEGIES[@]}"; do
    output_file="$OUTPUT_DIR/output-${strategy}.jsonl"
    echo "Strategy: $strategy"
    echo "-------------------------------------------"

    # Run the scanner
    "$SCANNER" "$INPUT" "$output_file" \
        --strategy "$strategy" \
        --limit "$LIMIT" \
        2>&1 | grep -E "^(Strategy:|Pages processed:|Senses written:|Time:|Rate:)"

    # Count output lines
    lines=$(wc -l < "$output_file" | tr -d ' ')
    echo "Output lines: $lines"
    echo ""
done

echo "=============================================="
echo "Benchmark complete!"
echo "Output files in: $OUTPUT_DIR"
echo "=============================================="
