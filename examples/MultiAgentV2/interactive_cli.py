#!/usr/bin/env python3
"""
Interactive CLI for Genesis Multi-Agent Demo

Provides a smooth conversational interface for chatting with available agents.
Shows real-time agent discovery, service grouping, and user selection.
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional, Dict, List, Any
from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging to be less verbose for better user experience
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class InteractiveChatCLI(MonitoredInterface):
    """
    Interactive chat interface for conversing with available agents.
    
    Features:
    - Real-time agent discovery
    - Service grouping (multiple agents offering same service)
    - User selection interface
    - Smooth conversation flow
    """
    
    def __init__(self):
        super().__init__(
            interface_name="InteractiveChatCLI",
            service_name="InteractiveChatService"
        )
        self.connected = False
        self.selected_agent_name = "Agent"
        self.selected_service_name = "Unknown"
        self.conversation_history = []
        
    def group_agents_by_service(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group discovered agents by their service names (like DDS RPC)"""
        service_groups = {}
        
        for agent_id, agent_info in self.available_agents.items():
            service_name = agent_info.get('service_name', 'UnknownService')
            if service_name not in service_groups:
                service_groups[service_name] = []
            service_groups[service_name].append({
                'agent_id': agent_id,
                'name': agent_info.get('prefered_name', 'Unknown'),
                'service_name': service_name,
                'agent_info': agent_info
            })
        
        return service_groups
    
    def display_agent_discovery_results(self) -> Dict[str, List[Dict[str, Any]]]:
        """Display discovered agents grouped by service name"""
        service_groups = self.group_agents_by_service()
        
        print("\n📊 Discovery Results:")
        
        if not service_groups:
            print("   No agents discovered yet")
            return service_groups
        
        # Count total agents and services
        total_agents = sum(len(agents) for agents in service_groups.values())
        total_services = len(service_groups)
        
        print(f"   Found {total_agents} agent(s) offering {total_services} service(s)")
        print("   ✅ Discovered agents:")
        
        # Display each service group
        agent_counter = 1
        for service_name, agents in service_groups.items():
            if len(agents) == 1:
                # Single agent for this service
                agent = agents[0]
                print(f"      {agent_counter}. {agent['name']} ({agent['agent_id'][:8]}...)")
                print(f"         Service: {service_name}")
                print(f"         Status: available")
            else:
                # Multiple agents for this service (load balanced)
                print(f"      {service_name} service ({len(agents)} instances):")
                for i, agent in enumerate(agents):
                    print(f"      {agent_counter}. {agent['name']} ({agent['agent_id'][:8]}...)")
                    print(f"         Instance: {i+1}/{len(agents)}")
                    print(f"         Status: available")
                    agent_counter += 1
                    continue
            agent_counter += 1
        
        return service_groups
    
    def get_user_agent_selection(self, service_groups: Dict[str, List[Dict[str, Any]]]) -> Optional[tuple]:
        """Let user select an agent from the available services"""
        if not service_groups:
            return None
        
        # Create a flat list for easy selection
        all_agents = []
        for service_name, agents in service_groups.items():
            all_agents.extend(agents)
        
        if len(all_agents) == 1:
            # Only one agent available, auto-select
            agent = all_agents[0]
            print(f"\n🎯 Auto-selecting only available agent: {agent['name']}")
            return (agent['agent_info'], agent['service_name'], agent['name'])
        
        # Multiple agents available, let user choose
        print(f"\n🤔 Please select an agent to chat with:")
        for i, agent in enumerate(all_agents, 1):
            print(f"   {i}. {agent['name']} (Service: {agent['service_name']})")
        
        while True:
            try:
                choice = input(f"\nEnter your choice (1-{len(all_agents)}): ").strip()
                
                if choice.lower() in ['quit', 'exit', 'q']:
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(all_agents):
                    selected_agent = all_agents[choice_num - 1]
                    return (selected_agent['agent_info'], selected_agent['service_name'], selected_agent['name'])
                else:
                    print(f"❌ Please enter a number between 1 and {len(all_agents)}")
                    
            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n👋 Selection cancelled")
                return None
    
    async def start_chat_session(self):
        """Start the interactive chat session with proper agent discovery and selection"""
        print("🔍 Discovering agents...")
        
        # Wait for agent discovery with proper timing
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
        
        # DEBUG: Print raw discovered agent data
        print(f"\n🔍 DEBUG: Raw discovered agents: {self.available_agents}")
        
        # Display discovery results
        service_groups = self.display_agent_discovery_results()
        
        # Let user select an agent
        selection = self.get_user_agent_selection(service_groups)
        if not selection:
            print("👋 No agent selected. Exiting...")
            return False
        
        agent_info, service_name, agent_name = selection
        
        print(f"\n🔗 Connecting to {agent_name}...")
        print(f"   Service: {service_name}")
        print(f"🔍 DEBUG: Full agent_info: {agent_info}")
        
        try:
            print(f"🔍 DEBUG: Before connection - self.requester: {self.requester}")
            print(f"🔍 DEBUG: Before connection - self._connected_agent_id: {getattr(self, '_connected_agent_id', 'Not set')}")
            
            self.connected = await self.connect_to_agent(service_name, timeout_seconds=10.0)
            
            print(f"🔍 DEBUG: After connection - self.connected: {self.connected}")
            print(f"🔍 DEBUG: After connection - self.requester: {self.requester}")
            print(f"🔍 DEBUG: After connection - self._connected_agent_id: {getattr(self, '_connected_agent_id', 'Not set')}")
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
        
        if not self.connected:
            print("❌ Failed to connect to agent.")
            return False
        
        # Store selected agent details
        self.selected_agent_name = agent_name
        self.selected_service_name = service_name
        
        print(f"✅ Connected to {self.selected_agent_name}!")
        print("")
        return True
    
    async def chat_loop(self):
        """Main interactive chat loop"""
        print("💬 " + "="*50)
        print(f"   Welcome to Genesis Interactive Chat!")
        print(f"   Connected to: {self.selected_agent_name}")
        print(f"   Service: {self.selected_service_name}")
        print("💬 " + "="*50)
        print("")
        print("📝 You can:")
        print("   • Ask questions or have conversations")
        print("   • Request calculations (e.g., 'What is 123 + 456?')")
        print("   • Ask for jokes or creative content")
        print("   • Type 'quit', 'exit', or 'bye' to end")
        print("")
        print("🚀 Let's chat! (Type your message and press Enter)")
        print("")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Check for exit commands
                if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("")
                    print("👋 Thanks for chatting! Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Show thinking indicator
                print(f"{self.selected_agent_name}: Thinking... 🤔")
                
                # Send request to agent
                try:
                    response = await self.send_request(
                        {"message": user_input}, 
                        timeout_seconds=30.0
                    )
                    
                    if response and response.get('status') == 0:
                        agent_response = response.get('message', 'No response')
                        
                        # Clear the "thinking" line and show response
                        print(f"\r{self.selected_agent_name}: {agent_response}")
                        print("")
                        
                        # Store in conversation history
                        self.conversation_history.append({
                            'user': user_input,
                            'agent': agent_response
                        })
                        
                    else:
                        print(f"\r❌ Agent error: {response.get('message', 'Unknown error')}")
                        print("")
                        
                except asyncio.TimeoutError:
                    print(f"\r⏰ Request timed out. The agent might be busy.")
                    print("")
                except Exception as e:
                    print(f"\r❌ Error sending request: {e}")
                    print("")
                    
            except KeyboardInterrupt:
                print("")
                print("👋 Chat interrupted. Goodbye!")
                break
            except EOFError:
                print("")
                print("👋 Chat ended. Goodbye!")
                break
    
    def print_conversation_summary(self):
        """Print a summary of the conversation"""
        if self.conversation_history:
            print("")
            print("📊 Conversation Summary:")
            print("=" * 30)
            for i, exchange in enumerate(self.conversation_history, 1):
                print(f"{i}. You: {exchange['user'][:50]}{'...' if len(exchange['user']) > 50 else ''}")
                print(f"   {self.selected_agent_name}: {exchange['agent'][:50]}{'...' if len(exchange['agent']) > 50 else ''}")
                print("")

async def main():
    """Main entry point for interactive chat"""
    print("🚀 Genesis Interactive Chat Starting...")
    print("")
    
    # Create CLI instance
    cli = InteractiveChatCLI()
    
    try:
        # Start chat session
        if await cli.start_chat_session():
            # Run chat loop
            await cli.chat_loop()
            
            # Show conversation summary
            cli.print_conversation_summary()
        
    except KeyboardInterrupt:
        print("")
        print("👋 Interactive chat interrupted. Shutting down...")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        print("🧹 Closing connection...")
        await cli.close()
        print("✅ Interactive chat closed successfully.")

def handle_signal(signum, frame):
    """Handle interrupt signals gracefully"""
    print("")
    print("👋 Signal received. Shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Interactive chat terminated.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1) 