#!/bin/bash
"""
Test Multi-Agent System with Timeouts
This script runs agents for specific durations to test communication patterns.
"""

set -e

echo "🚀 Starting Multi-Agent System Test with Timeouts"

# Cleanup any existing processes
echo "🧹 Cleaning up any existing processes..."
pkill -f "calculator_service.py" || true
pkill -f "personal_assistant.py" || true 
pkill -f "weather_agent.py" || true
sleep 2

# Start Calculator Service in background with 60 second timeout
echo "🔢 Starting Calculator Service (60 seconds)..."
timeout 60s python ../../test_functions/calculator_service.py &
CALC_PID=$!
sleep 3

# Start Personal Assistant in background with 45 second timeout
echo "🤖 Starting Personal Assistant (45 seconds)..."
timeout 45s python agents/personal_assistant.py &
PA_PID=$!
sleep 3

# Start Weather Agent in background with 30 second timeout
echo "🌤️ Starting Weather Agent (30 seconds)..."
timeout 30s python agents/weather_agent.py &
WA_PID=$!
sleep 5

echo "✅ All services started. Testing communication..."

# Wait a bit for discovery
echo "🔍 Waiting for agent discovery..."
sleep 5

# Run a quick test
echo "🧪 Running basic communication test..."
python -c "
import asyncio
import sys
sys.path.append('../../')
from genesis_lib.monitored_interface import MonitoredInterface

async def test():
    interface = MonitoredInterface('TestInterface', 'TestService')
    
    # Wait for agent discovery
    await asyncio.sleep(5)
    
    # Get discovered agents
    agents = interface.get_available_agents()
    print(f'📊 Discovered agents: {list(agents.keys())}')
    
    if agents:
        # Try to connect to first available agent
        first_agent = list(agents.keys())[0]
        print(f'🔗 Attempting to connect to {first_agent}...')
        
        connected = await interface.connect_to_agent(first_agent)
        if connected:
            print(f'✅ Connected to {first_agent}')
            
            # Send a simple test message
            response = await interface.send_request({'message': 'Hello, can you help me?'})
            print(f'📝 Response: {response}')
        else:
            print(f'❌ Failed to connect to {first_agent}')
    else:
        print('❌ No agents discovered')
    
    await interface.close()

try:
    asyncio.run(test())
except Exception as e:
    print(f'❌ Test failed: {e}')
"

echo "⏳ Waiting for agents to complete..."

# Wait for all background processes to complete
wait $CALC_PID 2>/dev/null || echo "Calculator service finished"
wait $PA_PID 2>/dev/null || echo "Personal Assistant finished" 
wait $WA_PID 2>/dev/null || echo "Weather Agent finished"

echo "🏁 Test completed. All agents have stopped." 