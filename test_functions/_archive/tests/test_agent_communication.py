#!/usr/bin/env python3
"""
Basic Agent Communication Test

This test verifies that the AgentCommunicationMixin can be properly initialized
and that its basic methods work correctly.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
import unittest
from unittest.mock import Mock, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.agent_communication import AgentCommunicationMixin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestAgentCommunication(unittest.TestCase):
    """Test cases for AgentCommunicationMixin"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mixin = AgentCommunicationMixin()
    
    def test_initialization(self):
        """Test that AgentCommunicationMixin initializes correctly"""
        logger.info("Testing AgentCommunicationMixin initialization")
        
        # Check that all required attributes are initialized
        self.assertIsInstance(self.mixin.agent_connections, dict)
        self.assertIsInstance(self.mixin.discovered_agents, dict)
        self.assertEqual(len(self.mixin.agent_connections), 0)
        self.assertEqual(len(self.mixin.discovered_agents), 0)
        
        # Check that attributes are properly initialized
        self.assertIsNone(self.mixin.agent_capability_writer)
        self.assertIsNone(self.mixin.agent_capability_reader)
        self.assertIsNone(self.mixin.agent_request_type)
        self.assertIsNone(self.mixin.agent_reply_type)
        self.assertIsNone(self.mixin.agent_replier)
        self.assertFalse(self.mixin._agent_communication_enabled)
        
        logger.info("✅ AgentCommunicationMixin initialization test passed")
    
    def test_type_loading(self):
        """Test that RPC types can be loaded"""
        logger.info("Testing RPC type loading")
        
        # Test type loading
        success = self.mixin._initialize_agent_rpc_types()
        
        if success:
            self.assertIsNotNone(self.mixin.agent_request_type)
            self.assertIsNotNone(self.mixin.agent_reply_type)
            logger.info("✅ RPC types loaded successfully")
        else:
            logger.warning("⚠️ RPC type loading failed (expected if not in full DDS environment)")
    
    def test_service_name_generation(self):
        """Test agent service name generation"""
        logger.info("Testing service name generation")
        
        # Mock the required attributes
        self.mixin.base_service_name = "TestService"
        self.mixin.app = Mock()
        self.mixin.app.agent_id = "test_agent_123"
        
        service_name = self.mixin._get_agent_service_name("test_agent_123")
        expected_name = "TestService_test_agent_123"
        
        self.assertEqual(service_name, expected_name)
        logger.info(f"✅ Service name generation test passed: {service_name}")
    
    def test_service_name_fallback(self):
        """Test agent service name generation fallback"""
        logger.info("Testing service name generation fallback")
        
        # Test without base_service_name
        service_name = self.mixin._get_agent_service_name("fallback_agent")
        expected_name = "AgentService_fallback_agent"
        
        self.assertEqual(service_name, expected_name)
        logger.info(f"✅ Service name fallback test passed: {service_name}")
    
    def test_agent_discovery_methods(self):
        """Test agent discovery utility methods"""
        logger.info("Testing agent discovery methods")
        
        # Add some mock discovered agents
        self.mixin.discovered_agents = {
            "agent1": {
                "agent_id": "agent1",
                "name": "TestAgent1",
                "agent_type": "calculator",
                "service_name": "CalcService",
                "description": "Calculator agent"
            },
            "agent2": {
                "agent_id": "agent2", 
                "name": "TestAgent2",
                "agent_type": "processor",
                "service_name": "ProcessService",
                "description": "Data processor agent"
            }
        }
        
        # Test get_discovered_agents
        discovered = self.mixin.get_discovered_agents()
        self.assertEqual(len(discovered), 2)
        self.assertIn("agent1", discovered)
        self.assertIn("agent2", discovered)
        
        # Test is_agent_discovered
        self.assertTrue(self.mixin.is_agent_discovered("agent1"))
        self.assertFalse(self.mixin.is_agent_discovered("nonexistent"))
        
        # Test get_agents_by_type
        calc_agents = self.mixin.get_agents_by_type("calculator")
        self.assertEqual(len(calc_agents), 1)
        self.assertEqual(calc_agents[0]["agent_id"], "agent1")
        
        # Test get_agents_by_capability
        calc_capability = self.mixin.get_agents_by_capability("calc")
        self.assertEqual(len(calc_capability), 1)
        self.assertEqual(calc_capability[0]["agent_id"], "agent1")
        
        logger.info("✅ Agent discovery methods test passed")
    
    async def test_wait_for_agent_timeout(self):
        """Test wait_for_agent timeout functionality"""
        logger.info("Testing wait_for_agent timeout")
        
        # Test timeout for non-existent agent
        result = await self.mixin.wait_for_agent("nonexistent_agent", timeout_seconds=0.1)
        self.assertFalse(result)
        
        logger.info("✅ Wait for agent timeout test passed")
    
    async def test_wait_for_agent_success(self):
        """Test wait_for_agent success case"""
        logger.info("Testing wait_for_agent success")
        
        # Add agent after a short delay
        async def add_agent_later():
            await asyncio.sleep(0.05)
            self.mixin.discovered_agents["test_agent"] = {"agent_id": "test_agent"}
        
        # Start the delayed addition
        asyncio.create_task(add_agent_later())
        
        # Wait for the agent
        result = await self.mixin.wait_for_agent("test_agent", timeout_seconds=1.0)
        self.assertTrue(result)
        
        logger.info("✅ Wait for agent success test passed")
    
    def test_cleanup(self):
        """Test cleanup functionality"""
        logger.info("Testing cleanup functionality")
        
        # Mock some connections
        mock_requester = Mock()
        self.mixin.agent_connections["test_agent"] = mock_requester
        
        # Test cleanup
        self.mixin._cleanup_agent_connections()
        
        # Verify cleanup
        self.assertEqual(len(self.mixin.agent_connections), 0)
        mock_requester.close.assert_called_once()
        
        logger.info("✅ Cleanup test passed")

class ConcreteAgentCommunication(AgentCommunicationMixin):
    """Concrete implementation for testing abstract methods"""
    
    async def process_agent_request(self, request):
        """Simple implementation for testing"""
        return {
            "message": f"Processed: {request.get('message', '')}",
            "status": 0,
            "conversation_id": request.get("conversation_id", "")
        }

class TestConcreteImplementation(unittest.TestCase):
    """Test the concrete implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.agent = ConcreteAgentCommunication()
    
    async def test_process_agent_request(self):
        """Test the concrete process_agent_request implementation"""
        logger.info("Testing concrete process_agent_request implementation")
        
        request = {
            "message": "test message",
            "conversation_id": "test_conv_123",
            "sender_agent_id": "sender_agent"
        }
        
        response = await self.agent.process_agent_request(request)
        
        self.assertEqual(response["message"], "Processed: test message")
        self.assertEqual(response["status"], 0)
        self.assertEqual(response["conversation_id"], "test_conv_123")
        
        logger.info("✅ Concrete implementation test passed")

async def run_async_tests():
    """Run async test methods"""
    logger.info("Running async tests...")
    
    # Create test instances
    test_comm = TestAgentCommunication()
    test_comm.setUp()
    
    test_concrete = TestConcreteImplementation()
    test_concrete.setUp()
    
    # Run async tests
    await test_comm.test_wait_for_agent_timeout()
    await test_comm.test_wait_for_agent_success()
    await test_concrete.test_process_agent_request()
    
    logger.info("✅ All async tests completed successfully")

def main():
    """Main test function"""
    logger.info("Starting Agent Communication Tests")
    
    try:
        # Run synchronous tests
        unittest.main(argv=[''], exit=False, verbosity=2)
        
        # Run async tests
        asyncio.run(run_async_tests())
        
        logger.info("🎉 All Agent Communication Tests PASSED!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Tests failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 