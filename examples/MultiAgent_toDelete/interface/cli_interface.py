#!/usr/bin/env python3
"""
Multi-Agent CLI Interface

This is the main CLI application for the Smart Assistant Ecosystem.
It provides an interactive interface for discovering, selecting, and
conversing with available general assistant agents.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
from typing import Optional, List
import signal
import argparse

# Add the parent directories to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from interface.agent_selector import AgentSelector, DiscoveredAgent
from interface.conversation_manager import ConversationManager
from config.system_settings import validate_environment, get_system_config
from config.agent_configs import get_all_general_assistants

# Configure logging for CLI
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise in CLI
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class MultiAgentCLI:
    """
    Main CLI application for the Multi-Agent Smart Assistant Ecosystem.
    
    This class provides:
    1. System status and environment validation
    2. Agent discovery and listing
    3. Interactive agent selection
    4. Conversation management
    5. Graceful shutdown handling
    """
    
    def __init__(self, test_mode: bool = False):
        """Initialize the CLI application."""
        self.agent_selector: Optional[AgentSelector] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.running = False
        self.current_agent: Optional[DiscoveredAgent] = None
        self.test_mode = test_mode
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n🛑 Shutting down Multi-Agent CLI...")
        self.running = False
        
        # If called twice, force exit
        if hasattr(self, '_shutdown_called'):
            print("🛑 Force shutdown!")
            os._exit(1)
        self._shutdown_called = True
    
    async def start(self) -> int:
        """
        Start the CLI application.
        
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Display welcome banner
            self._display_banner()
            
            # Validate environment
            if not self._validate_environment():
                return 1
            
            # Initialize components
            if not await self._initialize_components():
                return 1
            
            # Test discovery mode - run discovery and exit
            if self.test_mode:
                return await self._run_test_discovery()
            
            # Start main loop for interactive mode
            self.running = True
            await self._main_loop()
            
            return 0
            
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
            return 0
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            logger.error(f"Fatal error in CLI: {e}", exc_info=True)
            return 1
        finally:
            await self._cleanup()
    
    def _display_banner(self):
        """Display the welcome banner."""
        print("=" * 70)
        print("🤖 Genesis Multi-Agent Smart Assistant Ecosystem")
        print("=" * 70)
        print("Welcome! This interface lets you discover and chat with AI assistants.")
        print("Each assistant has different specialties and can coordinate with")
        print("specialized agents and services to help you with various tasks.")
        print("=" * 70)
    
    def _validate_environment(self) -> bool:
        """
        Validate the environment configuration.
        
        Returns:
            True if environment is valid, False otherwise
        """
        print("🔍 Validating environment...")
        
        validation = validate_environment()
        
        if validation["warnings"]:
            print("\n⚠️  Environment Warnings:")
            for warning in validation["warnings"]:
                print(f"   • {warning}")
        
        if validation["errors"]:
            print("\n❌ Environment Errors:")
            for error in validation["errors"]:
                print(f"   • {error}")
            print("\nPlease fix these errors before continuing.")
            return False
        
        print("✅ Environment validation passed!")
        return True
    
    async def _initialize_components(self) -> bool:
        """
        Initialize CLI components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        print("\n🚀 Initializing system components...")
        
        try:
            # Initialize agent selector
            print("   📡 Starting agent discovery...")
            self.agent_selector = AgentSelector("MultiAgentCLI")
            await self.agent_selector.start_discovery()
            
            # Initialize conversation manager
            print("   💬 Starting conversation manager...")
            self.conversation_manager = ConversationManager()
            
            # Wait for initial discovery
            print("   ⏳ Waiting for agent discovery...")
            await asyncio.sleep(3)  # Give time for discovery
            await self.agent_selector.refresh_discovery()
            
            print("✅ System components initialized!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize components: {e}")
            logger.error(f"Component initialization failed: {e}", exc_info=True)
            return False
    
    async def _main_loop(self):
        """Main application loop."""
        while self.running:
            try:
                if self.current_agent is None:
                    # Show main menu
                    choice = await self._show_main_menu()
                    await self._handle_main_menu_choice(choice)
                else:
                    # In conversation mode
                    await self._conversation_mode()
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error in main loop: {e}")
                logger.error(f"Main loop error: {e}", exc_info=True)
                # Continue running unless it's a fatal error
                await asyncio.sleep(1)
    
    async def _show_main_menu(self) -> str:
        """
        Display the main menu and get user choice.
        
        Returns:
            User's menu choice
        """
        print("\n" + "=" * 50)
        print("📋 MAIN MENU")
        print("=" * 50)
        
        # Get available agents
        available_agents = self.agent_selector.get_available_agents()
        
        if available_agents:
            print("🤖 Available General Assistants:")
            for i, agent in enumerate(available_agents, 1):
                status_emoji = "🟢"  # Available
                response_info = ""
                if agent.response_time:
                    response_info = f" ({agent.response_time:.3f}s)"
                print(f"   {i}. {agent.display_name}{response_info}")
                print(f"      {agent.description}")
            print()
        else:
            print("⏳ No agents discovered yet. Discovery is ongoing...")
            print()
        
        # Menu options
        print("Options:")
        if available_agents:
            print("   [1-9] Connect to an assistant")
        print("   [s]   Show system status")
        print("   [r]   Refresh agent discovery")
        print("   [h]   Show help")
        print("   [q]   Quit")
        print()
        
        return input("Enter your choice: ").strip().lower()
    
    async def _handle_main_menu_choice(self, choice: str):
        """
        Handle user's main menu choice.
        
        Args:
            choice: User's menu choice
        """
        if choice == 'q':
            self.running = False
            return
        
        elif choice == 's':
            await self._show_system_status()
        
        elif choice == 'r':
            print("🔄 Refreshing agent discovery...")
            await self.agent_selector.refresh_discovery()
            print("✅ Discovery refreshed!")
        
        elif choice == 'h':
            self._show_help()
        
        elif choice.isdigit():
            # Try to connect to an agent
            await self._connect_to_agent(int(choice))
        
        else:
            print("❓ Invalid choice. Please try again.")
    
    async def _connect_to_agent(self, agent_number: int):
        """
        Connect to a specific agent by number.
        
        Args:
            agent_number: The agent number from the menu (1-based)
        """
        available_agents = self.agent_selector.get_available_agents()
        
        if 1 <= agent_number <= len(available_agents):
            agent = available_agents[agent_number - 1]
            print(f"\n🔗 Connecting to {agent.display_name}...")
            
            # Perform health check first
            healthy = await self.agent_selector.health_check_agent(agent.agent_id)
            if not healthy:
                print(f"❌ {agent.display_name} is not responding. Please try another agent.")
                return
            
            # Connect to agent
            connected = await self.conversation_manager.connect_to_agent(agent)
            if connected:
                self.current_agent = agent
                print(f"✅ Connected to {agent.display_name}!")
                print("💬 You are now in conversation mode. Type 'exit' to return to main menu.")
                print("-" * 50)
            else:
                print(f"❌ Failed to connect to {agent.display_name}. Please try again.")
        else:
            print("❓ Invalid agent number. Please try again.")
    
    async def _conversation_mode(self):
        """Handle conversation mode with the connected agent."""
        try:
            print(f"\n💬 {self.current_agent.display_name}")
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                # Disconnect from agent
                self.conversation_manager.disconnect()
                self.current_agent = None
                print("👋 Disconnected. Returning to main menu...")
                return
            
            if user_input.lower() == 'history':
                # Show conversation summary
                print("\n" + "=" * 60)
                print(self.conversation_manager.get_conversation_summary())
                return
            
            if user_input.lower() == 'stats':
                # Show session statistics (simplified)
                print("\n📊 Session Statistics:")
                print(self.conversation_manager.get_conversation_summary())
                return
            
            if not user_input:
                return  # Empty input, just continue
            
            # Send message to agent
            print("⏳ Thinking...")
            response = await self.conversation_manager.send_message(user_input)
            
            if response:
                print(f"\n🤖 {self.current_agent.display_name}: {response}")
            else:
                print("❌ Failed to get response from agent. Please try again.")
                
        except KeyboardInterrupt:
            # User pressed Ctrl+C in conversation mode
            print("\n💬 Type 'exit' to return to main menu or continue chatting...")
    
    async def _show_system_status(self):
        """Display system status information."""
        print("\n" + "=" * 60)
        print("📊 SYSTEM STATUS")
        print("=" * 60)
        
        # Show configuration
        config = get_system_config()
        print("🔧 Configuration:")
        print(f"   Domain ID: {config['domain_id']}")
        print(f"   OpenAI Model: {config['openai_model']}")
        print(f"   Debug Mode: {config['debug_mode']}")
        print(f"   API Keys: {'✅' if config['openai_api_key'] else '❌'} OpenAI, {'✅' if config['weather_api_key'] else '❌'} Weather")
        
        # Show discovered agents
        print("\n🤖 Discovered Agents:")
        if self.agent_selector:
            all_agents = list(self.agent_selector.discovered_agents.values())
            if all_agents:
                for agent in all_agents:
                    status_emoji = {"available": "🟢", "busy": "🟡", "offline": "🔴", "unknown": "⚪"}[agent.status.value]
                    print(f"   {status_emoji} {agent.display_name} ({agent.agent_id[:8]}...)")
            else:
                print("   No agents discovered yet")
        else:
            print("   Agent selector not initialized")
        
        # Show conversation status
        print("\n💬 Conversation Status:")
        if self.conversation_manager and self.conversation_manager.current_session:
            session = self.conversation_manager.current_session
            print(f"   Connected to: {session.agent.display_name}")
            print(f"   Messages: {session.total_messages}")
            print(f"   Duration: {(session.last_activity - session.created_at).total_seconds():.1f}s")
        else:
            print("   No active conversation")
        
        print("=" * 60)
    
    def _show_help(self):
        """Display help information."""
        print("\n" + "=" * 60)
        print("❓ HELP")
        print("=" * 60)
        print("Welcome to the Genesis Multi-Agent Smart Assistant Ecosystem!")
        print()
        print("🤖 General Assistants:")
        for name, config in get_all_general_assistants().items():
            print(f"   • {config['display_name']}: {config['description']}")
        print()
        print("💬 Conversation Commands (when connected to an agent):")
        print("   • Type your message and press Enter to chat")
        print("   • 'history' - Show recent conversation history")
        print("   • 'stats' - Show session statistics")
        print("   • 'exit' - Return to main menu")
        print()
        print("🔧 Main Menu Commands:")
        print("   • [1-9] - Connect to an assistant by number")
        print("   • [s] - Show system status")
        print("   • [r] - Refresh agent discovery")
        print("   • [h] - Show this help")
        print("   • [q] - Quit the application")
        print("=" * 60)
    
    async def _cleanup(self):
        """Clean up resources with timeout to prevent hanging."""
        print("\n🧹 Cleaning up...")
        
        try:
            # Use asyncio.wait_for to add timeouts to cleanup operations
            cleanup_timeout = 5.0  # 5 second timeout for cleanup
            
            if self.conversation_manager:
                try:
                    await asyncio.wait_for(
                        self.conversation_manager.close(), 
                        timeout=cleanup_timeout
                    )
                    self.conversation_manager = None
                except asyncio.TimeoutError:
                    print("⚠️  Conversation manager cleanup timed out")
                    self.conversation_manager = None
                except Exception as e:
                    print(f"⚠️  Error cleaning up conversation manager: {e}")
                    self.conversation_manager = None
            
            if self.agent_selector:
                try:
                    await asyncio.wait_for(
                        self.agent_selector.close(), 
                        timeout=cleanup_timeout
                    )
                    self.agent_selector = None
                except asyncio.TimeoutError:
                    print("⚠️  Agent selector cleanup timed out")
                    self.agent_selector = None
                except Exception as e:
                    print(f"⚠️  Error cleaning up agent selector: {e}")
                    self.agent_selector = None
            
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            logger.error(f"Cleanup error: {e}", exc_info=True)
    
    async def _run_test_discovery(self) -> int:
        """
        Run discovery test and exit.
        
        Returns:
            Exit code (0 for success, 1 for error)
        """
        print("\n🧪 Running discovery test...")
        
        # Wait for discovery to complete
        print("   ⏳ Waiting for agent discovery...")
        await asyncio.sleep(5)  # Give more time for discovery
        await self.agent_selector.refresh_discovery()
        
        # Check results
        available_agents = self.agent_selector.get_available_agents()
        
        print(f"\n📊 Discovery Results:")
        print(f"   Found {len(available_agents)} general assistant(s)")
        
        if available_agents:
            print("   ✅ Discovered agents:")
            for i, agent in enumerate(available_agents, 1):
                print(f"      {i}. {agent.display_name} ({agent.agent_id[:8]}...)")
                print(f"         Service: {agent.service_name}")
                print(f"         Status: {agent.status.value}")
            return 0
        else:
            print("   ❌ No general assistants discovered")
            print("   💡 Make sure PersonalAssistant or other general assistants are running")
            return 1

async def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="Multi-Agent CLI Interface")
    parser.add_argument("--test-discovery", action="store_true", help="Run in test discovery mode")
    args = parser.parse_args()

    cli = MultiAgentCLI(test_mode=args.test_discovery)
    try:
        # Add overall timeout to prevent hanging
        exit_code = await asyncio.wait_for(cli.start(), timeout=300.0)  # 5 minute overall timeout
        return exit_code
    except asyncio.TimeoutError:
        print("\n⏰ CLI application timed out")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        # Force exit to prevent hanging
        os._exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        # Force exit to prevent hanging
        os._exit(1) 