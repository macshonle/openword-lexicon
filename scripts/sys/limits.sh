#!/usr/bin/env bash
# limits.sh — Track download sizes and peak RSS to enforce project constraints
# Constraints: total downloads ≤ 100 GB, peak RAM per step ≤ 2 GB

set -euo pipefail

# Configuration
readonly MAX_DOWNLOAD_BYTES=$((100 * 1024 * 1024 * 1024))  # 100 GB
readonly MAX_RAM_KB=$((2 * 1024 * 1024))                    # 2 GB in KB
readonly DATA_DIR="${DATA_DIR:-data/raw}"
readonly LOG_FILE="${LOG_FILE:-data/.limits-log.json}"

# Initialize log file if it doesn't exist
init_log() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo '{"steps":[],"total_downloads_bytes":0}' > "$LOG_FILE"
    fi
}

# Get current total download size (bytes)
get_download_size() {
    if [[ -d "$DATA_DIR" ]]; then
        du -sb "$DATA_DIR" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

# Update log with current download size
update_download_log() {
    local current_size
    current_size=$(get_download_size)

    # Use Python to update JSON (since jq may not be available)
    python3 -c "
import json
import sys

try:
    with open('$LOG_FILE', 'r') as f:
        data = json.load(f)
except:
    data = {'steps': [], 'total_downloads_bytes': 0}

data['total_downloads_bytes'] = $current_size

with open('$LOG_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
}

# Run a command with memory tracking via /usr/bin/time
run_with_memory_tracking() {
    local step_name="$1"
    shift
    local cmd=("$@")

    local time_output
    time_output=$(mktemp)

    echo "→ Running: $step_name"

    # Run with /usr/bin/time to capture memory stats
    if /usr/bin/time -v "${cmd[@]}" 2>"$time_output"; then
        # Extract peak RSS in KB
        local peak_rss_kb
        peak_rss_kb=$(grep "Maximum resident set size" "$time_output" | awk '{print $6}' || echo "0")

        # Log the step
        log_step "$step_name" "$peak_rss_kb" "success"

        rm -f "$time_output"
        return 0
    else
        local exit_code=$?
        log_step "$step_name" "0" "failed"
        rm -f "$time_output"
        return $exit_code
    fi
}

# Log a step with its memory usage
log_step() {
    local step_name="$1"
    local peak_rss_kb="$2"
    local status="$3"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    python3 -c "
import json

try:
    with open('$LOG_FILE', 'r') as f:
        data = json.load(f)
except:
    data = {'steps': [], 'total_downloads_bytes': 0}

step_data = {
    'name': '$step_name',
    'timestamp': '$timestamp',
    'peak_rss_kb': $peak_rss_kb,
    'status': '$status'
}

data['steps'].append(step_data)

with open('$LOG_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
}

# Check if limits are exceeded
check_limits() {
    init_log
    update_download_log

    local total_bytes
    local violations=0

    # Read current totals
    total_bytes=$(python3 -c "
import json
with open('$LOG_FILE', 'r') as f:
    data = json.load(f)
print(data.get('total_downloads_bytes', 0))
")

    echo "═══════════════════════════════════════════════════"
    echo "  OPENWORD LEXICON - RESOURCE LIMITS CHECK"
    echo "═══════════════════════════════════════════════════"
    echo ""

    # Check download size
    local total_gb
    total_gb=$(python3 -c "print(f'{$total_bytes / (1024**3):.2f}')")
    echo "📥 Total downloads: ${total_gb} GB / 100 GB"

    if (( total_bytes > MAX_DOWNLOAD_BYTES )); then
        echo "   ❌ VIOLATION: Download size exceeds 100 GB limit!"
        violations=$((violations + 1))
    else
        echo "   ✓ Within limit"
    fi

    echo ""

    # Check peak RAM for each step
    echo "💾 Peak RAM usage by step:"

    python3 -c "
import json

with open('$LOG_FILE', 'r') as f:
    data = json.load(f)

violations = 0
max_ram_kb = $MAX_RAM_KB

for step in data.get('steps', []):
    name = step.get('name', 'unknown')
    peak_kb = step.get('peak_rss_kb', 0)
    status = step.get('status', 'unknown')
    peak_mb = peak_kb / 1024

    status_icon = '✓' if status == 'success' else '✗'

    print(f'   {status_icon} {name}: {peak_mb:.0f} MB', end='')

    if peak_kb > max_ram_kb:
        print(f' ❌ VIOLATION (exceeds 2 GB limit!)')
        violations += 1
    else:
        print(f' (OK)')

exit(violations)
" || violations=$((violations + $?))

    echo ""
    echo "═══════════════════════════════════════════════════"

    if (( violations > 0 )); then
        echo "❌ FAILED: $violations limit violation(s) detected"
        echo "═══════════════════════════════════════════════════"
        return 1
    else
        echo "✅ PASSED: All resource limits satisfied"
        echo "═══════════════════════════════════════════════════"
        return 0
    fi
}

# Reset logs (for testing)
reset_logs() {
    rm -f "$LOG_FILE"
    init_log
    echo "✓ Logs reset"
}

# Main command dispatcher
main() {
    local cmd="${1:-check}"

    case "$cmd" in
        check)
            check_limits
            ;;
        track)
            shift
            if [[ $# -lt 2 ]]; then
                echo "Usage: $0 track <step-name> <command...>"
                exit 1
            fi
            run_with_memory_tracking "$@"
            ;;
        update)
            update_download_log
            echo "✓ Download log updated"
            ;;
        reset)
            reset_logs
            ;;
        init)
            init_log
            echo "✓ Log initialized"
            ;;
        *)
            echo "Usage: $0 {check|track|update|reset|init}"
            echo ""
            echo "Commands:"
            echo "  check          - Check if limits are exceeded (exit 1 if violated)"
            echo "  track <name> <cmd...> - Run command with memory tracking"
            echo "  update         - Update download size log"
            echo "  reset          - Reset logs (for testing)"
            echo "  init           - Initialize log file"
            exit 1
            ;;
    esac
}

main "$@"
