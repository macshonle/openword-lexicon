#!/bin/bash
# Benchmark script for testing parallel processing strategies
# Usage: ./benchmark.sh [input_file] [output_dir]

set -e

# Configuration
INPUT_FILE="${1:-../../data/enwiktionary-latest-pages-articles.xml.bz2}"
OUTPUT_DIR="${2:-./benchmark_results}"
THREADS="${THREADS:-0}"  # 0 = auto-detect

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build release binary if needed
echo "Building release binary..."
cargo build --release

BINARY="./target/release/wiktionary-rust"

# Check if input exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Input file not found: $INPUT_FILE"
    echo "Generating synthetic test data..."
    python3 scripts/generate_synthetic_data.py --medium -o "$OUTPUT_DIR/synthetic_medium.xml.bz2"
    INPUT_FILE="$OUTPUT_DIR/synthetic_medium.xml.bz2"
fi

echo ""
echo "=========================================="
echo "BENCHMARK CONFIGURATION"
echo "=========================================="
echo "Input: $INPUT_FILE"
echo "Output directory: $OUTPUT_DIR"
echo "Threads: ${THREADS:-auto}"
echo ""

# Run built-in benchmark mode
echo "Running comprehensive benchmark..."
$BINARY "$INPUT_FILE" "$OUTPUT_DIR/output.jsonl" --benchmark -t "$THREADS"

echo ""
echo "=========================================="
echo "INDIVIDUAL STRATEGY TESTS"
echo "=========================================="

# Test each strategy individually with timing
strategies=("sequential" "batch-parallel" "channel-pipeline" "two-phase")

for strategy in "${strategies[@]}"; do
    echo ""
    echo "Testing $strategy..."
    output_file="$OUTPUT_DIR/output_${strategy}.jsonl"

    time $BINARY "$INPUT_FILE" "$output_file" -s "$strategy" -t "$THREADS" -q

    # Count output lines
    lines=$(wc -l < "$output_file")
    echo "Output: $lines entries"
done

echo ""
echo "=========================================="
echo "BATCH SIZE COMPARISON (batch-parallel)"
echo "=========================================="

batch_sizes=(100 500 1000 2000 5000)
for batch_size in "${batch_sizes[@]}"; do
    echo ""
    echo "Batch size: $batch_size"
    time $BINARY "$INPUT_FILE" "$OUTPUT_DIR/output_batch_${batch_size}.jsonl" \
        -s batch-parallel --batch-size "$batch_size" -t "$THREADS" -q
done

echo ""
echo "=========================================="
echo "THREAD COUNT COMPARISON"
echo "=========================================="

for num_threads in 1 2 4 8; do
    echo ""
    echo "Threads: $num_threads"
    time $BINARY "$INPUT_FILE" "$OUTPUT_DIR/output_threads_${num_threads}.jsonl" \
        -s batch-parallel -t "$num_threads" -q
done

echo ""
echo "=========================================="
echo "BENCHMARK COMPLETE"
echo "=========================================="
echo "Results saved to: $OUTPUT_DIR"
