#!/bin/bash

# Genesis Multi-Agent Interactive Demo V3
# Modern multi-agent system featuring @genesis_tool auto-discovery

set -e  # Exit on any error

echo "🚀 Genesis Multi-Agent Interactive Demo V3"
echo "==========================================="
echo "🌟 Featuring @genesis_tool Auto-Discovery System"
echo ""

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "agents" ] || [ ! -d "interfaces" ]; then
    echo "❌ Error: Please run this script from the examples/MultiAgent directory"
    echo "   Current directory: $(pwd)"
    echo "   Expected files: README.md, agents/, interfaces/"
    exit 1
fi

# Check environment variables
echo "🔧 Checking environment..."
python config/demo_config.py
echo ""

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY environment variable not set"
    echo "💡 Please set your OpenAI API key:"
    echo "   export OPENAI_API_KEY=\"your-openai-api-key\""
    exit 1
fi

if [ -z "$OPENWEATHERMAP_API_KEY" ]; then
    echo "⚠️ Warning: OPENWEATHERMAP_API_KEY not set - WeatherAgent will use mock data"
    echo "💡 For real weather data, get a free API key at: https://openweathermap.org/api"
    echo "   export OPENWEATHERMAP_API_KEY=\"your-weather-api-key\""
    echo ""
fi

echo "📊 Starting Genesis Multi-Agent System..."
echo ""

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    
    # Kill specific processes we started
    if [ ! -z "$CALC_PID" ]; then
        kill $CALC_PID 2>/dev/null || true
        echo "   ✅ Calculator service stopped"
    fi
    
    if [ ! -z "$WEATHER_PID" ]; then
        kill $WEATHER_PID 2>/dev/null || true
        echo "   ✅ WeatherAgent stopped"
    fi
    
    if [ ! -z "$PERSONAL_PID" ]; then
        kill $PERSONAL_PID 2>/dev/null || true
        echo "   ✅ PersonalAssistant stopped"
    fi
    
    if [ ! -z "$DDSSPY_PID" ]; then
        kill $DDSSPY_PID 2>/dev/null || true
        echo "   ✅ DDS Spy stopped"
    fi
    
    # Wait for processes to clean up
    if [ ! -z "$CALC_PID" ]; then wait $CALC_PID 2>/dev/null || true; fi
    if [ ! -z "$WEATHER_PID" ]; then wait $WEATHER_PID 2>/dev/null || true; fi
    if [ ! -z "$PERSONAL_PID" ]; then wait $PERSONAL_PID 2>/dev/null || true; fi
    if [ ! -z "$DDSSPY_PID" ]; then wait $DDSSPY_PID 2>/dev/null || true; fi
    
    echo "   ✅ Cleanup complete"
}

# Set up cleanup on script exit
trap cleanup EXIT

# 0. Start DDS Spy to capture all DDS traffic
echo "🔍 Starting DDS Spy to monitor all traffic..."
if [ ! -z "$NDDSHOME" ]; then
    mkdir -p logs
    $NDDSHOME/bin/rtiddsspy -printSample > logs/dds_spy_output.log 2>&1 &
    DDSSPY_PID=$!
    echo "   ✅ DDS Spy started (PID: $DDSSPY_PID)"
    echo "   📝 DDS traffic will be logged to: logs/dds_spy_output.log"
else
    echo "   ⚠️ NDDSHOME not set - skipping DDS Spy"
    DDSSPY_PID=""
fi

# 1. Start Calculator Service (function service)
echo ""
echo "🧮 Starting Calculator service..."
cd ../../
python -m test_functions.calculator_service &
CALC_PID=$!
echo "   ✅ Calculator service started (PID: $CALC_PID)"
cd examples/MultiAgent/

# Wait for calculator to initialize
sleep 3

# 2. Start WeatherAgent (@genesis_tool example)
echo ""
echo "🌤️ Starting WeatherAgent with @genesis_tool auto-discovery..."
python agents/weather_agent.py &
WEATHER_PID=$!
echo "   ✅ WeatherAgent started (PID: $WEATHER_PID)"
echo "   🛠️ @genesis_tool decorators will auto-generate OpenAI schemas"

# 3. Start PersonalAssistant (general agent with delegation)
echo ""
echo "🤖 Starting PersonalAssistant with multi-agent capabilities..."
python agents/personal_assistant.py &
PERSONAL_PID=$!
echo "   ✅ PersonalAssistant started (PID: $PERSONAL_PID)"
echo "   🔍 Will auto-discover WeatherAgent and Calculator service"

# Wait for all services to fully initialize and discover each other
echo ""
echo "⏳ Waiting for all services to initialize and discover each other..."
sleep 8

echo ""
echo "✅ All services started successfully!"
echo ""
echo "🎯 Available Services:"
echo "   • PersonalAssistant (General agent with delegation)"
echo "   • WeatherAgent (Specialized @genesis_tool example)"
echo "   • Calculator Service (Function service integration)"
if [ ! -z "$DDSSPY_PID" ]; then
    echo "   • DDS Spy (Monitoring all DDS traffic)"
fi
echo ""
echo "🧪 Ready for Demo Scenarios:"
echo "   1. Weather Delegation: 'What's the weather in Tokyo?'"
echo "   2. Function Calling: 'Calculate 987 * 654'"
echo "   3. @genesis_tool Demo: 'Give me a 5-day forecast for Paris'"
echo "   4. Mixed Capabilities: 'Weather in London and calculate 15% tip on $85'"
echo ""

# Prompt user for interface choice
echo "🎯 Choose your interface:"
echo "   1. Interactive CLI (recommended for exploration)"
echo "   2. Web GUI Interface (modern web-based interface with network visualization)"
echo "   3. Quick automated test (for validation)"
echo ""
read -p "Your choice (1, 2, or 3): " interface_choice

case $interface_choice in
    1)
        echo ""
        echo "🚀 Starting Interactive CLI..."
        echo "💡 Type 'scenarios' for demo examples"
        echo ""
        python interfaces/interactive_cli.py
        ;;
    2)
        echo ""
        echo "🌐 Starting Web GUI Interface..."
        echo "🎯 Features:"
        echo "   • Interactive chat with agents"
        echo "   • Real-time network topology visualization"
        echo "   • Live monitoring of agent communications"
        echo "   • Dynamic agent discovery and selection"
        echo ""
        echo "📡 Web interface will be available at: http://127.0.0.1:5000"
        echo "💡 Open your browser to interact with the Genesis system"
        if [ ! -z "$DDSSPY_PID" ]; then
            echo "🔍 DDS traffic is being logged to: logs/dds_spy_output.log"
        fi
        echo ""
        python interfaces/gui_interface.py
        ;;
    3)
        echo ""
        echo "🧪 Running Quick Test..."
        echo ""
        python interfaces/quick_test.py
        ;;
    *)
        echo "❌ Invalid choice. Starting Interactive CLI by default..."
        echo ""
        python interfaces/interactive_cli.py
        ;;
esac

echo ""
echo "👋 Genesis Multi-Agent Demo completed!"
echo "🌟 Thank you for exploring @genesis_tool auto-discovery!"

# Show DDS spy log summary if it was running
if [ ! -z "$DDSSPY_PID" ] && [ -f "logs/dds_spy_output.log" ]; then
    echo ""
    echo "📊 DDS Traffic Summary:"
    echo "========================"
    echo "Total DDS samples captured: $(grep -c "sample" logs/dds_spy_output.log 2>/dev/null || echo "0")"
    echo "ComponentLifecycleEvent samples: $(grep -c "ComponentLifecycleEvent" logs/dds_spy_output.log 2>/dev/null || echo "0")"
    echo "ChainEvent samples: $(grep -c "ChainEvent" logs/dds_spy_output.log 2>/dev/null || echo "0")"
    echo ""
    echo "📝 Full DDS traffic log available at: logs/dds_spy_output.log"
    echo "💡 Use this log to debug any missing monitoring data"
    echo "========================"
fi

# =============================================================================
# TRACING CONTROL
# =============================================================================

show_tracing_options() {
    echo -e "${BLUE}🔧 Tracing Control Options${NC}"
    echo -e "${BLUE}========================${NC}"
    echo
    echo -e "${WHITE}Demo Mode (Clean):${NC}"
    echo "   • No debug output"
    echo "   • Clean progress indicators"
    echo "   • Professional appearance"
    echo "   • Recommended for presentations"
    echo
    echo -e "${WHITE}Debug Mode (Verbose):${NC}"
    echo "   • Full agent tracing"
    echo "   • Genesis library internals"
    echo "   • OpenAI API call details"
    echo "   • Recommended for development"
    echo
}

configure_tracing() {
    echo -e "${PURPLE}🎛️ Configure Demo Experience${NC}"
    echo -e "${PURPLE}============================${NC}"
    echo
    show_tracing_options
    
    echo -e "${YELLOW}Choose your experience:${NC}"
    echo "   1. Clean Demo Mode (recommended for presentations)"
    echo "   2. Debug Mode (full tracing for development)"
    echo "   3. Show tracing options again"
    echo
    
    while true; do
        read -p "Your choice (1, 2, or 3): " tracing_choice
        case $tracing_choice in
            1)
                echo -e "${GREEN}✅ Setting up Clean Demo Mode${NC}"
                # Update config to disable tracing
                python3 -c "
import sys, os
sys.path.insert(0, '$CONFIG_DIR')
config_file = '$CONFIG_DIR/demo_config.py'
with open(config_file, 'r') as f:
    content = f.read()
content = content.replace('ENABLE_DEMO_TRACING = True', 'ENABLE_DEMO_TRACING = False')
content = content.replace('ENABLE_DEMO_TRACING = False', 'ENABLE_DEMO_TRACING = False')
with open(config_file, 'w') as f:
    f.write(content)
print('✅ Clean demo mode configured')
"
                break
                ;;
            2)
                echo -e "${YELLOW}⚙️ Setting up Debug Mode${NC}"
                # Update config to enable tracing
                python3 -c "
import sys, os
sys.path.insert(0, '$CONFIG_DIR')
config_file = '$CONFIG_DIR/demo_config.py'
with open(config_file, 'r') as f:
    content = f.read()
content = content.replace('ENABLE_DEMO_TRACING = False', 'ENABLE_DEMO_TRACING = True')
content = content.replace('ENABLE_DEMO_TRACING = True', 'ENABLE_DEMO_TRACING = True')
with open(config_file, 'w') as f:
    f.write(content)
print('✅ Debug mode configured')
"
                break
                ;;
            3)
                show_tracing_options
                continue
                ;;
            *)
                echo -e "${RED}❌ Invalid choice. Please enter 1, 2, or 3.${NC}"
                ;;
        esac
    done
    echo
}

# =============================================================================
# MAIN DEMO FLOW
# =============================================================================

echo -e "${PURPLE}🚀 Genesis Multi-Agent Interactive Demo${NC}"
echo -e "${PURPLE}=======================================${NC}"
echo
echo -e "${WHITE}This demo showcases Genesis's @genesis_tool system:${NC}"
echo "   • Automatic tool schema generation"
echo "   • Zero-boilerplate agent development"  
echo "   • Agent-to-agent delegation"
echo "   • Real weather API integration"
echo

# Step 1: Configure tracing experience
configure_tracing

# Step 2: Environment validation
echo -e "${BLUE}🔍 Validating Demo Environment${NC}"
echo -e "${BLUE}==============================${NC}"
echo

check_dependencies
validate_environment
echo

# Step 3: Start services with appropriate output level
echo -e "${GREEN}🚀 Starting Genesis Services${NC}"
echo -e "${GREEN}============================${NC}"
echo

start_calculator_service
start_personal_assistant  
start_weather_agent

echo -e "${GREEN}✅ All services started successfully!${NC}"
echo

# Display service status
echo -e "${CYAN}🎯 Available Services:${NC}"
echo "   • PersonalAssistant (General agent with delegation)"
echo "   • WeatherAgent (Specialized @genesis_tool example)"
echo "   • Calculator Service (Function service integration)"
echo

# Step 4: Demo scenario suggestions
echo -e "${YELLOW}🧪 Ready for Demo Scenarios:${NC}"
echo "   1. Weather Delegation: 'What's the weather in Tokyo?'"
echo "   2. Function Calling: 'Calculate 987 * 654'"
echo "   3. @genesis_tool Demo: 'Give me a 5-day forecast for Paris'"
echo "   4. Mixed Capabilities: 'Weather in London and calculate 15% tip on $85'"
echo

# Step 5: Interface selection
echo -e "${PURPLE}🎯 Choose your interface:${NC}"
echo "   1. Interactive CLI (recommended for exploration)"
echo "   2. Quick automated test (for validation)"
echo

interface_choice=""
while [[ ! "$interface_choice" =~ ^[12]$ ]]; do
    read -p "Your choice (1 or 2): " interface_choice
    if [[ ! "$interface_choice" =~ ^[12]$ ]]; then
        echo -e "${RED}❌ Please enter 1 or 2${NC}"
    fi
done

if [ "$interface_choice" = "1" ]; then
    echo -e "${GREEN}🚀 Starting Interactive CLI...${NC}"
    echo -e "${YELLOW}💡 Type 'scenarios' for demo examples${NC}"
    echo
    
    # Start interactive CLI
    cd "$DEMO_DIR"
    python3 interfaces/interactive_cli.py
    
elif [ "$interface_choice" = "2" ]; then
    echo -e "${GREEN}🧪 Running Quick Automated Test...${NC}"
    echo
    
    # Run automated test
    cd "$DEMO_DIR"
    python3 interfaces/quick_test.py
fi

echo
echo -e "${GREEN}👋 Genesis Multi-Agent Demo completed!${NC}"
echo -e "${GREEN}🌟 Thank you for exploring @genesis_tool auto-discovery!${NC}" 