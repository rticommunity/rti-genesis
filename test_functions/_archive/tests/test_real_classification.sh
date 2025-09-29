#!/bin/bash

# Real LLM Classification Test Script
# Tests real LLM classification with real weather agent and agent-to-agent communication

echo "🌤️  Starting Real LLM Classification Test"
echo "==========================================="

# Change to the correct directory
cd "$(dirname "$0")/.."

# Check for required API keys
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY is required for this test"
    echo "   Set it with: export OPENAI_API_KEY='your_key_here'"
    exit 1
fi

echo "✅ OPENAI_API_KEY found - LLM classification enabled"

if [ -z "$OPENWEATHERMAP_API_KEY" ]; then
    echo "⚠️  OPENWEATHERMAP_API_KEY not set - weather agent will use mock data"
    echo "   Set it with: export OPENWEATHERMAP_API_KEY='your_key_here' for real weather data"
else
    echo "✅ OPENWEATHERMAP_API_KEY found - real weather data enabled"
fi

# Clean up any background processes on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    if [ ! -z "$WEATHER_AGENT_PID" ]; then
        echo "Stopping Real Weather Agent (PID: $WEATHER_AGENT_PID)..."
        kill $WEATHER_AGENT_PID 2>/dev/null
        wait $WEATHER_AGENT_PID 2>/dev/null
    fi
    if [ ! -z "$GENERAL_AGENT_PID" ]; then
        echo "Stopping Real General Agent (PID: $GENERAL_AGENT_PID)..."
        kill $GENERAL_AGENT_PID 2>/dev/null
        wait $GENERAL_AGENT_PID 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Real Weather Agent and capture its PID
echo ""
echo "1. Starting Real Weather Agent..."
echo "   Command: python test_functions/test_real_classification.py weather"
python test_functions/test_real_classification.py weather &
WEATHER_AGENT_PID=$!
echo "   Real Weather Agent started with PID: $WEATHER_AGENT_PID"

# Wait for weather agent to initialize
echo "   Waiting 5 seconds for Real Weather Agent to initialize..."
sleep 5

# Start Real General Agent and capture its PID
echo "2. Starting Real General Agent with LLM Classification..."
echo "   Command: python test_functions/test_real_classification.py general"
python test_functions/test_real_classification.py general &
GENERAL_AGENT_PID=$!
echo "   Real General Agent started with PID: $GENERAL_AGENT_PID"

# Wait for general agent to initialize and agents to discover each other
echo "   Waiting 8 seconds for all agents to initialize and discover each other..."
sleep 8

echo ""
echo "3. Running Real LLM Classification Test..."
echo "   Command: python test_functions/test_real_classification.py test"
echo ""

# Run the classification test
python test_functions/test_real_classification.py test

# Check if the test was successful
TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Real LLM Classification Test PASSED!"
else
    echo "❌ Real LLM Classification Test FAILED (exit code: $TEST_EXIT_CODE)"
fi

echo ""
echo "4. Test Summary:"
echo "   • Real Weather Agent (PID: $WEATHER_AGENT_PID) ✅ Running"
echo "   • Real General Agent (PID: $GENERAL_AGENT_PID) ✅ Running"  
echo "   • LLM Classification Test: $([ $TEST_EXIT_CODE -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

echo ""
echo "🔍 Agents will continue running for 10 more seconds to demonstrate discovery..."
echo "   You can observe agent capability announcements and LLM routing decisions."
sleep 10

echo ""
echo "🏁 Real LLM Classification Test Complete!"
cleanup 