#!/usr/bin/env bash
# run_wordnet_tests.sh - Run WordNet enrichment tests with detailed output
#
# Usage:
#   bash tests/run_wordnet_tests.sh
#
# Output:
#   - tests/wordnet_test_results.txt (human-readable)
#   - tests/wordnet_test_detailed_results.json (machine-readable)
#   - Console output (verbose)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "==================================="
echo "WordNet Enrichment Test Suite"
echo "==================================="
echo ""
echo "Running comprehensive tests for:"
echo "  - NLTK-based WordNet enrichment (current)"
echo "  - Edge cases and bug detection"
echo "  - Baseline behavior documentation"
echo ""
echo "Test outputs:"
echo "  - tests/wordnet_test_results.txt"
echo "  - tests/wordnet_test_detailed_results.json"
echo ""

# Ensure test results directory exists
mkdir -p tests/

# Run tests with detailed output
echo "Starting test run..."
echo ""

# Run pytest with verbose output and capture to file
uv run pytest tests/test_wordnet_enrichment.py \
    -v \
    --tb=long \
    --color=yes \
    --capture=no \
    2>&1 | tee tests/wordnet_test_results.txt

echo ""
echo "==================================="
echo "Test run complete!"
echo ""

if [ -f tests/wordnet_test_results.txt ]; then
    echo "✓ Human-readable results: tests/wordnet_test_results.txt"
fi

if [ -f tests/wordnet_test_detailed_results.json ]; then
    echo "✓ JSON results: tests/wordnet_test_detailed_results.json"
fi

echo ""
echo "Review results and commit to version control if appropriate."
echo "==================================="
