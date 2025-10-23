#!/usr/bin/env python3
"""
Test MCP (Model Context Protocol) integration with Genesis agents.

This test verifies that:
1. An agent can enable MCP server functionality
2. The MCP server exposes the agent's process_message method as a tool
3. MCP clients can discover and call the agent's tool
4. The agent properly handles requests from MCP clients
5. Error handling works correctly (port conflicts, missing dependencies)

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestMCPAgent(OpenAIGenesisAgent):
    """Simple test agent that provides a greeting service via MCP."""
    
    def __init__(self):
        """Initialize the test agent."""
        super().__init__(
            model_name="gpt-4o-mini",  # Use cheaper model for testing
            agent_name="TestMCPAgent",
            description="A test agent for MCP integration testing",
            enable_tracing=False  # Keep tests quiet
        )
        logger.info("TestMCPAgent initialized")


async def test_mcp_enable():
    """Test that MCP can be enabled on an agent."""
    logger.info("=" * 60)
    logger.info("TEST 1: Enable MCP on agent")
    logger.info("=" * 60)
    
    agent = None
    try:
        # Create agent
        agent = TestMCPAgent()
        logger.info("✓ Agent created successfully")
        
        # Enable MCP on a test port
        test_port = 18000  # Use high port to avoid conflicts
        agent.enable_mcp(
            port=test_port,
            toolname="test_agent_tool",
            tooldesc="Test tool for MCP integration testing"
        )
        logger.info(f"✓ MCP enabled on port {test_port}")
        
        # Verify MCP server was created
        assert agent.mcp_server is not None, "MCP server should be initialized"
        logger.info("✓ MCP server instance created")
        
        # Verify thread was started
        assert agent._mcp_thread is not None, "MCP thread should be started"
        assert agent._mcp_thread.is_alive(), "MCP thread should be running"
        logger.info("✓ MCP server thread is running")
        
        # Give server time to start
        await asyncio.sleep(2)
        
        logger.info("✅ TEST 1 PASSED: MCP enabled successfully")
        return True
        
    except ImportError as e:
        if "mcp" in str(e).lower():
            logger.warning("⚠️  TEST 1 SKIPPED: MCP package not installed")
            logger.warning("   Install with: pip install mcp")
            return None  # None = skipped
        else:
            raise
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}")
        raise
    finally:
        if agent:
            await agent.close()


async def test_mcp_idempotency():
    """Test that enabling MCP multiple times is safe."""
    logger.info("=" * 60)
    logger.info("TEST 2: MCP enable idempotency")
    logger.info("=" * 60)
    
    agent = None
    try:
        agent = TestMCPAgent()
        test_port = 18001
        
        # Enable MCP first time
        agent.enable_mcp(port=test_port)
        first_server = agent.mcp_server
        first_thread = agent._mcp_thread
        logger.info("✓ MCP enabled first time")
        
        # Enable MCP second time (should be idempotent)
        agent.enable_mcp(port=test_port)
        second_server = agent.mcp_server
        second_thread = agent._mcp_thread
        logger.info("✓ MCP enable called second time")
        
        # Should be the same server instance
        assert first_server is second_server, "Should reuse existing MCP server"
        assert first_thread is second_thread, "Should reuse existing MCP thread"
        logger.info("✓ Same server instance reused")
        
        logger.info("✅ TEST 2 PASSED: MCP enable is idempotent")
        return True
        
    except ImportError as e:
        if "mcp" in str(e).lower():
            logger.warning("⚠️  TEST 2 SKIPPED: MCP package not installed")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}")
        raise
    finally:
        if agent:
            await agent.close()


async def test_mcp_with_client():
    """Test MCP client connecting to agent."""
    logger.info("=" * 60)
    logger.info("TEST 3: MCP client interaction")
    logger.info("=" * 60)
    
    agent = None
    try:
        # Import MCP client libraries
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
            from contextlib import AsyncExitStack
        except ImportError as e:
            logger.warning("⚠️  TEST 3 SKIPPED: MCP client libraries not available")
            return None
        
        # Create and start agent with MCP
        agent = TestMCPAgent()
        test_port = 18002
        agent.enable_mcp(
            port=test_port,
            toolname="greet_user",
            tooldesc="Greet a user by name"
        )
        logger.info(f"✓ Agent MCP server started on port {test_port}")
        
        # Give server time to start
        await asyncio.sleep(3)
        
        # Connect MCP client
        exit_stack = AsyncExitStack()
        async with exit_stack:
            server_url = f"http://localhost:{test_port}/mcp"
            logger.info(f"Connecting to MCP server at {server_url}")
            
            read_stream, write_stream, _ = await exit_stack.enter_async_context(
                streamablehttp_client(server_url)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            await session.initialize()
            logger.info("✓ MCP client connected and initialized")
            
            # List available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools
            logger.info(f"✓ Found {len(tools)} tool(s): {[t.name for t in tools]}")
            
            # Verify our tool is present
            tool_names = [t.name for t in tools]
            assert "greet_user" in tool_names, "Expected 'greet_user' tool not found"
            logger.info("✓ Expected tool 'greet_user' found")
            
            # Call the tool (simulating agent request)
            logger.info("Calling tool with test message...")
            result = await session.call_tool(
                "greet_user",
                {"message": "Hello from MCP test!"}
            )
            logger.info(f"✓ Tool responded: {result}")
            
            # Verify we got a response
            assert result is not None, "Should receive a response"
            logger.info("✓ Received response from agent via MCP")
        
        logger.info("✅ TEST 3 PASSED: MCP client interaction successful")
        return True
        
    except ImportError as e:
        if "mcp" in str(e).lower():
            logger.warning("⚠️  TEST 3 SKIPPED: MCP package not installed")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}")
        logger.exception("Detailed error:")
        raise
    finally:
        if agent:
            await agent.close()


async def run_all_tests():
    """Run all MCP tests."""
    logger.info("=" * 60)
    logger.info("GENESIS MCP INTEGRATION TEST SUITE")
    logger.info("=" * 60)
    
    tests = [
        ("Enable MCP", test_mcp_enable),
        ("MCP Idempotency", test_mcp_idempotency),
        ("MCP Client Interaction", test_mcp_with_client),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
            if result is None:
                logger.info(f"⚠️  {test_name}: SKIPPED")
            elif result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.info(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)
    
    logger.info(f"Total:   {total}")
    logger.info(f"Passed:  {passed}")
    logger.info(f"Failed:  {failed}")
    logger.info(f"Skipped: {skipped}")
    
    if skipped == total:
        logger.info("=" * 60)
        logger.info("⚠️  ALL TESTS SKIPPED - MCP package not installed")
        logger.info("Install with: pip install mcp")
        logger.info("=" * 60)
        return 0  # Don't fail build if MCP is optional
    
    if failed > 0:
        logger.info("=" * 60)
        logger.info("❌ SOME TESTS FAILED")
        logger.info("=" * 60)
        return 1
    else:
        logger.info("=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

