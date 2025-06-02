#!/bin/bash

# Interactive Genesis Multi-Agent Demo
# This script starts all services and provides an interactive interface for chatting with PersonalAssistant

set -e  # Exit on any error

echo "🚀 Genesis Interactive Demo V2"
echo "=============================="
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

# Store PIDs for cleanup
CALC_PID=""
AGENT_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Shutting down services..."
    if [ ! -z "$CALC_PID" ]; then
        kill $CALC_PID 2>/dev/null || true
        echo "  ✅ Calculator service stopped"
    fi
    if [ ! -z "$AGENT_PID" ]; then
        kill $AGENT_PID 2>/dev/null || true
        echo "  ✅ PersonalAssistant stopped"
    fi
    echo "👋 Interactive demo cleanup complete"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

echo "📊 Starting calculator service..."
cd ../../
python -m test_functions.calculator_service &
CALC_PID=$!
cd examples/MultiAgentV2/
echo "  ✅ Calculator service started (PID: $CALC_PID)"

echo ""
echo "🤖 Starting PersonalAssistant..."
python agents/personal_assistant.py &
AGENT_PID=$!
echo "  ✅ PersonalAssistant started (PID: $AGENT_PID)"

echo ""
echo "⏳ Waiting for services to initialize..."
sleep 8  # Give services time to start and discover each other

echo ""
echo "🖥️ Starting Interactive Chat Interface..."
echo "========================================"
echo ""
echo "💬 You can now chat with your PersonalAssistant!"
echo "   • Ask questions, request jokes, have conversations"
echo "   • Ask for math calculations (agent will use calculator service)"
echo "   • Type 'quit', 'exit', or 'bye' to end the session"
echo "   • Press Ctrl+C to stop everything"
echo ""

# Start the interactive CLI
python interactive_cli.py

echo ""
echo "📋 Interactive Demo Complete"
echo "============================"
echo "Thanks for trying Genesis Multi-Agent Demo V2! 🚀" 