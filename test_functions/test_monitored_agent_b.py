#!/usr/bin/env python3
"""
Test MonitoredAgent B - runs as separate process for agent-to-agent communication testing.
"""

import asyncio
import logging
import sys
import os
import time
import uuid
from typing import Dict, Any

print("🚀 PRINT: Agent B Script starting - before any imports")

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

print("🚀 PRINT: Agent B MonitoredAgent imported")

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 PRINT: Agent B Logging configured")
logger.info("🚀 LOGGER: Agent B Initial logger test - if you see this, logging is working")

class TestMonitoredAgentB(MonitoredAgent):
    """Test agent B that responds to requests from other agents"""
    
    def __init__(self):
        print("🚀 PRINT: TestMonitoredAgentB.__init__() starting")
        logger.info("🚀 TRACE: TestMonitoredAgentB.__init__() starting")
        super().__init__(
            agent_name="TestMonitoredAgentB",
            base_service_name="TestServiceB",
            agent_type="SPECIALIZED_AGENT",
            agent_id="test_monitored_agent_b",
            enable_agent_communication=True
        )
        print("✅ PRINT: TestMonitoredAgentB.__init__() completed")
        logger.info("✅ TRACE: TestMonitoredAgentB.__init__() completed")
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process requests locally"""
        print(f"🔄 PRINT: TestMonitoredAgentB.process_request() called with: {request}")
        logger.info(f"🔄 TRACE: TestMonitoredAgentB.process_request() called with: {request}")
        message = request.get('message', '')
        result = {
            'message': f"Agent B processed: {message}",
            'status': 0
        }
        print(f"📤 PRINT: TestMonitoredAgentB.process_request() returning: {result}")
        logger.info(f"📤 TRACE: TestMonitoredAgentB.process_request() returning: {result}")
        return result
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests from other agents"""
        print(f"🤝 PRINT: TestMonitoredAgentB.process_agent_request() called with: {request}")
        logger.info(f"🤝 TRACE: TestMonitoredAgentB.process_agent_request() called with: {request}")
        message = request.get('message', '')
        conversation_id = request.get('conversation_id', '')
        
        print(f"📥 PRINT: Agent B received agent request: {message}")
        logger.info(f"📥 TRACE: Agent B received agent request: {message}")
        
        result = {
            'message': f"Agent B handled agent request: {message}",
            'status': 0,
            'conversation_id': conversation_id
        }
        print(f"📤 PRINT: TestMonitoredAgentB.process_agent_request() returning: {result}")
        logger.info(f"📤 TRACE: TestMonitoredAgentB.process_agent_request() returning: {result}")
        return result

    async def run(self):
        """Custom run method that tests agent communication"""
        try:
            print("🎬 PRINT: TestMonitoredAgentB.run() starting")
            logger.info("🎬 TRACE: TestMonitoredAgentB.run() starting")
            
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
            print(f"📋 PRINT: Agent B discovered: {list(discovered_agents.keys())}")
            logger.info(f"📋 TRACE: Agent B discovered: {list(discovered_agents.keys())}")
            print(f"📋 PRINT: Full discovered agents data: {discovered_agents}")
            logger.info(f"📋 TRACE: Full discovered agents data: {discovered_agents}")
            
            # Now run the normal agent loop
            print("🔄 PRINT: Agent B running... (Ctrl+C to exit)")
            logger.info("🔄 TRACE: Agent B running... (Ctrl+C to exit)")
            
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
    print("🎬 PRINT: === Starting Test MonitoredAgent B ===")
    logger.info("🎬 TRACE: === Starting Test MonitoredAgent B ===")
    
    print("🏗️ PRINT: Creating TestMonitoredAgentB instance...")
    logger.info("🏗️ TRACE: Creating TestMonitoredAgentB instance...")
    agent_b = TestMonitoredAgentB()
    print("✅ PRINT: TestMonitoredAgentB instance created")
    logger.info("✅ TRACE: TestMonitoredAgentB instance created")
    
    try:
        print("🚀 PRINT: Starting agent's main loop...")
        logger.info("🚀 TRACE: Starting agent's main loop...")
        # Start the agent's main loop
        await agent_b.run()
        print("✅ PRINT: Agent's main loop completed")
        logger.info("✅ TRACE: Agent's main loop completed")
        
    except KeyboardInterrupt:
        print("🛑 PRINT: KeyboardInterrupt in main(), shutting down Agent B...")
        logger.info("🛑 TRACE: KeyboardInterrupt in main(), shutting down Agent B...")
    except Exception as e:
        print(f"💥 PRINT: Exception in main(): {e}")
        logger.error(f"💥 TRACE: Exception in main(): {e}")
        import traceback
        print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
        logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
    finally:
        print("🧹 PRINT: Cleaning up Agent B...")
        logger.info("🧹 TRACE: Cleaning up Agent B...")
        await agent_b.close()
        print("✅ PRINT: Agent B cleanup completed")
        logger.info("✅ TRACE: Agent B cleanup completed")

if __name__ == "__main__":
    print("🎬 PRINT: Agent B Script starting, about to run main()")
    logger.info("🎬 TRACE: Agent B Script starting, about to run main()")
    asyncio.run(main())
    print("✅ PRINT: Agent B Script completed")
    logger.info("✅ TRACE: Agent B Script completed") 