#!/usr/bin/env python3
"""
Interactive CLI - Genesis Multi-Agent Demo

Modern command-line interface for interacting with the Genesis multi-agent system.
Demonstrates agent discovery, delegation, and the @genesis_tool decorator system.

Features:
- Agent discovery and selection
- Real-time chat with agents
- Demo scenario suggestions
- Automatic delegation visualization
- Enhanced tracing and monitoring

"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional
import json

# Add Genesis library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging to be less verbose for CLI
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class MultiAgentCLI:
    """
    Interactive CLI for Genesis Multi-Agent system.
    
    Provides a user-friendly interface to interact with multiple agents,
    demonstrates automatic delegation, and showcases @genesis_tool functionality.
    """
    
    def __init__(self):
        self.interface = None
        self.connected_agent = None
        self.conversation_id = "multi_agent_demo"
        
    async def start(self):
        """Start the interactive CLI"""
        print("🚀 Genesis Multi-Agent Interactive Demo")
        print("=" * 50)
        print()
        print("🎯 This demo showcases:")
        print("   • @genesis_tool automatic tool discovery")
        print("   • Agent-to-agent delegation")
        print("   • Function service integration")
        print("   • Zero-boilerplate development")
        print()
        
        # Initialize Genesis interface
        print("🔧 Initializing Genesis interface...")
        self.interface = MonitoredInterface('MultiAgentDemo', 'InteractiveCLI')
        
        # Wait for agent discovery
        print("🔍 Discovering available agents...")
        await asyncio.sleep(5)  # Give agents time to start up
        
        # Show available agents
        await self.show_available_agents()
        
        # Main interaction loop
        await self.main_loop()

    async def show_available_agents(self):
        """Display available agents and their capabilities"""
        agents = self.interface.available_agents
        
        if not agents:
            print("❌ No agents discovered!")
            print("💡 Make sure agents are running:")
            print("   • PersonalAssistant (general agent)")
            print("   • WeatherAgent (@genesis_tool example)")
            print("   • Calculator Service (function service)")
            return
        
        print(f"✅ Discovered {len(agents)} agent(s):")
        print()
        
        for i, (agent_id, agent_info) in enumerate(agents.items(), 1):
            name = agent_info.get('prefered_name', 'Unknown')
            description = agent_info.get('description', 'No description')
            agent_type = agent_info.get('agent_type', 'Unknown')
            
            print(f"   {i}. {name}")
            print(f"      Type: {agent_type}")
            print(f"      Description: {description}")
            
            # Show capabilities if available
            capabilities = agent_info.get('capabilities', [])
            if capabilities:
                cap_str = ', '.join(capabilities[:3])
                if len(capabilities) > 3:
                    cap_str += f" (+{len(capabilities)-3} more)"
                print(f"      Capabilities: {cap_str}")
            
            print()

    async def main_loop(self):
        """Main interaction loop"""
        while True:
            try:
                # Get list of discovered agents for dynamic menu
                agents = list(self.interface.available_agents.items())
                
                print("🎯 Choose an option:")
                
                # Generate dynamic menu based on discovered agents
                if agents:
                    for i, (agent_id, agent_info) in enumerate(agents, 1):
                        name = agent_info.get('prefered_name', 'Unknown')
                        if name == 'PersonalAssistant':
                            print(f"   {i}. Connect to {name} (recommended)")
                        else:
                            print(f"   {i}. Connect to {name}")
                    
                    print(f"   {len(agents) + 1}. Show demo scenarios")
                    print(f"   {len(agents) + 2}. Refresh agent list")
                else:
                    print("   (No agents available)")
                    print("   1. Refresh agent list")
                
                print("   0. Exit")
                print()
                
                choice = input("Your choice: ").strip()
                
                if choice == "0":
                    break
                elif agents and choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(agents):
                        # Connect to the agent at the chosen position
                        agent_id, agent_info = agents[choice_num - 1]
                        preferred_name = agent_info.get('prefered_name', 'Unknown')
                        await self.connect_to_agent(preferred_name)
                    elif choice_num == len(agents) + 1:
                        self.show_demo_scenarios()
                    elif choice_num == len(agents) + 2:
                        await asyncio.sleep(2)
                        await self.show_available_agents()
                    else:
                        print("❌ Invalid choice. Please try again.")
                        print()
                elif not agents and choice == "1":
                    await asyncio.sleep(2)
                    await self.show_available_agents()
                else:
                    print("❌ Invalid choice. Please try again.")
                    print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                print()

    async def connect_to_agent(self, preferred_name: str):
        """Connect to a specific agent and start chat"""
        # Find agent by preferred name
        target_agent_info = None
        for agent_id, agent_info in self.interface.available_agents.items():
            if agent_info.get('prefered_name') == preferred_name:
                target_agent_info = agent_info
                break
        
        if not target_agent_info:
            print(f"❌ Agent '{preferred_name}' not found!")
            return
        
        print(f"🔗 Connecting to {preferred_name}...")
        
        # Connect to agent using service_name, not agent ID
        service_name = target_agent_info.get('service_name')
        if not service_name:
            print(f"❌ No service name found for {preferred_name}")
            return
            
        connected = await self.interface.connect_to_agent(service_name)
        if not connected:
            print(f"❌ Failed to connect to {preferred_name}")
            return
        
        self.connected_agent = preferred_name
        print(f"✅ Connected to {preferred_name}")
        print()
        
        # Start chat session
        await self.chat_session()

    async def chat_session(self):
        """Interactive chat session with connected agent"""
        print(f"💬 Chat Session with {self.connected_agent}")
        print("=" * 40)
        print()
        
        if self.connected_agent == "PersonalAssistant":
            print("🌟 PersonalAssistant Demo Queries:")
            print("   • 'What's the weather in London?'")
            print("   • 'Calculate 987 * 654'")
            print("   • 'What's 15% tip on $85 and weather in Tokyo?'")
        elif self.connected_agent == "WeatherExpert":
            print("🌤️ WeatherAgent Demo Queries (@genesis_tool):")
            print("   • 'Current weather in Paris, France'")
            print("   • 'Give me a 5-day forecast for Tokyo'")
            print("   • 'Analyze weather: London, 18°C, cloudy, 75% humidity'")
        
        print()
        print("💡 Type 'quit' to disconnect, 'scenarios' for more examples")
        print()
        
        while True:
            try:
                user_input = input(f"{self.connected_agent}> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'disconnect']:
                    print(f"🔌 Disconnected from {self.connected_agent}")
                    self.connected_agent = None
                    print()
                    break
                elif user_input.lower() == 'scenarios':
                    self.show_demo_scenarios()
                    continue
                elif not user_input:
                    continue
                
                # Detect if this might be a weather query (likely to involve delegation)
                weather_keywords = ['weather', 'temperature', 'forecast', 'rain', 'snow', 'cloudy', 'sunny']
                likely_weather_query = any(keyword in user_input.lower() for keyword in weather_keywords)
                
                print(f"📤 Sending: {user_input}")
                if likely_weather_query and self.connected_agent == "PersonalAssistant":
                    print("⏳ Processing weather query (may involve agent delegation)...")
                else:
                    print("⏳ Processing...")
                
                # Start the request
                request_task = asyncio.create_task(self.interface.send_request({
                    'message': user_input,
                    'conversation_id': self.conversation_id
                }, timeout_seconds=60.0))
                
                # Show progress dots for potentially long operations
                if likely_weather_query and self.connected_agent == "PersonalAssistant":
                    await self._show_progress_with_dots(request_task, "🌤️ Consulting weather specialist")
                else:
                    # For quick operations, just wait normally
                    pass
                
                # Get the result
                try:
                    response = await request_task
                except Exception as e:
                    print(f"❌ Request failed: {e}")
                    print()
                    continue
                
                if response and response.get('status') == 0:
                    message = response.get('message', 'No response')
                    print(f"📥 {self.connected_agent}: {message}")
                else:
                    print(f"❌ Error: {response.get('message', 'Unknown error') if response else 'No response'}")
                
                print()
                
            except KeyboardInterrupt:
                print(f"\n🔌 Disconnected from {self.connected_agent}")
                self.connected_agent = None
                print()
                break
            except Exception as e:
                print(f"❌ Chat error: {e}")
                print()

    def show_demo_scenarios(self):
        """Show detailed demo scenarios"""
        print("🧪 Genesis Multi-Agent Demo Scenarios")
        print("=" * 40)
        print()
        
        print("1️⃣ Weather Delegation (PersonalAssistant → WeatherAgent)")
        print("   Query: 'What's the weather in Tokyo, Japan?'")
        print("   Flow: PersonalAssistant discovers WeatherAgent")
        print("         → Delegates weather query automatically")
        print("         → WeatherAgent uses @genesis_tool methods")
        print("         → Returns real/mock weather data")
        print()
        
        print("2️⃣ Function Calling (PersonalAssistant → Calculator)")
        print("   Query: 'Calculate 123 * 456 + 789'")
        print("   Flow: PersonalAssistant discovers Calculator service")
        print("         → Calls math functions automatically")
        print("         → Returns calculated results")
        print()
        
        print("3️⃣ Mixed Capabilities (Multi-delegation)")
        print("   Query: 'Weather in London and calculate 15% tip on $85'")
        print("   Flow: PersonalAssistant handles both:")
        print("         → Weather → WeatherAgent")
        print("         → Math → Calculator Service")
        print("         → Combines results intelligently")
        print()
        
        print("4️⃣ Direct Specialization (WeatherAgent)")
        print("   Query: 'Give me a 5-day forecast for Paris with analysis'")
        print("   Flow: WeatherAgent uses @genesis_tool decorators:")
        print("         → get_weather_forecast()")
        print("         → analyze_weather_conditions()")
        print("         → No manual schema definition needed!")
        print()
        
        print("5️⃣ @genesis_tool Auto-Discovery Demo")
        print("   Query: 'Analyze weather conditions for 22°C sunny day in Rome'")
        print("   Flow: WeatherAgent's @genesis_tool method:")
        print("         → Automatic OpenAI schema generation")
        print("         → Type-safe parameter handling")
        print("         → Detailed weather analysis")
        print()
        
        print("💡 Try these queries with PersonalAssistant or WeatherAgent!")
        print()

    async def close(self):
        """Clean up resources"""
        if self.interface:
            await self.interface.close()

    async def _show_progress_with_dots(self, task: asyncio.Task, message: str):
        """Show progress dots for potentially long operations"""
        import sys
        
        print(f"🔄 {message}", end="", flush=True)
        dot_count = 0
        
        while not task.done():
            await asyncio.sleep(0.8)
            if not task.done():
                dot_count = (dot_count + 1) % 4
                dots = "." * dot_count + " " * (3 - dot_count)
                print(f"\r🔄 {message}{dots}", end="", flush=True)
        
        # Clear the progress line and show completion
        print(f"\r✅ {message}... completed!        ")
        sys.stdout.flush()

async def main():
    """Main entry point"""
    cli = MultiAgentCLI()
    
    try:
        await cli.start()
    except KeyboardInterrupt:
        print("\n👋 Demo ended by user")
    finally:
        await cli.close()

if __name__ == "__main__":
    asyncio.run(main()) 