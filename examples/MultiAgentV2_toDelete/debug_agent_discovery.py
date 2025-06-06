#!/usr/bin/env python3
"""
Debug Agent Discovery

This script connects to running agents and checks their discovery state.
"""

import asyncio
import logging
import sys
import os

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentDiscoveryDebugger(MonitoredInterface):
    """Debug interface to check agent discovery"""
    
    def __init__(self):
        super().__init__(interface_name="DiscoveryDebugger", service_name="OpenAIAgent")
        
    async def debug_discovery(self):
        """Check what agents are discovered"""
        logger.info("🔍 Checking agent discovery...")
        
        # Wait for discovery
        await asyncio.sleep(5)
        
        logger.info(f"📊 Found {len(self.available_agents)} agents:")
        
        for agent_id, agent_info in self.available_agents.items():
            logger.info(f"  🤖 Agent: {agent_info.get('prefered_name', 'Unknown')}")
            logger.info(f"     ID: {agent_id}")
            logger.info(f"     Service: {agent_info.get('service_name', 'Unknown')}")
            logger.info(f"     Description: {agent_info.get('description', 'None')}")
            
            # Try to extract capabilities/specializations
            capabilities = []
            specializations = []
            
            if 'capabilities' in agent_info:
                capabilities = agent_info['capabilities']
            if 'specializations' in agent_info:
                specializations = agent_info['specializations']
                
            logger.info(f"     Capabilities: {capabilities}")
            logger.info(f"     Specializations: {specializations}")
            logger.info("     " + "-"*40)
            
        return len(self.available_agents)

async def main():
    """Main debug function"""
    debugger = AgentDiscoveryDebugger()
    
    try:
        agent_count = await debugger.debug_discovery()
        
        if agent_count >= 2:
            logger.info("✅ Discovery working - found expected agents")
        else:
            logger.warning(f"⚠️ Only found {agent_count} agents")
            
        return 0
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        return 1
    finally:
        await debugger.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 