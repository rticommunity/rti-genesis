#!/usr/bin/env python3
"""
Basic Two-Agent Communication Test

This test creates two mock agents and verifies that they can successfully
communicate with each other using the AgentCommunicationMixin.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.agent_communication import AgentCommunicationMixin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockAgent(AgentCommunicationMixin):
    """Mock agent implementation for testing"""
    
    def __init__(self, agent_id: str, agent_name: str):
        super().__init__()
        
        # Mock the app object
        self.app = Mock()
        self.app.agent_id = agent_id
        self.app.participant = Mock()
        
        # Mock attributes
        self.agent_name = agent_name
        self.base_service_name = f"TestService_{agent_name}"
        
        # Track processed requests for testing
        self.processed_requests = []
    
    async def process_agent_request(self, request):
        """Process agent requests and track them"""
        logger.info(f"Agent {self.agent_name} processing request: {request['message']}")
        
        # Store the request for verification
        self.processed_requests.append(request)
        
        # Generate a response
        response = {
            "message": f"Hello from {self.agent_name}! Processed: {request['message']}",
            "status": 0,
            "conversation_id": request.get("conversation_id", ""),
            "processed_by": self.agent_name
        }
        
        return response

class TestTwoAgentCommunication(unittest.TestCase):
    """Test cases for two-agent communication"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.agent_a = MockAgent("agent_a", "AgentA")
        self.agent_b = MockAgent("agent_b", "AgentB")
    
    def test_agent_initialization(self):
        """Test that both agents initialize correctly"""
        logger.info("Testing agent initialization")
        
        # Check Agent A
        self.assertEqual(self.agent_a.app.agent_id, "agent_a")
        self.assertEqual(self.agent_a.agent_name, "AgentA")
        self.assertEqual(self.agent_a.base_service_name, "TestService_AgentA")
        
        # Check Agent B
        self.assertEqual(self.agent_b.app.agent_id, "agent_b")
        self.assertEqual(self.agent_b.agent_name, "AgentB")
        self.assertEqual(self.agent_b.base_service_name, "TestService_AgentB")
        
        logger.info("✅ Agent initialization test passed")
    
    def test_service_name_generation(self):
        """Test service name generation for both agents"""
        logger.info("Testing service name generation")
        
        # Test Agent A service name
        service_name_a = self.agent_a._get_agent_service_name("agent_a")
        expected_a = "TestService_AgentA_agent_a"
        self.assertEqual(service_name_a, expected_a)
        
        # Test Agent B service name
        service_name_b = self.agent_b._get_agent_service_name("agent_b")
        expected_b = "TestService_AgentB_agent_b"
        self.assertEqual(service_name_b, expected_b)
        
        logger.info("✅ Service name generation test passed")
    
    async def test_agent_discovery_simulation(self):
        """Test simulated agent discovery"""
        logger.info("Testing agent discovery simulation")
        
        # Simulate Agent A discovering Agent B
        self.agent_a.discovered_agents["agent_b"] = {
            "agent_id": "agent_b",
            "name": "AgentB",
            "agent_type": "test_agent",
            "service_name": "TestService_AgentB",
            "description": "Test Agent B"
        }
        
        # Simulate Agent B discovering Agent A
        self.agent_b.discovered_agents["agent_a"] = {
            "agent_id": "agent_a",
            "name": "AgentA", 
            "agent_type": "test_agent",
            "service_name": "TestService_AgentA",
            "description": "Test Agent A"
        }
        
        # Verify discovery
        self.assertTrue(self.agent_a.is_agent_discovered("agent_b"))
        self.assertTrue(self.agent_b.is_agent_discovered("agent_a"))
        
        # Test wait_for_agent (should return immediately since agents are discovered)
        result_a = await self.agent_a.wait_for_agent("agent_b", timeout_seconds=0.1)
        result_b = await self.agent_b.wait_for_agent("agent_a", timeout_seconds=0.1)
        
        self.assertTrue(result_a)
        self.assertTrue(result_b)
        
        logger.info("✅ Agent discovery simulation test passed")
    
    async def test_process_agent_request(self):
        """Test agent request processing"""
        logger.info("Testing agent request processing")
        
        # Test Agent A processing a request
        request_a = {
            "message": "Hello Agent A",
            "conversation_id": "test_conv_123",
            "sender_agent_id": "agent_b",
            "timestamp": 1234567890
        }
        
        response_a = await self.agent_a.process_agent_request(request_a)
        
        self.assertEqual(response_a["status"], 0)
        self.assertIn("Hello from AgentA", response_a["message"])
        self.assertIn("Hello Agent A", response_a["message"])
        self.assertEqual(response_a["conversation_id"], "test_conv_123")
        self.assertEqual(response_a["processed_by"], "AgentA")
        
        # Verify request was tracked
        self.assertEqual(len(self.agent_a.processed_requests), 1)
        self.assertEqual(self.agent_a.processed_requests[0]["message"], "Hello Agent A")
        
        # Test Agent B processing a request
        request_b = {
            "message": "Hello Agent B",
            "conversation_id": "test_conv_456",
            "sender_agent_id": "agent_a",
            "timestamp": 1234567891
        }
        
        response_b = await self.agent_b.process_agent_request(request_b)
        
        self.assertEqual(response_b["status"], 0)
        self.assertIn("Hello from AgentB", response_b["message"])
        self.assertIn("Hello Agent B", response_b["message"])
        self.assertEqual(response_b["conversation_id"], "test_conv_456")
        self.assertEqual(response_b["processed_by"], "AgentB")
        
        logger.info("✅ Agent request processing test passed")
    
    @patch('genesis_lib.agent_communication.rpc.Requester')
    async def test_connection_attempt_mock(self, mock_requester_class):
        """Test connection attempt with mocked RPC"""
        logger.info("Testing connection attempt with mocked RPC")
        
        # Set up mock
        mock_requester = Mock()
        mock_requester.matched_replier_count = 1  # Simulate successful match
        mock_requester_class.return_value = mock_requester
        
        # Mock RPC types
        self.agent_a.agent_request_type = Mock()
        self.agent_a.agent_reply_type = Mock()
        
        # Simulate Agent A discovering Agent B
        self.agent_a.discovered_agents["agent_b"] = {
            "agent_id": "agent_b",
            "name": "AgentB",
            "agent_type": "test_agent"
        }
        
        # Test connection
        result = await self.agent_a.connect_to_agent("agent_b", timeout_seconds=1.0)
        
        # Verify connection was successful
        self.assertTrue(result)
        self.assertIn("agent_b", self.agent_a.agent_connections)
        self.assertEqual(self.agent_a.agent_connections["agent_b"], mock_requester)
        
        # Verify RPC requester was created with correct parameters
        mock_requester_class.assert_called_once()
        call_args = mock_requester_class.call_args
        self.assertEqual(call_args[1]["service_name"], "TestService_AgentA_agent_b")
        
        logger.info("✅ Connection attempt test passed")
    
    async def test_send_request_without_connection(self):
        """Test sending request to undiscovered agent"""
        logger.info("Testing send request to undiscovered agent")
        
        # Test sending request to agent that hasn't been discovered
        response = await self.agent_a.send_agent_request(
            target_agent_id="unknown_agent",
            message="Test message",
            timeout_seconds=0.1
        )
        
        # Should return None since agent is not discovered
        self.assertIsNone(response)
        
        logger.info("✅ Send request without connection test passed")
    
    def test_connection_cleanup(self):
        """Test connection cleanup"""
        logger.info("Testing connection cleanup")
        
        # Add mock connections
        mock_requester_a = Mock()
        mock_requester_b = Mock()
        
        self.agent_a.agent_connections["agent_b"] = mock_requester_a
        self.agent_a.agent_connections["agent_c"] = mock_requester_b
        
        # Test cleanup of specific connection
        self.agent_a._cleanup_agent_connection("agent_b")
        
        # Verify specific connection was cleaned up
        self.assertNotIn("agent_b", self.agent_a.agent_connections)
        self.assertIn("agent_c", self.agent_a.agent_connections)
        mock_requester_a.close.assert_called_once()
        
        # Test cleanup of all connections
        self.agent_a._cleanup_agent_connections()
        
        # Verify all connections were cleaned up
        self.assertEqual(len(self.agent_a.agent_connections), 0)
        mock_requester_b.close.assert_called_once()
        
        logger.info("✅ Connection cleanup test passed")

async def run_async_tests():
    """Run async test methods"""
    logger.info("Running async tests...")
    
    try:
        # Create test instance
        test_comm = TestTwoAgentCommunication()
        test_comm.setUp()
        
        # Run async tests
        await test_comm.test_agent_discovery_simulation()
        await test_comm.test_process_agent_request()
        await test_comm.test_connection_attempt_mock()
        await test_comm.test_send_request_without_connection()
        
        logger.info("✅ All async tests completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Async tests failed: {e}")
        raise

def main():
    """Main test function"""
    logger.info("Starting Two-Agent Communication Tests")
    
    try:
        # Run synchronous tests
        unittest.main(argv=[''], exit=False, verbosity=2)
        
        # Run async tests
        asyncio.run(run_async_tests())
        
        logger.info("🎉 All Two-Agent Communication Tests PASSED!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Tests failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 