#!/bin/bash
set -e

echo "🚀 Genesis Multi-Agent Demo V2"
echo "================================"
echo ""

# Cleanup function for graceful shutdown
cleanup() {
    echo ""
    echo "🧹 Shutting down services..."
    if [ ! -z "$CALC_PID" ]; then
        kill $CALC_PID 2>/dev/null || true
        echo "  ✅ Calculator service stopped"
    fi
    if [ ! -z "$ASSISTANT_PID" ]; then
        kill $ASSISTANT_PID 2>/dev/null || true
        echo "  ✅ PersonalAssistant stopped"
    fi
    echo "👋 Demo cleanup complete"
}

# Set up signal handlers for cleanup
trap cleanup EXIT INT TERM

# Check if we're in the right directory
if [ ! -f "agents/personal_assistant.py" ]; then
    echo "❌ Error: Must run from MultiAgentV2 directory"
    echo "Current directory: $(pwd)"
    echo "Expected file: agents/personal_assistant.py"
    exit 1
fi

# Check if calculator service exists
if [ ! -f "../../services/calculator_service.py" ]; then
    echo "❌ Error: Calculator service not found at ../../services/calculator_service.py"
    echo "Make sure you're running from examples/MultiAgentV2/"
    exit 1
fi

echo "📊 Starting calculator service..."
cd ../../
python -m services.calculator_service &
CALC_PID=$!
echo "  ✅ Calculator service started (PID: $CALC_PID)"

# Return to MultiAgentV2 directory
cd examples/MultiAgentV2

echo ""
echo "🤖 Starting PersonalAssistant..."
python agents/personal_assistant.py &
ASSISTANT_PID=$!
echo "  ✅ PersonalAssistant started (PID: $ASSISTANT_PID)"

echo ""
echo "⏳ Waiting for services to initialize..."
sleep 3

echo ""
echo "🖥️ Starting CLI test interface..."
echo "================================"
echo ""

# Run the CLI test - this will test both joke and math requests
python test_cli.py

# Check the exit code of the CLI test
CLI_EXIT_CODE=$?

echo ""
echo "📋 Demo Summary"
echo "==============="

if [ $CLI_EXIT_CODE -eq 0 ]; then
    echo "✅ Multi-Agent Demo completed successfully!"
    echo ""
    echo "🎯 What was demonstrated:"
    echo "  • PersonalAssistant agent discovery"
    echo "  • CLI interface connection to agent"
    echo "  • Conversational requests (jokes) via OpenAI"
    echo "  • Functional requests (math) via calculator service"
    echo "  • All using Genesis framework patterns"
    echo ""
    echo "🚀 Genesis framework is working correctly!"
else
    echo "❌ Multi-Agent Demo failed!"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "  • Check OPENAI_API_KEY environment variable"
    echo "  • Verify calculator service is running"
    echo "  • Check PersonalAssistant agent startup logs"
    echo "  • Ensure no firewall blocking DDS communication"
fi

# Cleanup will be called automatically via trap 