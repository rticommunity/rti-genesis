#!/usr/bin/env python3
"""
Interactive Memory Test - Genesis Agent Memory System

This interactive CLI allows users to manually test the memory functionality
of Genesis agents. It demonstrates how agents can maintain conversation
context across multiple turns using the pluggable memory system.

Features:
- Direct interaction with OpenAI Genesis Agent
- Memory persistence across conversation turns
- Memory content inspection
- Clear demonstration of memory recall capabilities

Usage:
    python interactive_memory_test.py

Commands during conversation:
- Type any message to chat with the agent
- Type 'memory' to see current memory contents
- Type 'clear' to clear memory
- Type 'exit' or 'quit' to end the session

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import sys
import logging
import os
from datetime import datetime

# Add Genesis library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.memory import SimpleMemoryAdapter

# Configure logging to be less verbose for CLI
logging.basicConfig(level=logging.ERROR)  # Even quieter for interactive use
logger = logging.getLogger("interactive_memory_test")

class InteractiveMemoryAgent(OpenAIGenesisAgent):
    """
    An OpenAI Genesis Agent specifically configured for memory testing.
    
    This agent has a clear system prompt that identifies it as a Genesis agent
    and emphasizes its memory capabilities for testing purposes.
    """
    
    def __init__(self, memory_adapter=None):
        # Temporarily suppress print output during initialization
        import builtins
        original_print = builtins.print
        
        def quiet_print(*args, **kwargs):
            # Only suppress Genesis initialization prints
            if args and isinstance(args[0], str) and ('🚀 PRINT:' in args[0] or '🏗️ PRINT:' in args[0] or '✅ PRINT:' in args[0] or '📊 PRINT:' in args[0] or '🔍 TRACE:' in args[0] or '📡 TRACE:' in args[0]):
                return
            original_print(*args, **kwargs)
        
        builtins.print = quiet_print
        
        try:
            super().__init__(
                model_name="gpt-4o",
                classifier_model_name="gpt-4o-mini",
                agent_name="InteractiveMemoryAgent",
                description="An interactive Genesis agent for testing memory capabilities",
                enable_tracing=False,  # Disable tracing for cleaner CLI experience
                memory_adapter=memory_adapter or SimpleMemoryAdapter()
            )
        finally:
            # Restore original print
            builtins.print = original_print
        
        # Override the system prompt to clearly identify this as a Genesis agent with memory
        self.system_prompt = (
            "You are a Genesis agent, part of the Genesis distributed agent framework. "
            "You have memory capabilities and can recall previous conversations perfectly. "
            "Always identify yourself as a Genesis agent when asked about your type. "
            "Be helpful, friendly, and demonstrate your ability to remember information "
            "from earlier in our conversation. If asked about your memory, explain that "
            "you can remember our entire conversation history."
        )
        
        logger.info("InteractiveMemoryAgent initialized with memory capabilities")

class InteractiveMemoryTest:
    """
    Interactive CLI for testing Genesis agent memory functionality.
    
    Provides a user-friendly interface to chat with an agent and observe
    how it maintains context through memory across conversation turns.
    """
    
    def __init__(self):
        self.agent = None
        self.conversation_count = 0
        
    def print_header(self):
        """Print the welcome header and instructions."""
        print("🧠 Genesis Agent Memory Test - Interactive CLI")
        print("=" * 50)
        print()
        print("🎯 This demo showcases:")
        print("   • Agent memory persistence across conversation turns")
        print("   • Context recall from previous messages")
        print("   • Memory content inspection and management")
        print("   • Genesis agent identity and capabilities")
        print()
        print("💡 Available commands:")
        print("   • Type any message to chat with the agent")
        print("   • Type 'memory' to inspect current memory contents")
        print("   • Type 'clear' to clear all memory")
        print("   • Type 'help' to show this help again")
        print("   • Type 'exit' or 'quit' to end the session")
        print()
        print("🧪 Suggested test scenarios:")
        print("   1. 'What kind of agent are you?'")
        print("   2. 'My favorite color is blue. Remember this.'")
        print("   3. 'What is my favorite color?'")
        print("   4. 'My birthday is March 15th. Please remember.'")
        print("   5. 'What do you remember about me?'")
        print()
    
    def print_memory_contents(self):
        """Display current memory contents in a readable format."""
        if not self.agent or not self.agent.memory:
            print("❌ No agent or memory available")
            return
            
        memory_items = self.agent.memory.retrieve(k=20)  # Get last 20 items
        
        if not memory_items:
            print("📝 Memory is empty")
            return
            
        print("📝 Current Memory Contents:")
        print("-" * 40)
        
        for i, entry in enumerate(memory_items, 1):
            item = entry.get("item", "")
            metadata = entry.get("metadata", {})
            role = metadata.get("role", "unknown")
            
            # Truncate long messages for display
            display_item = item[:100] + "..." if len(item) > 100 else item
            
            print(f"{i:2}. [{role:9}] {display_item}")
        
        print("-" * 40)
        print(f"Total memory items: {len(memory_items)}")
        print()
    
    def clear_memory(self):
        """Clear all memory contents."""
        if not self.agent or not self.agent.memory:
            print("❌ No agent or memory available")
            return
            
        # Clear memory by creating a new adapter
        self.agent.memory = SimpleMemoryAdapter()
        print("🗑️ Memory cleared successfully")
        print()
    
    def print_help(self):
        """Print help information."""
        print("💡 Available commands:")
        print("   • Type any message to chat with the agent")
        print("   • Type 'memory' to inspect current memory contents")
        print("   • Type 'clear' to clear all memory")
        print("   • Type 'help' to show this help again")
        print("   • Type 'exit' or 'quit' to end the session")
        print()
    
    async def start(self):
        """Start the interactive memory test."""
        self.print_header()
        
        print("🔧 Initializing Genesis agent with memory...")
        
        try:
            # Create agent with memory
            self.agent = InteractiveMemoryAgent()
            
            # Give some time for initialization
            await asyncio.sleep(2)
            
            print("✅ Agent initialized successfully!")
            print()
            print("🚀 Ready to test memory capabilities!")
            print("=" * 50)
            print()
            
            # Main interaction loop
            await self.main_loop()
            
        except Exception as e:
            print(f"❌ Error initializing agent: {e}")
            logger.error(f"Agent initialization error: {e}")
        finally:
            if self.agent:
                await self.agent.close()
    
    async def main_loop(self):
        """Main interaction loop."""
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Goodbye! Thanks for testing Genesis memory!")
                    break
                elif user_input.lower() == 'memory':
                    self.print_memory_contents()
                    continue
                elif user_input.lower() == 'clear':
                    self.clear_memory()
                    continue
                elif user_input.lower() == 'help':
                    self.print_help()
                    continue
                elif not user_input:
                    continue
                
                # Process message with agent
                print("🤖 Agent: ", end="", flush=True)
                
                try:
                    # Send message to agent
                    response = await self.agent.process_message(user_input)
                    print(response)
                    
                    # Increment conversation counter
                    self.conversation_count += 1
                    
                    # Show memory hint after a few exchanges
                    if self.conversation_count == 3:
                        print()
                        print("💡 Tip: Type 'memory' to see what the agent remembers!")
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
                    logger.error(f"Message processing error: {e}")
                
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye! Thanks for testing Genesis memory!")
                break
            except EOFError:
                print("\n👋 Input stream closed. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                logger.error(f"Main loop error: {e}")

async def main():
    """Main entry point for the interactive memory test."""
    test = InteractiveMemoryTest()
    
    try:
        await test.start()
    except KeyboardInterrupt:
        print("\n👋 Memory test ended by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 