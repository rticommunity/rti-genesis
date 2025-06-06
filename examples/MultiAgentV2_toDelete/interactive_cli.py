#!/usr/bin/env python3
"""
Interactive CLI for Genesis Multi-Agent Demo V2

Generic multi-agent interface that discovers agents dynamically and allows
users to select which agent to connect to based on their advertised capabilities.

Features:
- Dynamic agent discovery based on advertised capabilities
- User selection of which agent to connect to  
- Generic conversation interface
- No hardcoded agent types

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional, Dict, Any, List
from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging to be less verbose for better user experience
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class MultiAgentInteractiveCLI(MonitoredInterface):
    """
    Interactive CLI supporting multiple agents for multi-agent demonstration.
    
    Features:
    - Discovers agents dynamically based on their advertised capabilities
    - Allows user selection of which agent to connect to
    - Provides smooth conversational interface
    - No hardcoded agent knowledge
    """
    
    def __init__(self):
        super().__init__(interface_name="MultiAgentChatInterface", service_name="InteractiveChat")
        
        # Agent management
        self.connected_agent_name: Optional[str] = None
        self.connected_service_name: Optional[str] = None
        self.conversation_history: List[Dict[str, str]] = []
        
        logger.debug("MultiAgentInteractiveCLI initialized")
    
    def get_agent_capabilities(self, agent_info: Dict[str, Any]) -> List[str]:
        """Extract capabilities from agent info"""
        capabilities = []
        
        # Check for capabilities in the agent info
        if 'capabilities' in agent_info:
            caps = agent_info['capabilities']
            if isinstance(caps, list):
                capabilities.extend(caps)
            elif isinstance(caps, str):
                capabilities.append(caps)
        
        # Check for specializations
        if 'specializations' in agent_info:
            specs = agent_info['specializations']
            if isinstance(specs, list):
                capabilities.extend(specs)
            elif isinstance(specs, str):
                capabilities.append(specs)
        
        # If no explicit capabilities, infer from service name
        service_name = agent_info.get('service_name', '')
        if service_name and not capabilities:
            capabilities.append(service_name.replace('Service', '').lower())
        
        return capabilities
    
    def display_agent_selection(self) -> List[Dict[str, Any]]:
        """Display available agents and return selection list"""
        print("\n📊 Discovery Results:")
        print("=" * 60)
        
        available_agents = []
        option_num = 1
        
        for agent_id, agent_info in self.available_agents.items():
            agent_name = agent_info.get('prefered_name', 'Unknown')
            service_name = agent_info.get('service_name', 'Unknown')
            capabilities = self.get_agent_capabilities(agent_info)
            
            print(f"🤖 {option_num}. {agent_name}")
            print(f"   ID: {agent_id[:12]}...")
            print(f"   Service: {service_name}")
            
            if capabilities:
                caps_str = ", ".join(capabilities[:3])  # Show first 3 capabilities
                if len(capabilities) > 3:
                    caps_str += f" (+{len(capabilities)-3} more)"
                print(f"   Capabilities: {caps_str}")
            else:
                print(f"   Capabilities: General purpose")
            
            print()
            
            available_agents.append({
                "id": agent_id,
                "name": agent_name,
                "service_name": service_name,
                "capabilities": capabilities,
                "info": agent_info
            })
            option_num += 1
        
        return available_agents
    
    async def start_chat_session(self):
        """Start the interactive chat session with agent selection"""
        print("🔍 Discovering agents...")
        
        # Wait for agent discovery
        timeout = 15.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.available_agents:
                break
            await asyncio.sleep(0.5)
        
        if not self.available_agents:
            print("❌ No agents discovered within 15 seconds.")
            print("   Make sure agents are running!")
            return False
        
        # Display available agents
        available_agents = self.display_agent_selection()
        
        # Auto-select if only one agent available
        if len(available_agents) == 1:
            selected_agent = available_agents[0]
            print(f"🎯 Auto-selecting only available agent: {selected_agent['name']}")
        else:
            # User selection
            print("🎯 Agent Selection:")
            print("=" * 50)
            print("Choose which agent to connect to:")
            print()
            
            while True:
                try:
                    choice = input("Enter agent number (1-{}): ".format(len(available_agents)))
                    agent_index = int(choice) - 1
                    if 0 <= agent_index < len(available_agents):
                        selected_agent = available_agents[agent_index]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(available_agents)}")
                except ValueError:
                    print("Please enter a valid number")
                except KeyboardInterrupt:
                    print("\n👋 Selection cancelled")
                    return False
        
        # Connect to selected agent
        print(f"\n🔗 Connecting to {selected_agent['name']}...")
        print(f"   Service: {selected_agent['service_name']}")
        
        success = await self.connect_to_agent(selected_agent['service_name'])
        
        if success:
            self.connected_agent_name = selected_agent['name']
            self.connected_service_name = selected_agent['service_name']
            print(f"✅ Connected to {selected_agent['name']}!")
            
            # Start conversation
            await self._run_conversation_loop(selected_agent)
            return True
        else:
            print(f"❌ Failed to connect to {selected_agent['name']}")
            return False
    
    async def _run_conversation_loop(self, selected_agent: Dict[str, Any]):
        """Run the main conversation loop"""
        print(f"\n💬 {'='*50}")
        print(f"   Welcome to Genesis Multi-Agent Chat!")
        print(f"   Connected to: {self.connected_agent_name}")
        print(f"   Service: {self.connected_service_name}")
        print(f"💬 {'='*50}")
        
        # Show usage tips based on capabilities
        capabilities = selected_agent.get('capabilities', [])
        if capabilities:
            print(f"\n📝 {self.connected_agent_name} Capabilities:")
            for cap in capabilities[:5]:  # Show first 5 capabilities
                print(f"   • {cap.title()}")
            if len(capabilities) > 5:
                print(f"   • ... and {len(capabilities)-5} more")
        else:
            print(f"\n📝 Chat Tips:")
            print("   • Ask questions or have conversations")
            print("   • The agent will use available tools and services")
        
        print("   • Type 'quit', 'exit', or 'bye' to end")
        print("\n🚀 Let's chat! (Type your message and press Enter)")
        
        while True:
            try:
                # Get user input
                user_input = input(f"\nYou: ").strip()
                
                if not user_input:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                    break
                
                # Send message to agent
                print(f"{self.connected_agent_name}: Thinking... 🤔")
                
                response = await self.send_request({
                    "message": user_input,
                    "conversation_id": f"chat_{int(time.time())}"
                })
                
                if response and response.get('status') == 0:
                    agent_response = response.get('message', 'No response')
                    print(f"{self.connected_agent_name}: {agent_response}")
                    
                    # Store in conversation history
                    self.conversation_history.append({
                        "user": user_input,
                        "agent": agent_response,
                        "timestamp": time.time()
                    })
                else:
                    print(f"{self.connected_agent_name}: Sorry, I encountered an error processing your message.")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                break
        
        print(f"\n👋 Thanks for chatting with {self.connected_agent_name}!")
        if self.conversation_history:
            print(f"📊 Conversation summary: {len(self.conversation_history)} exchanges")

async def main():
    """Main function"""
    # Set up graceful shutdown
    cli = None
    
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        if cli:
            asyncio.create_task(cli.close())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("🚀 Genesis Multi-Agent Interactive Chat Starting...")
        print()
        
        # Create and run CLI
        cli = MultiAgentInteractiveCLI()
        success = await cli.start_chat_session()
        
        if not success:
            print("❌ Failed to start chat session")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        if cli:
            print(f"\n🧹 Closing connection...")
            await cli.close()
            print("✅ Interactive chat closed successfully.")
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 