#!/usr/bin/env bash
# Monitoring Topic Consolidation Validation Script
# 
# This script uses rtiddsspy to compare old vs new monitoring topics for 1:1 parity.
# It does NOT assume the new method is broken - it investigates objectively.
#
# Old Topics (5):
#   - GenesisGraphNode (durable)
#   - GenesisGraphEdge (durable)
#   - ChainEvent (volatile)
#   - ComponentLifecycleEvent (volatile)
#   - MonitoringEvent (volatile)
#
# New Topics (2):
#   - GraphTopology (durable) - consolidates Node + Edge
#   - Event (volatile) - consolidates Chain + Lifecycle + MonitoringEvent
#
# Usage: ./validate_monitoring_parity.sh [duration_seconds]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENESIS_LIB_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$GENESIS_LIB_DIR/logs"
DURATION="${1:-30}"  # Default 30 seconds capture

echo "=========================================="
echo "Monitoring Topic Consolidation Validation"
echo "=========================================="
echo "Duration: ${DURATION}s"
echo "Log Directory: $LOG_DIR"
echo ""

# Check if rtiddsspy is available
if [ -z "$NDDSHOME" ]; then
    echo "ERROR: NDDSHOME environment variable not set"
    echo "Please source your RTI Connext DDS environment"
    exit 1
fi

RTIDDSSPY="$NDDSHOME/bin/rtiddsspy"
if [ ! -f "$RTIDDSSPY" ]; then
    echo "ERROR: rtiddsspy not found at $RTIDDSSPY"
    echo "Please ensure RTI Connext DDS is installed correctly"
    exit 1
fi

# Ensure spy config exists
SPY_CONFIG="$GENESIS_LIB_DIR/spy_transient.xml"
if [ ! -f "$SPY_CONFIG" ]; then
    echo "ERROR: Spy config not found at $SPY_CONFIG"
    exit 1
fi

# Create temp directory for this run
TEMP_DIR="$LOG_DIR/validation_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR"

echo "Starting rtiddsspy capture..."
echo "Temp directory: $TEMP_DIR"
echo ""

# Start rtiddsspy in background with output to file
RTIDDSSPY_PROFILEFILE="$SPY_CONFIG" "$RTIDDSSPY" -printSample > "$TEMP_DIR/spy_raw.log" 2>&1 &
SPY_PID=$!

echo "rtiddsspy PID: $SPY_PID"
echo "Capturing DDS traffic for ${DURATION} seconds..."
sleep "$DURATION"

echo ""
echo "Stopping rtiddsspy..."
kill -TERM "$SPY_PID" 2>/dev/null || true
wait "$SPY_PID" 2>/dev/null || true
sleep 2

echo ""
echo "=========================================="
echo "Analyzing DDS Traffic"
echo "=========================================="
echo ""

# Parse rtiddsspy output to count samples per topic
parse_spy_log() {
    local log_file="$1"
    local output_file="$2"
    
    # Initialize counts
    declare -A topic_counts
    declare -A topic_writers
    
    # Parse the log file
    while IFS= read -r line; do
        # Look for topic publications (sample count lines)
        if [[ "$line" =~ Write\ sample:\ (.+)\ \(([0-9]+)\ samples\) ]]; then
            topic="${BASH_REMATCH[1]}"
            count="${BASH_REMATCH[2]}"
            topic_counts["$topic"]=$count
        fi
        # Also look for inline sample notifications
        if [[ "$line" =~ source_timestamp:.*topic:\ (.+)$ ]]; then
            topic="${BASH_REMATCH[1]}"
            ((topic_counts["$topic"]++)) || topic_counts["$topic"]=1
        fi
    done < "$log_file"
    
    # Write counts to output file
    {
        echo "# Topic Sample Counts"
        echo "# Format: TOPIC_NAME:SAMPLE_COUNT"
        for topic in "${!topic_counts[@]}"; do
            echo "$topic:${topic_counts[$topic]}"
        done
    } > "$output_file"
}

# Count actual data samples only (not writer/reader announcements)
count_topic_samples() {
    local log_file="$1"
    local topic_name="$2"
    
    # Count only "New data" and "Modified instance" lines for this topic
    local count=$(grep "rti/connext/genesis/$topic_name" "$log_file" 2>/dev/null | grep -E "New data|Modified instance" | wc -l | tr -d ' ')
    # Ensure we return a clean integer
    echo "${count:-0}"
}

echo "Counting samples per topic..."

# Old Topics
OLD_NODE_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/GenesisGraphNode")
OLD_EDGE_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/GenesisGraphEdge")
OLD_CHAIN_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/ChainEvent")
OLD_LIFECYCLE_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/ComponentLifecycleEvent")
OLD_MONITORING_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/MonitoringEvent")

# New Topics
NEW_TOPOLOGY_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/GraphTopology")
NEW_EVENT_COUNT=$(count_topic_samples "$TEMP_DIR/spy_raw.log" "monitoring/Event")

# Calculate expected parity
EXPECTED_TOPOLOGY_COUNT=$((OLD_NODE_COUNT + OLD_EDGE_COUNT))
EXPECTED_EVENT_COUNT=$((OLD_CHAIN_COUNT + OLD_LIFECYCLE_COUNT + OLD_MONITORING_COUNT))

# Save results
RESULTS_FILE="$TEMP_DIR/parity_results.txt"
{
    echo "=========================================="
    echo "Monitoring Topic Consolidation - Parity Results"
    echo "Capture Duration: ${DURATION}s"
    echo "Timestamp: $(date)"
    echo "=========================================="
    echo ""
    echo "OLD TOPICS (5):"
    echo "  GenesisGraphNode:           $OLD_NODE_COUNT samples"
    echo "  GenesisGraphEdge:           $OLD_EDGE_COUNT samples"
    echo "  ChainEvent:                 $OLD_CHAIN_COUNT samples"
    echo "  ComponentLifecycleEvent:    $OLD_LIFECYCLE_COUNT samples"
    echo "  MonitoringEvent:            $OLD_MONITORING_COUNT samples"
    echo "  ---"
    echo "  Total:                      $((OLD_NODE_COUNT + OLD_EDGE_COUNT + OLD_CHAIN_COUNT + OLD_LIFECYCLE_COUNT + OLD_MONITORING_COUNT)) samples"
    echo ""
    echo "NEW TOPICS (2):"
    echo "  GraphTopology:              $NEW_TOPOLOGY_COUNT samples"
    echo "  Event:                      $NEW_EVENT_COUNT samples"
    echo "  ---"
    echo "  Total:                      $((NEW_TOPOLOGY_COUNT + NEW_EVENT_COUNT)) samples"
    echo ""
    echo "=========================================="
    echo "PARITY ANALYSIS:"
    echo "=========================================="
    echo ""
    echo "1. GRAPH TOPOLOGY (Durable):"
    echo "   Expected: Node ($OLD_NODE_COUNT) + Edge ($OLD_EDGE_COUNT) = $EXPECTED_TOPOLOGY_COUNT"
    echo "   Actual:   $NEW_TOPOLOGY_COUNT"
    
    if [ "$NEW_TOPOLOGY_COUNT" -eq "$EXPECTED_TOPOLOGY_COUNT" ]; then
        echo "   Status:   ✅ PASS - Perfect 1:1 parity"
    else
        DIFF=$((NEW_TOPOLOGY_COUNT - EXPECTED_TOPOLOGY_COUNT))
        if [ "$DIFF" -gt 0 ]; then
            echo "   Status:   ⚠️  MISMATCH - New has $DIFF MORE samples"
            echo "   Analysis: Possible duplicate publishing in new method OR old method missing samples"
        else
            DIFF=$((EXPECTED_TOPOLOGY_COUNT - NEW_TOPOLOGY_COUNT))
            echo "   Status:   ⚠️  MISMATCH - New has $DIFF FEWER samples"
            echo "   Analysis: Possible missing data in new method OR old method has duplicates"
        fi
    fi
    echo ""
    
    echo "2. MONITORING EVENTS (Volatile):"
    echo "   Expected: Chain ($OLD_CHAIN_COUNT) + Lifecycle ($OLD_LIFECYCLE_COUNT) + Monitoring ($OLD_MONITORING_COUNT) = $EXPECTED_EVENT_COUNT"
    echo "   Actual:   $NEW_EVENT_COUNT"
    
    if [ "$NEW_EVENT_COUNT" -eq "$EXPECTED_EVENT_COUNT" ]; then
        echo "   Status:   ✅ PASS - Perfect 1:1 parity"
    else
        DIFF=$((NEW_EVENT_COUNT - EXPECTED_EVENT_COUNT))
        if [ "$DIFF" -gt 0 ]; then
            echo "   Status:   ⚠️  MISMATCH - New has $DIFF MORE samples"
            echo "   Analysis: Possible duplicate publishing in new method OR old method missing samples"
        else
            DIFF=$((EXPECTED_EVENT_COUNT - NEW_EVENT_COUNT))
            echo "   Status:   ⚠️  MISMATCH - New has $DIFF FEWER samples"
            echo "   Analysis: Possible missing data in new method OR old method has duplicates"
        fi
    fi
    echo ""
    
    echo "=========================================="
    echo "OVERALL RESULT:"
    echo "=========================================="
    
    if [ "$NEW_TOPOLOGY_COUNT" -eq "$EXPECTED_TOPOLOGY_COUNT" ] && [ "$NEW_EVENT_COUNT" -eq "$EXPECTED_EVENT_COUNT" ]; then
        echo "✅ PASS - All topics have 1:1 parity"
        echo ""
        echo "Consolidation is working correctly!"
        exit 0
    else
        echo "⚠️  MISMATCH - Parity verification failed"
        echo ""
        echo "ACTION REQUIRED:"
        echo "1. Review raw spy log: $TEMP_DIR/spy_raw.log"
        echo "2. Check for duplicate publications in code"
        echo "3. Verify all dual-publishing paths are correct"
        echo "4. Investigate whether old method has issues"
        echo ""
        echo "Note: Do NOT assume new method is broken - investigate both methods!"
        exit 1
    fi
} | tee "$RESULTS_FILE"

echo ""
echo "Results saved to: $RESULTS_FILE"
echo "Raw spy log: $TEMP_DIR/spy_raw.log"
echo ""

