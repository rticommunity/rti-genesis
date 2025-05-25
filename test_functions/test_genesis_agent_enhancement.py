#!/usr/bin/env python3
"""
Test GenesisAgent Enhancement

This test verifies that the enhanced GenesisAgent class works correctly
with the new enable_agent_communication parameter.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.agent import GenesisAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestAgent(GenesisAgent):
    """Simple test agent implementation"""
    
    async def process_request(self, request):
        """Simple request processing"""
        return {
            'message': f'Processed: {request.get("message", "")}',
            'status': 0
        }
    
    async def process_agent_request(self, request):
        """Handle agent-to-agent requests"""
        return {
            'message': f'Agent response: {request.get("message", "")}',
            'status': 0,
            'conversation_id': request.get('conversation_id', '')
        }

def test_agent_without_communication():
    """Test agent without agent communication enabled"""
    logger.info("Testing agent without agent communication")
    
    agent = TestAgent('TestAgent1', 'TestService', enable_agent_communication=False)
    
    # Verify agent communication is disabled
    assert agent.enable_agent_communication == False
    assert agent.agent_communication is None
    
    # Verify convenience methods return appropriate responses
    discovered = agent.get_discovered_agents()
    assert discovered == {}
    
    logger.info("✅ Agent without communication test passed")
    return agent

def test_agent_with_communication():
    """Test agent with agent communication enabled"""
    logger.info("Testing agent with agent communication")
    
    agent = TestAgent('TestAgent2', 'TestService', enable_agent_communication=True)
    
    # Verify agent communication is enabled
    assert agent.enable_agent_communication == True
    assert agent.agent_communication is not None
    
    # Verify the communication wrapper has the right attributes
    assert hasattr(agent.agent_communication, 'send_agent_request')
    assert hasattr(agent.agent_communication, 'connect_to_agent')
    assert hasattr(agent.agent_communication, 'discovered_agents')
    
    # Verify convenience methods work
    discovered = agent.get_discovered_agents()
    assert isinstance(discovered, dict)
    
    logger.info("✅ Agent with communication test passed")
    return agent

async def test_agent_request_processing():
    """Test agent request processing"""
    logger.info("Testing agent request processing")
    
    agent = TestAgent('TestAgent3', 'TestService', enable_agent_communication=True)
    
    # Test processing an agent request
    request = {
        'message': 'Hello from another agent',
        'conversation_id': 'test_conv_123',
        'sender_agent_id': 'sender_agent',
        'timestamp': 1234567890
    }
    
    response = await agent.process_agent_request(request)
    
    assert response['status'] == 0
    assert 'Agent response: Hello from another agent' in response['message']
    assert response['conversation_id'] == 'test_conv_123'
    
    logger.info("✅ Agent request processing test passed")

async def test_convenience_methods():
    """Test agent communication convenience methods"""
    logger.info("Testing convenience methods")
    
    # Test agent without communication
    agent_no_comm = TestAgent('TestAgent4', 'TestService', enable_agent_communication=False)
    
    result = await agent_no_comm.send_agent_request('target_agent', 'test message')
    assert result is None
    
    result = await agent_no_comm.wait_for_agent('target_agent', timeout_seconds=0.1)
    assert result == False
    
    # Test agent with communication
    agent_with_comm = TestAgent('TestAgent5', 'TestService', enable_agent_communication=True)
    
    # These should not return None/False immediately (they'll fail for other reasons)
    # but they should at least try to execute
    result = await agent_with_comm.wait_for_agent('nonexistent_agent', timeout_seconds=0.1)
    assert result == False  # Should timeout
    
    logger.info("✅ Convenience methods test passed")

def main():
    """Main test function"""
    logger.info("Starting GenesisAgent Enhancement Tests")
    
    try:
        # Test basic functionality
        agent1 = test_agent_without_communication()
        agent2 = test_agent_with_communication()
        
        # Test async functionality
        asyncio.run(test_agent_request_processing())
        asyncio.run(test_convenience_methods())
        
        logger.info("🎉 All GenesisAgent Enhancement Tests PASSED!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 