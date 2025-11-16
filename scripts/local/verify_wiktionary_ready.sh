#!/usr/bin/env bash
# verify_wiktionary_ready.sh - Verify Wiktionary data is ready for build
#
# Run this script to check if Wiktionary data has been properly integrated
# and is ready for the build pipeline.
#
# Usage:
#   bash scripts/local/verify_wiktionary_ready.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Wiktionary Integration Verification                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

LANG="${LEXICON_LANG:-en}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WIKT_JSONL="${PROJECT_ROOT}/data/intermediate/${LANG}/wikt.jsonl"

CHECKS_PASSED=0
CHECKS_FAILED=0

# Helper functions
check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

# Check 1: File exists
echo -e "${YELLOW}Checking Wiktionary data file...${NC}"
if [[ -f "${WIKT_JSONL}" ]]; then
    check_pass "File exists: ${WIKT_JSONL}"

    # Get file size
    SIZE=$(du -h "${WIKT_JSONL}" | cut -f1)
    echo "     Size: ${SIZE}"

    # Count entries
    ENTRY_COUNT=$(wc -l < "${WIKT_JSONL}" | tr -d ' ')
    echo "     Entries: ${ENTRY_COUNT}"

    if [[ ${ENTRY_COUNT} -gt 100000 ]]; then
        check_pass "Entry count looks good (${ENTRY_COUNT} entries)"
    elif [[ ${ENTRY_COUNT} -gt 10000 ]]; then
        check_warn "Entry count seems low (${ENTRY_COUNT} entries)"
        echo "     Expected: 500k-800k for full Wiktionary"
    else
        check_fail "Entry count too low (${ENTRY_COUNT} entries)"
        echo "     Expected: 500k-800k for full Wiktionary"
    fi
else
    check_fail "File not found: ${WIKT_JSONL}"
    echo ""
    echo "  ${YELLOW}To fix:${NC}"
    echo "    1. Run: bash scripts/local/process_wiktionary_local.sh"
    echo "    2. Or copy from local: scp local_path/wikt.jsonl ${WIKT_JSONL}"
    echo ""
    exit 1
fi
echo ""

# Check 2: File format (valid JSON lines)
echo -e "${YELLOW}Checking file format...${NC}"
SAMPLE_LINES=10
VALID_JSON=0

for i in $(seq 1 ${SAMPLE_LINES}); do
    LINE=$(sed -n "${i}p" "${WIKT_JSONL}")
    if echo "${LINE}" | jq . > /dev/null 2>&1; then
        ((VALID_JSON++))
    fi
done

if [[ ${VALID_JSON} -eq ${SAMPLE_LINES} ]]; then
    check_pass "File format valid (checked ${SAMPLE_LINES} lines)"
else
    check_fail "Invalid JSON format (${VALID_JSON}/${SAMPLE_LINES} lines valid)"
fi
echo ""

# Check 3: Syllable data
echo -e "${YELLOW}Checking syllable data...${NC}"
SYLLABLE_COUNT=$(grep -c '"syllables"' "${WIKT_JSONL}" || true)
if [[ ${SYLLABLE_COUNT} -gt 0 ]]; then
    SYLLABLE_PCT=$((SYLLABLE_COUNT * 100 / ENTRY_COUNT))
    check_pass "Syllable data found: ${SYLLABLE_COUNT} entries (${SYLLABLE_PCT}%)"

    if [[ ${SYLLABLE_PCT} -ge 30 ]]; then
        check_pass "Syllable coverage looks good (${SYLLABLE_PCT}%)"
    else
        check_warn "Syllable coverage lower than expected (${SYLLABLE_PCT}%, expected 30-50%)"
    fi
else
    check_fail "No syllable data found"
    echo "     This is unexpected. Check scanner parser configuration."
fi
echo ""

# Check 4: Label data
echo -e "${YELLOW}Checking label data...${NC}"
LABEL_COUNT=$(grep -c '"labels"' "${WIKT_JSONL}" || true)
if [[ ${LABEL_COUNT} -gt 0 ]]; then
    LABEL_PCT=$((LABEL_COUNT * 100 / ENTRY_COUNT))
    check_pass "Label data found: ${LABEL_COUNT} entries (${LABEL_PCT}%)"

    if [[ ${LABEL_PCT} -ge 40 ]]; then
        check_pass "Label coverage looks good (${LABEL_PCT}%)"
    else
        check_warn "Label coverage lower than expected (${LABEL_PCT}%, expected 60-80%)"
    fi
else
    check_warn "No label data found"
    echo "     Labels may be optional, but coverage should be higher."
fi
echo ""

# Check 5: Sample entry structure
echo -e "${YELLOW}Checking entry structure...${NC}"
FIRST_ENTRY=$(head -n 1 "${WIKT_JSONL}")

# Check for required fields
HAS_WORD=$(echo "${FIRST_ENTRY}" | jq 'has("word")' 2>/dev/null || echo "false")
HAS_POS=$(echo "${FIRST_ENTRY}" | jq 'has("pos")' 2>/dev/null || echo "false")
HAS_SOURCES=$(echo "${FIRST_ENTRY}" | jq 'has("sources")' 2>/dev/null || echo "false")

if [[ "${HAS_WORD}" == "true" ]]; then
    check_pass "Has 'word' field"
else
    check_fail "Missing 'word' field"
fi

if [[ "${HAS_POS}" == "true" ]]; then
    check_pass "Has 'pos' field"
else
    check_warn "Missing 'pos' field (may be filled during enrichment)"
fi

if [[ "${HAS_SOURCES}" == "true" ]]; then
    check_pass "Has 'sources' field"
else
    check_fail "Missing 'sources' field"
fi
echo ""

# Check 6: POS tag variety
echo -e "${YELLOW}Checking POS tag variety...${NC}"
if command -v jq &> /dev/null; then
    POS_COUNT=$(jq -r '.pos[]?' "${WIKT_JSONL}" 2>/dev/null | sort -u | wc -l || echo "0")
    if [[ ${POS_COUNT} -gt 5 ]]; then
        check_pass "Found ${POS_COUNT} different POS tags"
        echo "     Top 5 POS tags:"
        jq -r '.pos[]?' "${WIKT_JSONL}" 2>/dev/null | sort | uniq -c | sort -rn | head -5 | while read count pos; do
            echo "       - ${pos}: ${count}"
        done
    else
        check_warn "Only found ${POS_COUNT} different POS tags (expected 10+)"
    fi
else
    check_warn "jq not installed, skipping POS variety check"
fi
echo ""

# Summary
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Verification Summary:${NC}"
echo ""
echo "  ${GREEN}✓ Passed:${NC} ${CHECKS_PASSED}"
echo "  ${RED}✗ Failed:${NC} ${CHECKS_FAILED}"
echo ""

if [[ ${CHECKS_FAILED} -eq 0 ]]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  All checks passed! Wiktionary data is ready.             ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Rebuild the lexicon with Wiktionary data:"
    echo "     ${BLUE}make build-en${NC}"
    echo ""
    echo "  2. Check the updated report for syllable coverage:"
    echo "     ${BLUE}make report-en${NC}"
    echo "     ${BLUE}grep -A 5 'Syllable Analysis' reports/metadata_analysis_en.md${NC}"
    echo ""
    echo "  Expected improvements:"
    echo "    • Total words: 208k → 800k-1.2M"
    echo "    • Syllable coverage: 0% → 30-50%"
    echo "    • Label coverage: 0% → 60-80%"
    echo "    • Multi-word phrases: many more"
    echo ""
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  Some checks failed. Review errors above.                 ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Common fixes:${NC}"
    echo "  • File missing: Run ${BLUE}bash scripts/local/process_wiktionary_local.sh${NC}"
    echo "  • Low entry count: Re-download and reprocess"
    echo "  • No syllables: Check scanner parser output"
    echo ""
    exit 1
fi
