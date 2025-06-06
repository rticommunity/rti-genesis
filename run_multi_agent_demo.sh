#!/bin/bash
set -e

echo "🚀 Genesis Multi-Agent Demo V3"
echo "==============================="
echo "Featuring @genesis_tool auto-discovery and clean demo mode"
echo ""

# Check if we're in the Genesis_LIB root directory
if [ ! -d "examples/MultiAgent" ]; then
    echo "❌ Error: Must run from Genesis_LIB root directory"
    echo "Current directory: $(pwd)"
    echo "Expected directory: examples/MultiAgent"
    exit 1
fi

echo "🎯 What this demo showcases:"
echo "  • @genesis_tool automatic schema generation"
echo "  • Agent-to-agent delegation (PersonalAssistant → WeatherAgent)"
echo "  • Function service integration (Calculator)"
echo "  • Clean demo mode for presentations"
echo "  • Real weather API integration"
echo ""

echo "📁 Switching to MultiAgent demo directory..."
cd examples/MultiAgent

echo "🚀 Launching Genesis Multi-Agent Interactive Demo..."
echo ""

# Execute the demo script
./run_interactive_demo.sh

# Check the exit code
DEMO_EXIT_CODE=$?

echo ""
echo "📋 Demo Summary"
echo "==============="

if [ $DEMO_EXIT_CODE -eq 0 ]; then
    echo "✅ Multi-Agent Demo completed successfully!"
    echo ""
    echo "🎉 Key features demonstrated:"
    echo "  • Zero-boilerplate @genesis_tool decorators"
    echo "  • Automatic agent discovery and delegation"
    echo "  • Real-time weather data integration"
    echo "  • Professional demo mode with progress indicators"
    echo "  • Type-safe tool development with Python hints"
    echo ""
    echo "🌟 Genesis framework transformation complete - from complex framework to 'magic decorators'!"
else
    echo "❌ Multi-Agent Demo failed!"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "  • Check OPENAI_API_KEY environment variable"
    echo "  • Get optional OPENWEATHERMAP_API_KEY for real weather data"
    echo "  • Run: python config/demo_config.py (to check environment)"
    echo "  • For debug mode, edit config/demo_config.py and set ENABLE_DEMO_TRACING=True"
fi

echo ""
echo "📚 Next steps:"
echo "  • Explore examples/MultiAgent/agents/weather_agent.py for @genesis_tool examples"
echo "  • Read examples/MultiAgent/README.md for detailed architecture"
echo "  • Check examples/MultiAgent/USAGE.md for usage examples" 