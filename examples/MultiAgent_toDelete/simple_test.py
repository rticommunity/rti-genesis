#!/usr/bin/env python3
"""
Simple automated test of the CLI interface.

This test demonstrates that the CLI can:
1. Discover the PersonalAssistant
2. Connect to it
3. Send a message like "Tell me a joke"
4. Receive a real response

This uses the working CLI infrastructure with automation.
"""

import asyncio
import sys
import os
from unittest.mock import patch
import io

# Add path for imports
sys.path.insert(0, os.path.dirname(__file__))

from interface.cli_interface import MultiAgentCLI

async def automated_conversation_test():
    """
    Automate the CLI to test conversation functionality.
    """
    print("🧪 Starting automated CLI conversation test...")
    
    # Create CLI instance in test mode
    cli = MultiAgentCLI(test_mode=True)
    
    try:
        # Initialize the CLI
        success = await cli._initialize_components()
        if not success:
            print("❌ Failed to initialize CLI components")
            return False
        
        # Wait a bit for discovery
        print("⏳ Waiting for agent discovery...")
        await asyncio.sleep(5)
        
        # Refresh discovery
        await cli.agent_selector.refresh_discovery()
        
        # Check if we have any agents
        available_agents = cli.agent_selector.get_available_agents()
        
        if not available_agents:
            print("❌ No agents discovered")
            return False
        
        print(f"✅ Found {len(available_agents)} agent(s):")
        for i, agent in enumerate(available_agents, 1):
            print(f"   {i}. {agent.display_name}")
        
        # Select the first agent (PersonalAssistant)
        selected_agent = available_agents[0]
        print(f"🔗 Connecting to: {selected_agent.display_name}")
        
        # Connect to the agent
        connected = await cli.conversation_manager.connect_to_agent(selected_agent)
        
        if not connected:
            print("❌ Failed to connect to agent")
            return False
        
        print("✅ Connected! Now testing conversation...")
        
        # Test messages
        test_messages = [
            "Hello! How are you?",
            "Tell me a joke",
            "What is 5 + 3?",
        ]
        
        all_successful = True
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n📤 Test {i}: {message}")
            
            response = await cli.conversation_manager.send_message(message)
            
            if response:
                print(f"📥 Response: {response[:100]}...")
                print("✅ Test passed!")
            else:
                print("❌ No response received")
                all_successful = False
        
        # Show conversation summary
        summary = cli.conversation_manager.get_conversation_summary()
        print(f"\n📊 Conversation Summary:\n{summary}")
        
        return all_successful
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    
    finally:
        # Cleanup
        await cli._cleanup()

async def main():
    """Main test entry point."""
    print("🧪 Simple CLI Conversation Test")
    print("=" * 50)
    print("This test will:")
    print("  1. Initialize the CLI")
    print("  2. Discover the PersonalAssistant")
    print("  3. Connect to it")
    print("  4. Send test messages including 'Tell me a joke'")
    print("  5. Verify real responses are received")
    print()
    
    success = await automated_conversation_test()
    
    if success:
        print("\n🎉 ALL TESTS PASSED!")
        print("The CLI successfully connected to PersonalAssistant and received real responses!")
        return 0
    else:
        print("\n❌ Tests failed - check logs above")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 