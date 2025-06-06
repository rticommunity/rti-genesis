#!/bin/bash

# Debug Agent Communication Script
# This script starts agents with proper timeouts and monitors DDS communication
# to debug agent-to-agent capability advertising issues.

set -e

echo "🔍 Genesis Agent Communication Debug Tool"
echo "========================================="

# Configuration
AGENT_TIMEOUT=60  # Run agents for 60 seconds
SPY_TIMEOUT=15    # Monitor DDS for 15 seconds at a time
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Cleanup function
cleanup() {
    log_info "🧹 Cleaning up processes..."
    pkill -f "calculator_service.py" || true
    pkill -f "personal_assistant.py" || true
    pkill -f "weather_agent.py" || true
    pkill -f "rtiddsspy" || true
    sleep 2
    log_success "✅ Cleanup completed"
}

# Set trap for cleanup
trap cleanup EXIT

# Check if required files exist
check_requirements() {
    log_info "📁 Checking required files..."
    
    if [ ! -f "$SCRIPT_DIR/agents/personal_assistant.py" ]; then
        log_error "PersonalAssistant not found at agents/personal_assistant.py"
        exit 1
    fi
    
    if [ ! -f "$SCRIPT_DIR/agents/weather_agent.py" ]; then
        log_error "WeatherAgent not found at agents/weather_agent.py"
        exit 1
    fi
    
    if [ ! -f "$SCRIPT_DIR/../../test_functions/calculator_service.py" ]; then
        log_error "Calculator service not found at ../../test_functions/calculator_service.py"
        exit 1
    fi
    
    if [ -z "$NDDSHOME" ]; then
        log_error "NDDSHOME not set - cannot use rtiddsspy"
        exit 1
    fi
    
    if [ ! -f "$NDDSHOME/bin/rtiddsspy" ]; then
        log_error "rtiddsspy not found at $NDDSHOME/bin/rtiddsspy"
        exit 1
    fi
    
    log_success "✅ All required files found"
}

# Start monitoring DDS in background
start_dds_monitoring() {
    log_info "📊 Starting DDS monitoring..."
    
    # Create log file for DDS output
    DDS_LOG="$SCRIPT_DIR/dds_spy.log"
    rm -f "$DDS_LOG"
    
    # Start DDS spy in background
    timeout ${AGENT_TIMEOUT}s $NDDSHOME/bin/rtiddsspy -printSample > "$DDS_LOG" 2>&1 &
    DDS_SPY_PID=$!
    
    log_success "✅ DDS monitoring started (PID: $DDS_SPY_PID, log: dds_spy.log)"
    sleep 2
}

# Start calculator service
start_calculator() {
    log_info "🧮 Starting Calculator Service..."
    cd "$SCRIPT_DIR/../../"
    timeout ${AGENT_TIMEOUT}s python test_functions/calculator_service.py &
    CALC_PID=$!
    log_success "✅ Calculator Service started (PID: $CALC_PID)"
    sleep 3
}

# Start PersonalAssistant
start_personal_assistant() {
    log_info "🤖 Starting PersonalAssistant..."
    cd "$SCRIPT_DIR"
    timeout ${AGENT_TIMEOUT}s python agents/personal_assistant.py &
    PA_PID=$!
    log_success "✅ PersonalAssistant started (PID: $PA_PID)"
    sleep 5
}

# Start WeatherAgent
start_weather_agent() {
    log_info "🌤️ Starting WeatherAgent..."
    cd "$SCRIPT_DIR"
    timeout ${AGENT_TIMEOUT}s python agents/weather_agent.py &
    WA_PID=$!
    log_success "✅ WeatherAgent started (PID: $WA_PID)"
    sleep 5
}

# Analyze DDS traffic
analyze_dds_traffic() {
    log_info "🔍 Analyzing DDS traffic..."
    
    DDS_LOG="$SCRIPT_DIR/dds_spy.log"
    
    if [ ! -f "$DDS_LOG" ]; then
        log_error "DDS log file not found: $DDS_LOG"
        return 1
    fi
    
    echo ""
    echo "📊 DDS Traffic Analysis:"
    echo "========================"
    
    # Count different message types
    DISCOVERY_COUNT=$(grep -c "AgentDiscovery" "$DDS_LOG" 2>/dev/null || echo "0")
    CAPABILITY_COUNT=$(grep -c "capabilities\|specializations\|classification_tags" "$DDS_LOG" 2>/dev/null || echo "0")
    AGENT_COUNT=$(grep -c "agent_id\|prefered_name" "$DDS_LOG" 2>/dev/null || echo "0")
    
    echo "📈 Message Counts:"
    echo "   Agent Discovery Messages: $DISCOVERY_COUNT"
    echo "   Capability-related Messages: $CAPABILITY_COUNT"
    echo "   Agent Registration Messages: $AGENT_COUNT"
    
    echo ""
    echo "🔍 Capability Advertising Check:"
    if grep -q "weather" "$DDS_LOG" 2>/dev/null; then
        log_success "✅ Weather capabilities detected in DDS traffic"
    else
        log_warning "⚠️ No weather capabilities detected in DDS traffic"
    fi
    
    if grep -q "specializations" "$DDS_LOG" 2>/dev/null; then
        log_success "✅ Agent specializations detected in DDS traffic"
    else
        log_warning "⚠️ No agent specializations detected in DDS traffic"
    fi
    
    if grep -q "classification_tags" "$DDS_LOG" 2>/dev/null; then
        log_success "✅ Classification tags detected in DDS traffic"
    else
        log_warning "⚠️ No classification tags detected in DDS traffic"
    fi
    
    echo ""
    echo "📄 Recent DDS Messages (last 20 lines):"
    echo "----------------------------------------"
    tail -20 "$DDS_LOG" || echo "No recent messages"
    
    echo ""
    echo "🔍 Full DDS log available at: $DDS_LOG"
}

# Test agent discovery
test_agent_discovery() {
    log_info "🧪 Testing agent discovery..."
    
    cd "$SCRIPT_DIR"
    timeout 20s python -c "
import asyncio
import sys
import os
sys.path.append('../..')
from genesis_lib.monitored_interface import MonitoredInterface

async def test_discovery():
    interface = MonitoredInterface('DebugInterface', 'OpenAIAgent')
    
    print('⏳ Waiting for agent discovery (15 seconds)...')
    await asyncio.sleep(15)
    
    agents = interface.available_agents
    print(f'📊 Discovered {len(agents)} agents:')
    
    for agent_id, agent_info in agents.items():
        name = agent_info.get('prefered_name', 'Unknown')
        service = agent_info.get('service_name', 'Unknown')
        capabilities = agent_info.get('capabilities', [])
        specializations = agent_info.get('specializations', [])
        
        print(f'   🤖 {name} ({service})')
        print(f'      Capabilities: {capabilities}')
        print(f'      Specializations: {specializations}')
        print(f'      All fields: {list(agent_info.keys())}')
    
    await interface.close()
    return len(agents)

try:
    agent_count = asyncio.run(test_discovery())
    if agent_count >= 2:
        print('✅ Agent discovery working - found expected agents')
    else:
        print(f'⚠️ Only found {agent_count} agents (expected 2+)')
except Exception as e:
    print(f'❌ Discovery test failed: {e}')
"
}

# Main execution
main() {
    log_info "Starting comprehensive agent communication debug..."
    
    # Step 1: Check requirements
    check_requirements
    
    # Step 2: Clean up any existing processes
    cleanup
    sleep 2
    
    # Step 3: Start DDS monitoring first
    start_dds_monitoring
    
    # Step 4: Start services and agents with staggered timing
    start_calculator
    start_personal_assistant
    start_weather_agent
    
    # Step 5: Wait for agents to fully initialize and discover each other
    log_info "⏳ Waiting for agents to initialize and discover each other..."
    sleep 10
    
    # Step 6: Test agent discovery from interface perspective
    test_agent_discovery
    
    # Step 7: Wait a bit more for DDS traffic
    log_info "⏳ Collecting DDS traffic data..."
    sleep 10
    
    # Step 8: Analyze DDS traffic
    analyze_dds_traffic
    
    # Step 9: Wait for agents to complete or timeout
    log_info "⏳ Waiting for agents to complete (or timeout in ${AGENT_TIMEOUT}s)..."
    wait $CALC_PID 2>/dev/null || log_info "Calculator service completed"
    wait $PA_PID 2>/dev/null || log_info "PersonalAssistant completed"
    wait $WA_PID 2>/dev/null || log_info "WeatherAgent completed"
    wait $DDS_SPY_PID 2>/dev/null || log_info "DDS monitoring completed"
    
    log_success "🎉 Debug session completed"
    log_info "📄 Check dds_spy.log for full DDS traffic details"
}

# Check command line argument
case "${1:-run}" in
    run)
        main
        ;;
    clean)
        cleanup
        ;;
    *)
        echo "Usage: $0 [run|clean]"
        echo "  run   - Run full debug session (default)"
        echo "  clean - Clean up existing processes only"
        exit 1
        ;;
esac 