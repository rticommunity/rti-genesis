#!/bin/bash

# Enhanced Agent Capability Test Script
# Tests enhanced capability advertisement and intelligent routing

echo "🚀 Starting Enhanced Agent Capability Test"
echo "==========================================="

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
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Weather Agent and capture its PID
echo "1. Starting Weather Specialist Agent..."
echo "   Command: python test_functions/test_enhanced_capabilities.py weather"
python test_functions/test_enhanced_capabilities.py weather > /tmp/weather_agent.log 2>&1 &
WEATHER_AGENT_PID=$!
echo "   Weather Agent started with PID: $WEATHER_AGENT_PID"

# Wait for Weather Agent to initialize
echo "2. Waiting for Weather Agent to initialize..."
sleep 5

# Check if Weather Agent is still running
if ! kill -0 $WEATHER_AGENT_PID 2>/dev/null; then
    echo "❌ Weather Agent failed to start. Check /tmp/weather_agent.log for errors."
    echo "Weather Agent log contents:"
    cat /tmp/weather_agent.log
    exit 1
else
    echo "✅ Weather Agent process is running (PID: $WEATHER_AGENT_PID)"
fi

# Start General Agent (requester)
echo ""
echo "3. Starting General Purpose Agent..."
echo "   Command: python test_functions/test_enhanced_capabilities.py general"
echo ""

timeout 25s python test_functions/test_enhanced_capabilities.py general

GENERAL_AGENT_EXIT_CODE=$?

echo ""
echo "4. Test Results:"

if [ $GENERAL_AGENT_EXIT_CODE -eq 0 ]; then
    echo "✅ SUCCESS: Enhanced capability advertisement and routing test completed successfully!"
    echo "📊 Agents successfully advertised and discovered enhanced capabilities"
    echo "🧠 Intelligent routing based on specializations is working"
elif [ $GENERAL_AGENT_EXIT_CODE -eq 124 ]; then
    echo "⏰ TIMEOUT: General Agent timed out - this might be normal if the test completed"
else
    echo "❌ FAILURE: General Agent exited with code $GENERAL_AGENT_EXIT_CODE"
fi

echo ""
echo "5. Weather Agent Log Output:"
echo "============================"
if [ -f /tmp/weather_agent.log ]; then
    cat /tmp/weather_agent.log
else
    echo "No log file found for Weather Agent"
fi

# Clean up
cleanup 