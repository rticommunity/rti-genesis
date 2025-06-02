#!/bin/bash

# Simple runner for the comprehensive multi-agent test
# This is the main test for Phase 5 of the Genesis implementation

set -e

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Genesis Phase 5 - Comprehensive Multi-Agent Test"
echo "=================================================="
echo ""
echo "This test validates all communication patterns:"
echo "  ✓ Interface → Agent (direct)"
echo "  ✓ Agent → Agent (weather queries)"
echo "  ✓ Agent → Service (math calculations)"
echo "  ✓ Complex chains (weather + math)"
echo "  ✓ Multi-step reasoning"
echo "  ✓ System knowledge queries"
echo ""

# Check if monitoring is desired
if [ "$1" = "--with-monitor" ]; then
    echo "🖥️ Starting monitoring in background..."
    python "$PROJECT_ROOT/genesis_monitor.py" --domain 0 > monitor_output.log 2>&1 &
    MONITOR_PID=$!
    echo "  Monitor PID: $MONITOR_PID (output in monitor_output.log)"
    
    # Cleanup function that includes monitor
    cleanup_with_monitor() {
        echo "🧹 Stopping monitor..."
        kill $MONITOR_PID 2>/dev/null || true
        echo "✅ Monitor stopped"
    }
    trap cleanup_with_monitor EXIT
    
    sleep 2
fi

echo "🎬 Starting comprehensive multi-agent test..."
echo ""

# Run the main test
"$PROJECT_ROOT/run_scripts/run_interface_agent_agent_service_test.sh"

echo ""
echo "🎉 Comprehensive multi-agent test completed!"

if [ "$1" = "--with-monitor" ]; then
    echo "📊 Monitor output saved to monitor_output.log"
fi 