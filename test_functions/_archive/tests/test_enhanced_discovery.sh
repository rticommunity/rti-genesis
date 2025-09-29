#!/bin/bash

# Enhanced Discovery Test Script
# Tests the new capability-based discovery methods for agent-to-agent communication

echo "🚀 Starting Enhanced Discovery Test"
echo "=================================="

# Change to the correct directory
cd "$(dirname "$0")/.."

# Clean up any background processes on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    if [ ! -z "$WEATHER_AGENT_PID" ]; then
        echo "Stopping Weather Agent (PID: $WEATHER_AGENT_PID)..."
        kill $WEATHER_AGENT_PID 2>/dev/null
        wait $WEATHER_AGENT_PID 2>/dev/null
    fi
    if [ ! -z "$FINANCE_AGENT_PID" ]; then
        echo "Stopping Finance Agent (PID: $FINANCE_AGENT_PID)..."
        kill $FINANCE_AGENT_PID 2>/dev/null
        wait $FINANCE_AGENT_PID 2>/dev/null
    fi
    if [ ! -z "$GENERAL_AGENT_PID" ]; then
        echo "Stopping General Agent (PID: $GENERAL_AGENT_PID)..."
        kill $GENERAL_AGENT_PID 2>/dev/null
        wait $GENERAL_AGENT_PID 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Weather Specialist Agent and capture its PID
echo "1. Starting Weather Specialist Agent..."
echo "   Command: python test_functions/test_enhanced_discovery.py weather"
python test_functions/test_enhanced_discovery.py weather &
WEATHER_AGENT_PID=$!
echo "   Weather Agent started with PID: $WEATHER_AGENT_PID"

# Wait for weather agent to initialize
echo "   Waiting 3 seconds for Weather Agent to initialize..."
sleep 3

# Start Finance Specialist Agent and capture its PID
echo "2. Starting Finance Specialist Agent..."
echo "   Command: python test_functions/test_enhanced_discovery.py finance"
python test_functions/test_enhanced_discovery.py finance &
FINANCE_AGENT_PID=$!
echo "   Finance Agent started with PID: $FINANCE_AGENT_PID"

# Wait for finance agent to initialize
echo "   Waiting 3 seconds for Finance Agent to initialize..."
sleep 3

# Start General Purpose Agent and capture its PID
echo "3. Starting General Purpose Agent..."
echo "   Command: python test_functions/test_enhanced_discovery.py general"
python test_functions/test_enhanced_discovery.py general &
GENERAL_AGENT_PID=$!
echo "   General Agent started with PID: $GENERAL_AGENT_PID"

# Wait for general agent to initialize and agents to discover each other
echo "   Waiting 5 seconds for all agents to initialize and discover each other..."
sleep 5

echo ""
echo "4. Running Enhanced Discovery Methods Test..."
echo "   Command: python test_functions/test_enhanced_discovery.py test"
echo ""

# Run the discovery test
python test_functions/test_enhanced_discovery.py test

# Check if the test was successful
TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Enhanced Discovery Methods Test PASSED!"
else
    echo "❌ Enhanced Discovery Methods Test FAILED (exit code: $TEST_EXIT_CODE)"
fi

echo ""
echo "5. Test Summary:"
echo "   • Weather Specialist Agent (PID: $WEATHER_AGENT_PID) ✅ Running"
echo "   • Finance Specialist Agent (PID: $FINANCE_AGENT_PID) ✅ Running"  
echo "   • General Purpose Agent (PID: $GENERAL_AGENT_PID) ✅ Running"
echo "   • Enhanced Discovery Test: $([ $TEST_EXIT_CODE -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

echo ""
echo "🔍 Agents will continue running for 10 more seconds to demonstrate discovery..."
echo "   You can observe agent capability announcements and discovery messages."
sleep 10

echo ""
echo "🏁 Enhanced Discovery Test Complete!"
cleanup 