#!/usr/bin/env python3
"""
Test MonitoredAgent A - runs as separate process for agent-to-agent communication testing.
"""

import asyncio
import logging
import sys
import os
import time
import uuid
from typing import Dict, Any

print("🚀 PRINT: Script starting - before any imports")

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

print("🚀 PRINT: MonitoredAgent imported")

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 PRINT: Logging configured")
logger.info("🚀 LOGGER: Initial logger test - if you see this, logging is working")

class TestMonitoredAgentA(MonitoredAgent):
    """Test agent A that can send requests to other agents"""
    
    def __init__(self):
        print("🚀 PRINT: TestMonitoredAgentA.__init__() starting")
        logger.info("🚀 TRACE: TestMonitoredAgentA.__init__() starting")
        super().__init__(
            agent_name="TestMonitoredAgentA",
            base_service_name="TestServiceA",
            agent_type="AGENT",
            enable_agent_communication=True
        )
        print("✅ PRINT: TestMonitoredAgentA.__init__() completed")
        logger.info("✅ TRACE: TestMonitoredAgentA.__init__() completed")
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process requests and potentially route to other agents"""
        print(f"🔄 PRINT: TestMonitoredAgentA.process_request() called with: {request}")
        logger.info(f"🔄 TRACE: TestMonitoredAgentA.process_request() called with: {request}")
        message = request.get('message', '')
        
        if 'route_to_b' in message.lower():
            # Test routing to Agent B
            print("🔀 PRINT: Routing request to Agent B")
            logger.info("🔀 TRACE: Routing request to Agent B")
            
            # Wait for Agent B to be discovered
            print("⏳ PRINT: Waiting for Agent B to be discovered...")
            logger.info("⏳ TRACE: Waiting for Agent B to be discovered...")
            agent_b_found = await self.wait_for_agent("test_monitored_agent_b", timeout_seconds=10.0)
            print(f"🔍 PRINT: Agent B discovery result: {agent_b_found}")
            logger.info(f"🔍 TRACE: Agent B discovery result: {agent_b_found}")
            
            if not agent_b_found:
                print("❌ PRINT: Agent B not found")
                logger.warning("❌ TRACE: Agent B not found")
                return {
                    'message': 'Agent B not found',
                    'status': -1
                }
            
            # Send request to Agent B
            print("📤 PRINT: Sending request to Agent B...")
            logger.info("📤 TRACE: Sending request to Agent B...")
            response = await self.send_agent_request(
                target_agent_id="test_monitored_agent_b",
                message="Hello from Agent A",
                conversation_id=request.get('conversation_id')
            )
            print(f"📥 PRINT: Response from Agent B: {response}")
            logger.info(f"📥 TRACE: Response from Agent B: {response}")
            
            if response:
                return {
                    'message': f"Agent B replied: {response.get('message', 'No message')}",
                    'status': 0
                }
            else:
                return {
                    'message': 'Failed to get response from Agent B',
                    'status': -1
                }
        
        # Handle request locally
        print("🏠 PRINT: Handling request locally")
        logger.info("🏠 TRACE: Handling request locally")
        return {
            'message': f"Agent A processed: {message}",
            'status': 0
        }
    
    async def run(self):
        """Custom run method that tests agent communication"""
        try:
            print("🎬 PRINT: TestMonitoredAgentA.run() starting")
            logger.info("🎬 TRACE: TestMonitoredAgentA.run() starting")
            
            # Announce presence
            print("📢 PRINT: Announcing agent presence...")
            logger.info("📢 TRACE: Announcing agent presence...")
            await self.announce_self()
            print("✅ PRINT: Agent presence announced")
            logger.info("✅ TRACE: Agent presence announced")
            
            # Explicitly publish agent capability
            print("📢 PRINT: Publishing agent capability...")
            logger.info("📢 TRACE: Publishing agent capability...")
            if hasattr(self, 'agent_communication') and self.agent_communication:
                self.agent_communication.publish_agent_capability()
                print("✅ PRINT: Agent capability published")
                logger.info("✅ TRACE: Agent capability published")
            else:
                print("⚠️ PRINT: No agent communication available")
                logger.warning("⚠️ TRACE: No agent communication available")
            
            # Wait for initialization
            print("⏳ PRINT: Waiting 2 seconds for initialization...")
            logger.info("⏳ TRACE: Waiting 2 seconds for initialization...")
            await asyncio.sleep(2)
            print("✅ PRINT: Initialization wait completed")
            logger.info("✅ TRACE: Initialization wait completed")
            
            # Test agent discovery
            print("🔍 PRINT: Waiting 5 seconds for other agents to be discovered...")
            logger.info("🔍 TRACE: Waiting 5 seconds for other agents to be discovered...")
            await asyncio.sleep(5)
            print("✅ PRINT: Discovery wait completed")
            logger.info("✅ TRACE: Discovery wait completed")
            
            discovered_agents = self.get_discovered_agents()
            print(f"📋 PRINT: Agent A discovered: {list(discovered_agents.keys())}")
            logger.info(f"📋 TRACE: Agent A discovered: {list(discovered_agents.keys())}")
            print(f"📋 PRINT: Full discovered agents data: {discovered_agents}")
            logger.info(f"📋 TRACE: Full discovered agents data: {discovered_agents}")
            
            # Test direct communication if Agent B is found
            if "test_monitored_agent_b" in discovered_agents:
                print("🔗 PRINT: Testing direct communication with Agent B")
                logger.info("🔗 TRACE: Testing direct communication with Agent B")
                
                print("📤 PRINT: About to send direct test message...")
                logger.info("📤 TRACE: About to send direct test message...")
                response = await self.send_agent_request(
                    target_agent_id="test_monitored_agent_b",
                    message="Direct test message from Agent A",
                    timeout_seconds=5.0
                )
                print(f"📥 PRINT: Direct communication response: {response}")
                logger.info(f"📥 TRACE: Direct communication response: {response}")
                
                if response:
                    print(f"✅ PRINT: Direct communication successful: {response['message']}")
                    logger.info(f"✅ TRACE: Direct communication successful: {response['message']}")
                else:
                    print("❌ PRINT: Direct communication failed")
                    logger.error("❌ TRACE: Direct communication failed")
            else:
                print("⚠️ PRINT: Agent B not discovered yet")
                logger.info("⚠️ TRACE: Agent B not discovered yet")
            
            # Now run the normal agent loop
            print("🔄 PRINT: Agent A running... (Ctrl+C to exit)")
            logger.info("🔄 TRACE: Agent A running... (Ctrl+C to exit)")
            
            # Keep the event loop running (agent requests are handled by listeners)
            print("⏳ PRINT: Creating shutdown event and waiting...")
            logger.info("⏳ TRACE: Creating shutdown event and waiting...")
            shutdown_event = asyncio.Event()
            print("⏳ PRINT: About to wait for shutdown event (this should block)...")
            logger.info("⏳ TRACE: About to wait for shutdown event (this should block)...")
            await shutdown_event.wait()
            print("🛑 PRINT: Shutdown event received (this should not print unless interrupted)")
            logger.info("🛑 TRACE: Shutdown event received (this should not print unless interrupted)")
                
        except KeyboardInterrupt:
            print(f"\n🛑 PRINT: KeyboardInterrupt received, shutting down {self.agent_name}...")
            logger.info(f"\n🛑 TRACE: KeyboardInterrupt received, shutting down {self.agent_name}...")
            await self.close()
            sys.exit(0)
        except Exception as e:
            print(f"💥 PRINT: Exception in run(): {e}")
            logger.error(f"💥 TRACE: Exception in run(): {e}")
            import traceback
            print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
            logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
            raise

async def main():
    """Main function"""
    print("🎬 PRINT: === Starting Test MonitoredAgent A ===")
    logger.info("🎬 TRACE: === Starting Test MonitoredAgent A ===")
    
    print("🏗️ PRINT: Creating TestMonitoredAgentA instance...")
    logger.info("🏗️ TRACE: Creating TestMonitoredAgentA instance...")
    agent_a = TestMonitoredAgentA()
    print("✅ PRINT: TestMonitoredAgentA instance created")
    logger.info("✅ TRACE: TestMonitoredAgentA instance created")
    
    try:
        print("🚀 PRINT: Starting agent's main loop...")
        logger.info("🚀 TRACE: Starting agent's main loop...")
        # Start the agent's main loop (which includes our test)
        await agent_a.run()
        print("✅ PRINT: Agent's main loop completed")
        logger.info("✅ TRACE: Agent's main loop completed")
        
    except KeyboardInterrupt:
        print("🛑 PRINT: KeyboardInterrupt in main(), shutting down Agent A...")
        logger.info("🛑 TRACE: KeyboardInterrupt in main(), shutting down Agent A...")
    except Exception as e:
        print(f"💥 PRINT: Exception in main(): {e}")
        logger.error(f"💥 TRACE: Exception in main(): {e}")
        import traceback
        print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
        logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
    finally:
        print("🧹 PRINT: Cleaning up Agent A...")
        logger.info("🧹 TRACE: Cleaning up Agent A...")
        await agent_a.close()
        print("✅ PRINT: Agent A cleanup completed")
        logger.info("✅ TRACE: Agent A cleanup completed")

if __name__ == "__main__":
    print("🎬 PRINT: Script starting, about to run main()")
    logger.info("🎬 TRACE: Script starting, about to run main()")
    asyncio.run(main())
    print("✅ PRINT: Script completed")
    logger.info("✅ TRACE: Script completed") 