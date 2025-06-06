#!/bin/bash

# Genesis Multi-Agent Interactive Demo V2
# Enhanced version supporting multiple specialized agents:
# - PersonalAssistant (general agent with agent-to-agent delegation)
# - WeatherAgent (specialized weather agent)
# - Calculator Service (function calling)

set -e  # Exit on any error

echo "🚀 Genesis Multi-Agent Interactive Demo V2"
echo "=========================================="
echo ""

# Check if calculator service exists
if [ ! -f "../../test_functions/calculator_service.py" ]; then
    echo "❌ Error: Calculator service not found at ../../test_functions/calculator_service.py"
    echo "Make sure you're running from examples/MultiAgentV2/"
    exit 1
fi

# Check if personal assistant exists
if [ ! -f "agents/personal_assistant.py" ]; then
    echo "❌ Error: PersonalAssistant not found at agents/personal_assistant.py"
    echo "Make sure you're running from examples/MultiAgentV2/"
    exit 1
fi

# Check if weather agent exists
if [ ! -f "agents/weather_agent.py" ]; then
    echo "❌ Error: WeatherAgent not found at agents/weather_agent.py"
    echo "Make sure you're running from examples/MultiAgentV2/"
    exit 1
fi

# Check if interactive CLI exists
if [ ! -f "interactive_cli.py" ]; then
    echo "❌ Error: Interactive CLI not found at interactive_cli.py"
    echo "Make sure you're running from examples/MultiAgentV2/"
    exit 1
fi

# Check environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️ Warning: OPENAI_API_KEY not set - using OpenAI with no key may fail"
fi

if [ -z "$OPENWEATHERMAP_API_KEY" ]; then
    echo "⚠️ Warning: OPENWEATHERMAP_API_KEY not set - WeatherAgent will use mock data"
    echo "💡 Get a free API key at: https://openweathermap.org/api"
fi

echo "📊 Starting calculator service..."
cd ../../
python -m test_functions.calculator_service &
CALC_PID=$!
echo "✅ Calculator service started (PID: $CALC_PID)"

# Wait for calculator service to initialize
sleep 3

echo ""
echo "🤖 Starting PersonalAssistant..."
cd examples/MultiAgentV2/
python agents/personal_assistant.py &
PERSONAL_PID=$!
echo "✅ PersonalAssistant started (PID: $PERSONAL_PID)"

echo ""
echo "🌤️ Starting WeatherAgent..."
python agents/weather_agent.py &
WEATHER_PID=$!
echo "✅ WeatherAgent started (PID: $WEATHER_PID)"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    kill $CALC_PID 2>/dev/null || true
    kill $PERSONAL_PID 2>/dev/null || true  
    kill $WEATHER_PID 2>/dev/null || true
    wait $CALC_PID 2>/dev/null || true
    wait $PERSONAL_PID 2>/dev/null || true
    wait $WEATHER_PID 2>/dev/null || true
    echo "✅ Cleanup complete"
}

# Set up cleanup on script exit
trap cleanup EXIT

# Wait for all services to fully initialize
echo ""
echo "⏳ Waiting for all services to initialize..."
sleep 8

echo ""
echo "💬 Starting Interactive Multi-Agent Chat..."
echo "==========================================="
echo ""
echo "🎯 Choose your agent:"
echo "   • PersonalAssistant - General chat, math, weather delegation"  
echo "   • WeatherAgent - Direct weather specialization"
echo ""
echo "💡 Demo Scenarios:"
echo "   1. Connect to PersonalAssistant, ask 'What's the weather in London?'"
echo "      → Shows agent-to-agent delegation (PersonalAssistant → WeatherAgent)"
echo ""
echo "   2. Connect to WeatherAgent, ask 'How's the weather in Tokyo?'"
echo "      → Shows direct specialization"
echo ""
echo "   3. Connect to PersonalAssistant, ask 'What is 123 + 456?'"
echo "      → Shows agent-to-service function calling"
echo ""
echo "🚀 Starting Interactive CLI..."
echo ""

# Start interactive CLI (this will block until user quits)
python interactive_cli.py

echo ""
echo "👋 Demo completed! Thanks for trying Genesis Multi-Agent System!" 