#!/usr/bin/env python3
"""
Debug script to test MonitoredAgent creation with agent communication.
"""

import sys
import os
import traceback

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

try:
    print("Creating MonitoredAgent with agent communication...")
    agent = MonitoredAgent(
        agent_name='TestAgent',
        base_service_name='TestService',
        enable_agent_communication=True
    )
    print('✓ Agent created successfully')
    print(f'✓ Agent communication enabled: {hasattr(agent, "agent_communication")}')
    if hasattr(agent, 'agent_communication'):
        print(f'✓ Agent communication object: {agent.agent_communication}')
        print(f'✓ Agent communication types loaded: {agent.agent_communication.agent_request_type is not None}')
    
    print("Cleaning up...")
    import asyncio
    asyncio.run(agent.close())
    print("✓ Agent closed successfully")
    
except Exception as e:
    print(f'✗ Error: {e}')
    traceback.print_exc() 