#!/usr/bin/env python3
"""
Simple test to verify chain events are published when agents call functions.
Run this to debug chain event publishing.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

async def main():
    print("=" * 80)
    print("Testing Chain Events - Agent Function Call Monitoring")
    print("=" * 80)
    print()
    
    # Create a simple test agent
    agent = OpenAIGenesisAgent(
        model_name="gpt-4o",
        agent_name="TestAgent",
        base_service_name="TestAgentService",
        description="Test agent for chain event verification"
    )
    
    print(f"✅ Agent created: {agent.agent_name}")
    print(f"   Agent ID: {agent.app.agent_id}")
    print(f"   Has unified_event_writer: {hasattr(agent, 'unified_event_writer')}")
    if hasattr(agent, 'unified_event_writer'):
        print(f"   unified_event_writer value: {agent.unified_event_writer}")
    print()
    
    # Wait for discovery
    print("⏳ Waiting 5 seconds for function discovery...")
    await asyncio.sleep(5)
    
    # Check discovered functions
    functions = agent._get_available_functions()
    print(f"📚 Discovered {len(functions)} functions:")
    for fname in list(functions.keys())[:5]:
        print(f"   - {fname}")
    print()
    
    if not functions:
        print("❌ No functions discovered. Make sure a service is running!")
        print("   Start a calculator service: python test_functions/services/calculator_service.py")
        await agent.close()
        return
    
    # Try calling a function if available
    if 'add' in functions:
        print("🔥 Calling 'add' function...")
        print("   Watch for '🔥' debug logs in the output")
        print()
        try:
            result = await agent._call_function('add', x=10, y=20)
            print(f"✅ Function call successful! Result: {result}")
        except Exception as e:
            print(f"❌ Function call failed: {e}")
    else:
        print("⚠️  'add' function not available")
    
    print()
    print("🛑 Closing agent...")
    await agent.close()
    print("✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(main())

