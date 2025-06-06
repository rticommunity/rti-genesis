#!/usr/bin/env python3
"""
Debug script to check what capabilities agents are advertising
"""

import asyncio
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.monitored_interface import MonitoredInterface

class CapabilityDebugInterface(MonitoredInterface):
    """Interface to debug agent capabilities"""
    
    def __init__(self):
        super().__init__(
            interface_name="CapabilityDebug",
            service_name="OpenAIAgent"
        )
    
    async def debug_capabilities(self, timeout_seconds: float = 15.0) -> bool:
        """Debug what capabilities agents are advertising"""
        print(f"🔍 Monitoring agent capabilities for {timeout_seconds} seconds...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.available_agents:
                print(f"\n📊 Found {len(self.available_agents)} agent(s):")
                print("=" * 60)
                
                for agent_id, agent_info in self.available_agents.items():
                    name = agent_info.get('prefered_name', 'Unknown')
                    service = agent_info.get('service_name', 'Unknown')
                    agent_type = agent_info.get('agent_type', 'Unknown')
                    description = agent_info.get('description', 'No description')
                    
                    print(f"🤖 Agent: {name}")
                    print(f"   ID: {agent_id}")
                    print(f"   Service: {service}")
                    print(f"   Type: {agent_type}")
                    print(f"   Description: {description}")
                    
                    # Check for capability info
                    capabilities = agent_info.get('capabilities', [])
                    specializations = agent_info.get('specializations', [])
                    classification_tags = agent_info.get('classification_tags', [])
                    
                    print(f"   Capabilities: {capabilities}")
                    print(f"   Specializations: {specializations}")  
                    print(f"   Classification Tags: {classification_tags}")
                    
                    # Debug all fields
                    print(f"   All fields: {list(agent_info.keys())}")
                    print("-" * 40)
                
                return True
            
            await asyncio.sleep(1.0)
        
        print(f"❌ No agents found within {timeout_seconds} seconds")
        return False

async def main():
    """Main entry point"""
    print("🐛 Agent Capability Debug Tool")
    print("=" * 50)
    
    interface = CapabilityDebugInterface()
    
    try:
        await interface.debug_capabilities(timeout_seconds=20.0)
    finally:
        await interface.close()
        print("\n🐛 Debug completed")

if __name__ == "__main__":
    asyncio.run(main()) 