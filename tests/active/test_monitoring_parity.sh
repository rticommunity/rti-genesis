#!/bin/bash

# Automated Monitoring Topic Parity Test
# 
# This test verifies that during the dual-publishing phase, the new unified monitoring
# topics (GraphTopologyV2 and EventV2) receive 1:1 parity with the old topics.
#
# Expected behavior:
# - GraphTopologyV2 should have samples = GenesisGraphNode + GenesisGraphEdge
# - EventV2 should have samples = ChainEvent + ComponentLifecycleEvent + MonitoringEvent
#   PLUS additional LIFECYCLE events for graph topology (which is a new feature)
#
# This test uses rtiddsspy to capture DDS traffic and validates sample counts.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$PROJECT_ROOT/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check for NDDSHOME
if [ -z "$NDDSHOME" ]; then
    echo "ERROR: NDDSHOME environment variable is not set."
    echo "Please set NDDSHOME to your RTI Connext DDS installation directory."
    exit 1
fi

# Verify rtiddsspy exists
RTIDDSSPY="$NDDSHOME/bin/rtiddsspy"
if [ ! -f "$RTIDDSSPY" ]; then
    echo "ERROR: rtiddsspy not found at $RTIDDSSPY"
    exit 1
fi

# Ensure spy config exists
SPY_CONFIG="$PROJECT_ROOT/spy_transient.xml"
if [ ! -f "$SPY_CONFIG" ]; then
    echo "ERROR: Spy config not found at $SPY_CONFIG"
    exit 1
fi

echo "=========================================="
echo "Automated Monitoring Parity Test"
echo "=========================================="
echo ""

# Create temp directory for this test run
TEST_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="$LOG_DIR/parity_test_$TEST_TIMESTAMP"
mkdir -p "$TEMP_DIR"

SPY_LOG="$TEMP_DIR/spy_capture.log"
AGENT_LOG="$TEMP_DIR/agent.log"
SERVICE_LOG="$TEMP_DIR/service.log"
INTERFACE_LOG="$TEMP_DIR/interface.log"

# PIDs of background processes
pids=()

# Cleanup function
cleanup() {
    echo "Cleaning up parity test processes..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "Parity test cleanup complete."
}
trap cleanup EXIT

echo "Starting rtiddsspy capture..."
RTIDDSSPY_PROFILEFILE="$SPY_CONFIG" "$RTIDDSSPY" -printSample > "$SPY_LOG" 2>&1 &
SPY_PID=$!
pids+=("$SPY_PID")

# Give spy a moment to initialize
sleep 2

echo "Starting test components (agent, service, interface)..."

# Start SimpleGenesisAgent
export GENESIS_TOOL_CHOICE="required"
python "$SCRIPT_DIR/../helpers/simpleGenesisAgent.py" --tag parity_test --verbose > "$AGENT_LOG" 2>&1 &
pids+=("$!")

# Start CalculatorService
python "$PROJECT_ROOT/test_functions/services/calculator_service.py" --service-name ParityTestCalc > "$SERVICE_LOG" 2>&1 &
pids+=("$!")

# Wait for components to initialize
echo "Waiting 5 seconds for initialization..."
sleep 5

# Ensure agent has discovered functions
echo "Waiting for agent to discover functions..."
DISCOVERY_WAIT=15
DISCOVERY_START=$(date +%s)
while true; do
    if grep -q "function_discovery - INFO - Updated/Added discovered function: add" "$AGENT_LOG"; then
        echo "✅ Function discovery confirmed"
        break
    fi
    NOW=$(date +%s)
    ELAPSED=$((NOW - DISCOVERY_START))
    if [ $ELAPSED -ge $DISCOVERY_WAIT ]; then
        echo "ERROR: Agent did not discover functions within ${DISCOVERY_WAIT}s"
        echo "--- Agent Log (tail) ---"
        tail -n 40 "$AGENT_LOG"
        exit 1
    fi
    sleep 0.5
done

# Run interface to generate monitoring traffic
echo "Running interface to generate monitoring traffic..."
if python "$SCRIPT_DIR/../helpers/simpleGenesisInterfaceStatic.py" --question "What is 100 plus 200?" --verbose > "$INTERFACE_LOG" 2>&1; then
    echo "✅ Interface test completed successfully"
else
    echo "ERROR: Interface test failed"
    echo "--- Interface Log ---"
    cat "$INTERFACE_LOG"
    exit 1
fi

# Give a moment for all DDS traffic to be captured
echo "Waiting 3 seconds for DDS traffic capture..."
sleep 3

# Stop spy
echo "Stopping rtiddsspy..."
kill "$SPY_PID" 2>/dev/null || true
wait "$SPY_PID" 2>/dev/null || true

echo ""
echo "=========================================="
echo "Analyzing DDS Traffic for Parity"
echo "=========================================="
echo ""

# Count samples per topic (only "New data" or "Modified instance", not writer/reader announcements)
count_topic_samples() {
    local log_file="$1"
    local topic_name="$2"
    
    local count=$(grep "rti/connext/genesis/$topic_name" "$log_file" 2>/dev/null | grep -E "New data|Modified instance" | wc -l | tr -d ' ')
    echo "${count:-0}"
}

# Old Topics
OLD_NODE_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/GenesisGraphNode")
OLD_EDGE_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/GenesisGraphEdge")
OLD_CHAIN_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/ChainEvent")
OLD_LIFECYCLE_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/ComponentLifecycleEvent")
OLD_MONITORING_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/MonitoringEvent")

# New Topics (V2 transition naming)
NEW_TOPOLOGY_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/GraphTopologyV2")
NEW_EVENT_COUNT=$(count_topic_samples "$SPY_LOG" "monitoring/EventV2")

echo "OLD TOPICS:"
echo "  GenesisGraphNode:           $OLD_NODE_COUNT"
echo "  GenesisGraphEdge:           $OLD_EDGE_COUNT"
echo "  ChainEvent:                 $OLD_CHAIN_COUNT"
echo "  ComponentLifecycleEvent:    $OLD_LIFECYCLE_COUNT"
echo "  MonitoringEvent:            $OLD_MONITORING_COUNT"
echo "  ---"
echo "  Total:                      $((OLD_NODE_COUNT + OLD_EDGE_COUNT + OLD_CHAIN_COUNT + OLD_LIFECYCLE_COUNT + OLD_MONITORING_COUNT))"
echo ""

echo "NEW TOPICS (V2):"
echo "  GraphTopologyV2:            $NEW_TOPOLOGY_COUNT"
echo "  EventV2:                    $NEW_EVENT_COUNT"
echo "  ---"
echo "  Total:                      $((NEW_TOPOLOGY_COUNT + NEW_EVENT_COUNT))"
echo ""

echo "=========================================="
echo "PARITY VALIDATION:"
echo "=========================================="
echo ""

# Validate GraphTopologyV2
EXPECTED_TOPOLOGY=$((OLD_NODE_COUNT + OLD_EDGE_COUNT))
echo "1. GraphTopologyV2 (Durable):"
echo "   Expected: Node ($OLD_NODE_COUNT) + Edge ($OLD_EDGE_COUNT) = $EXPECTED_TOPOLOGY"
echo "   Actual:   $NEW_TOPOLOGY_COUNT"

TOPOLOGY_PASS=false
if [ "$NEW_TOPOLOGY_COUNT" -eq "$EXPECTED_TOPOLOGY" ]; then
    echo "   Status:   ✅ PASS - Perfect 1:1 parity"
    TOPOLOGY_PASS=true
else
    DIFF=$((NEW_TOPOLOGY_COUNT - EXPECTED_TOPOLOGY))
    if [ "$DIFF" -gt 0 ]; then
        echo "   Status:   ⚠️  MISMATCH - New has $DIFF MORE samples than expected"
    else
        echo "   Status:   ❌ FAIL - New has $((-DIFF)) FEWER samples than expected"
    fi
    echo "   This indicates a dual-publishing issue in graph_monitoring.py"
fi
echo ""

# Validate EventV2
# Note: EventV2 will have MORE samples than old topics because it includes new LIFECYCLE events
# for graph topology (which the old system didn't publish)
EXPECTED_EVENTS_MIN=$((OLD_CHAIN_COUNT + OLD_LIFECYCLE_COUNT + OLD_MONITORING_COUNT))
EXPECTED_EVENTS_WITH_LIFECYCLE=$((EXPECTED_EVENTS_MIN + EXPECTED_TOPOLOGY))  # Each topology update = 1 lifecycle event

echo "2. EventV2 (Volatile):"
echo "   Expected (minimum): Chain ($OLD_CHAIN_COUNT) + Lifecycle ($OLD_LIFECYCLE_COUNT) + Monitoring ($OLD_MONITORING_COUNT) = $EXPECTED_EVENTS_MIN"
echo "   Expected (with new lifecycle): $EXPECTED_EVENTS_WITH_LIFECYCLE (includes $EXPECTED_TOPOLOGY topology lifecycle events)"
echo "   Actual:   $NEW_EVENT_COUNT"

EVENTS_PASS=false
if [ "$NEW_EVENT_COUNT" -ge "$EXPECTED_EVENTS_MIN" ] && [ "$NEW_EVENT_COUNT" -le "$((EXPECTED_EVENTS_WITH_LIFECYCLE + 5))" ]; then
    # Allow small tolerance for timing differences
    echo "   Status:   ✅ PASS - Within expected range"
    EVENTS_PASS=true
    
    if [ "$NEW_EVENT_COUNT" -gt "$EXPECTED_EVENTS_MIN" ]; then
        LIFECYCLE_SAMPLES=$((NEW_EVENT_COUNT - EXPECTED_EVENTS_MIN))
        echo "   Note:     $LIFECYCLE_SAMPLES are NEW LIFECYCLE events (graph topology feature)"
    fi
else
    if [ "$NEW_EVENT_COUNT" -lt "$EXPECTED_EVENTS_MIN" ]; then
        MISSING=$((EXPECTED_EVENTS_MIN - NEW_EVENT_COUNT))
        echo "   Status:   ❌ FAIL - Missing $MISSING samples"
        echo "   This indicates dual-publishing issues in monitored_interface.py or monitored_agent.py"
    else
        EXTRA=$((NEW_EVENT_COUNT - EXPECTED_EVENTS_WITH_LIFECYCLE))
        echo "   Status:   ⚠️  WARNING - $EXTRA more samples than expected (possible duplicates)"
    fi
fi
echo ""

# Overall result
echo "=========================================="
echo "OVERALL RESULT:"
echo "=========================================="

if $TOPOLOGY_PASS && $EVENTS_PASS; then
    echo "✅ SUCCESS - Monitoring parity validated"
    echo ""
    echo "Dual-publishing is working correctly:"
    echo "  • GraphTopologyV2 receives all node and edge data"
    echo "  • EventV2 receives all chain, lifecycle, and monitoring events"
    echo "  • Plus new lifecycle events for graph topology updates"
    echo ""
    echo "Logs saved to: $TEMP_DIR"
    exit 0
else
    echo "❌ FAILURE - Parity validation failed"
    echo ""
    echo "Please review:"
    echo "  • Spy log: $SPY_LOG"
    echo "  • Agent log: $AGENT_LOG"
    echo "  • Service log: $SERVICE_LOG"
    echo "  • Interface log: $INTERFACE_LOG"
    echo ""
    echo "Investigate dual-publishing code in:"
    if ! $TOPOLOGY_PASS; then
        echo "  • genesis_lib/graph_monitoring.py (publish_node, publish_edge)"
    fi
    if ! $EVENTS_PASS; then
        echo "  • genesis_lib/monitored_interface.py (ChainEvent publishing)"
        echo "  • genesis_lib/monitored_agent.py (MonitoringEvent, ChainEvent publishing)"
    fi
    exit 1
fi

