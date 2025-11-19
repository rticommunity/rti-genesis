sour# Multi-Agent Example Implementation Prompt

## Context
You need to create a multi-agent example in `/examples/MultiAgent/` that demonstrates Genesis framework capabilities. **Do NOT reinvent Genesis patterns.**

## Critical Constraints

### 🚨 **NEVER RECREATE WHAT GENESIS PROVIDES**
- Genesis `MonitoredInterface` has built-in agent discovery (`available_agents`)
- Genesis `MonitoredInterface` has built-in connection (`connect_to_agent()`)  
- Genesis `MonitoredInterface` has built-in messaging (`send_request()`)
- Genesis `OpenAIGenesisAgent` handles all LLM integration automatically
- Genesis handles ALL DDS complexity automatically

### 🚨 **AVOID THESE MISTAKES**
1. **NO custom ConversationManager** - Use `MonitoredInterface` directly
2. **NO custom AgentSelector** - Use `available_agents` property
3. **NO manual DDS topic management** - Genesis does this
4. **NO mock data in final tests** - Only real agents/APIs
5. **NO hardcoded tool assumptions** - Dynamic discovery only

## ✅ **Correct Implementation Pattern**

### File 1: `examples/MultiAgent/agents/personal_assistant.py`
```python
#!/usr/bin/env python3
import asyncio
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

class PersonalAssistant(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            agent_name="PersonalAssistant",
            base_service_name="OpenAIAgent",
            description="A friendly, helpful general-purpose AI assistant",
            enable_agent_communication=True
        )

async def main():
    assistant = PersonalAssistant()
    await assistant.run()  # CRITICAL: This starts the RPC service

if __name__ == "__main__":
    asyncio.run(main())
```

### File 2: `examples/MultiAgent/test_cli.py`
```python
#!/usr/bin/env python3
import asyncio
from genesis_lib.monitored_interface import MonitoredInterface

class MultiAgentCLI(MonitoredInterface):
    def __init__(self):
        super().__init__(
            interface_name="MultiAgentCLI",
            service_name="OpenAIAgent"
        )

    async def test_conversation(self):
        # Wait for agent discovery
        print("🔍 Waiting for agents...")
        while not self.available_agents:
            await asyncio.sleep(0.5)
        
        # Show discovered agents
        print(f"✅ Found {len(self.available_agents)} agent(s):")
        for agent_id, info in self.available_agents.items():
            print(f"  - {info.get('prefered_name')} ({agent_id})")
        
        # Connect to first agent
        agent_info = next(iter(self.available_agents.values()))
        service_name = agent_info.get('service_name')
        success = await super().connect_to_agent(service_name)
        
        if not success:
            print("❌ Failed to connect")
            return
        
        # Test joke request
        print("\n💬 Testing joke request...")
        response = await self.send_request({
            "message": "Tell me a joke",
            "conversation_id": "test_joke"
        })
        
        if response:
            print(f"🤖 Response: {response.get('message')}")
        else:
            print("❌ No response")
        
        # Test math request (should use calculator service)
        print("\n🧮 Testing math request...")
        response = await self.send_request({
            "message": "What is 127 + 384?",
            "conversation_id": "test_math"
        })
        
        if response:
            print(f"🤖 Response: {response.get('message')}")
        else:
            print("❌ No response")

async def main():
    cli = MultiAgentCLI()
    await cli.test_conversation()
    await cli.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### File 3: `examples/MultiAgent/run_demo.sh`
```bash
#!/bin/bash
set -e

echo "🚀 Starting Multi-Agent Demo..."

# Start calculator service in background
echo "📊 Starting calculator service..."
cd ../../
python -m services.calculator_service &
CALC_PID=$!

# Start PersonalAssistant in background  
echo "🤖 Starting PersonalAssistant..."
cd examples/MultiAgent
python agents/personal_assistant.py &
ASSISTANT_PID=$!

# Wait for services to start
sleep 3

# Run test CLI
echo "🖥️ Starting CLI..."
python test_cli.py

# Cleanup
echo "🧹 Cleaning up..."
kill $CALC_PID $ASSISTANT_PID 2>/dev/null || true
echo "✅ Demo complete"
```

## 📋 **Implementation Steps**

1. **Copy the working pattern from `/run_scripts/comprehensive_multi_agent_test_interface.py`**
2. **Create PersonalAssistant using `OpenAIGenesisAgent` exactly as shown**
3. **Create CLI using `MonitoredInterface` exactly as shown**
4. **Test with real agents only - no mocks**
5. **Use Genesis built-in methods exclusively**

## 🎯 **Success Criteria**

The example works when:
- ✅ PersonalAssistant runs and discovers calculator service
- ✅ CLI discovers PersonalAssistant automatically
- ✅ "Tell me a joke" works (pure LLM response)
- ✅ "What is 127 + 384?" works (calls calculator service)
- ✅ All communication uses Genesis patterns only

## 🚨 **If You Start Thinking About...**

- **"I need to manage agent discovery"** → STOP. Use `available_agents`
- **"I need to create a connection manager"** → STOP. Use `connect_to_agent()`
- **"I need to handle DDS topics"** → STOP. Genesis does this
- **"I need to create mock data"** → STOP. Use real agents only
- **"I need to bridge components"** → STOP. Genesis provides everything

## 📚 **Reference Files**

**Copy these working examples exactly:**
- `/run_scripts/comprehensive_multi_agent_test_interface.py` - For CLI pattern
- `/genesis_lib/openai_genesis_agent.py` - For agent patterns
- `/services/calculator_service.py` - For service patterns

**The entire conversation history shows what NOT to do. Follow this prompt instead.** 