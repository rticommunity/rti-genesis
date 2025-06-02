# Genesis Multi-Agent Example Implementation Guide

## Critical Implementation Principles

### 🚨 **FUNDAMENTAL RULE: USE GENESIS PATTERNS, DON'T REINVENT**

**Genesis already provides everything you need. Do NOT create custom wrappers, managers, or discovery systems.**

## ✅ **Correct Implementation Pattern**

Look at these **WORKING** examples in the Genesis codebase:
- `/run_scripts/comprehensive_multi_agent_test_interface.py`
- `/run_scripts/run_interface_agent_service_test.sh`
- Any file in `/test_scripts/` that inherits from `MonitoredInterface`

### **Pattern 1: Interface (for CLI/User Interaction)**
```python
# ✅ CORRECT - Use MonitoredInterface directly
class MultiAgentCLI(MonitoredInterface):
    def __init__(self):
        super().__init__(
            interface_name="MultiAgentCLI",
            service_name="OpenAIAgent"  # The service you want to connect to
        )
        
    async def wait_for_agents(self):
        # ✅ Use built-in available_agents from MonitoredInterface
        while not self.available_agents:
            await asyncio.sleep(0.5)
        return self.available_agents
    
    async def connect_to_first_agent(self):
        agent_id = next(iter(self.available_agents.keys()))
        agent_info = self.available_agents[agent_id]
        
        # ✅ Use Genesis built-in connection
        service_name = agent_info.get('service_name')
        success = await super().connect_to_agent(service_name)
        return success
    
    async def send_joke_request(self):
        # ✅ Use Genesis built-in send_request
        response = await self.send_request({
            "message": "Tell me a joke",
            "conversation_id": "test_joke"
        })
        return response.get('message') if response else None
```

### **Pattern 2: Agent (PersonalAssistant)**
```python
# ✅ CORRECT - Use OpenAIGenesisAgent directly
class PersonalAssistant(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant", 
            base_service_name="OpenAIAgent",
            description="A friendly, helpful general-purpose AI assistant",
            enable_agent_communication=True  # For agent-as-tool pattern
        )
    
    async def main(self):
        # ✅ CRITICAL: Use Genesis run() method
        await self.run()  # This starts DDS listeners and RPC service
```

## ❌ **Common Mistakes to AVOID**

### **Mistake 1: Creating Custom Discovery/Connection Managers**
```python
# ❌ WRONG - Don't create custom wrappers
class ConversationManager(MonitoredInterface):
    def connect_to_agent(self, agent):
        # Don't create custom connection logic
        # Don't bridge between AgentSelector and MonitoredInterface
        # Don't create MockDiscoveredAgent objects
        pass
```

**Why Wrong**: Genesis `MonitoredInterface` already has:
- Built-in `available_agents` discovery
- Built-in `connect_to_agent()` method
- Built-in `send_request()` method

### **Mistake 2: Manual DDS Topic Management**
```python
# ❌ WRONG - Don't manually manage DDS
self.registration_reader = dds.DynamicData.DataReader(...)
self.app.function_registry.add_discovery_callback(...)
```

**Why Wrong**: Genesis handles all DDS complexity automatically.

### **Mistake 3: Custom Agent Discovery Systems**
```python
# ❌ WRONG - Don't create AgentSelector bridges
class AgentSelector:
    def get_available_agents(self):
        # Don't create custom discovery
        pass
```

**Why Wrong**: `MonitoredInterface.available_agents` provides this automatically.

### **Mistake 4: Not Using Genesis RPC Properly**
```python
# ❌ WRONG - Don't create sleep loops
async def main():
    while True:
        await asyncio.sleep(1)  # Does nothing!
```

**✅ CORRECT**:
```python
async def main():
    await agent.run()  # Starts Genesis RPC service
```

## 📋 **Step-by-Step Implementation**

### **Step 1: Copy Working Patterns**
1. Start with `/run_scripts/comprehensive_multi_agent_test_interface.py`
2. Copy the exact structure and inheritance
3. Modify ONLY the business logic, not the Genesis patterns

### **Step 2: Create PersonalAssistant**
```python
# Copy this EXACTLY - it works
class PersonalAssistant(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            agent_name="PersonalAssistant",
            base_service_name="OpenAIAgent", 
            enable_agent_communication=True
        )
    
    def _create_system_prompt(self, config):
        # ✅ CRITICAL: NO hardcoded tool assumptions
        return """You are a helpful AI assistant. 
        You can use any tools that are dynamically discovered.
        Never assume specific tools exist."""

# Run with Genesis pattern
async def main():
    assistant = PersonalAssistant()
    await assistant.run()  # This is THE critical line

if __name__ == "__main__":
    asyncio.run(main())
```

### **Step 3: Create CLI Interface**
```python
# Copy working interface pattern
class MultiAgentCLI(MonitoredInterface):
    def __init__(self):
        super().__init__("MultiAgentCLI", "OpenAIAgent")
    
    async def test_joke(self):
        # Wait for discovery
        while not self.available_agents:
            await asyncio.sleep(0.5)
        
        # Connect using Genesis
        agent_info = next(iter(self.available_agents.values()))
        service_name = agent_info.get('service_name')
        await super().connect_to_agent(service_name)
        
        # Send request using Genesis
        response = await self.send_request({
            "message": "Tell me a joke"
        })
        
        return response.get('message') if response else None
```

### **Step 4: Test Script**
```python
async def main():
    cli = MultiAgentCLI()
    
    # Test the joke request
    joke = await cli.test_joke()
    print(f"Joke response: {joke}")
    
    await cli.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 🧪 **Testing Strategy**

### **Use Existing Working Tests as Templates**
1. Copy `/run_scripts/comprehensive_multi_agent_test_interface.py`
2. Modify the test messages only
3. Keep all Genesis patterns identical

### **Key Test Requirements**
- ✅ Must discover real running agents (no mocks)
- ✅ Must use real OpenAI API calls
- ✅ Must use real function calls (calculator, etc.)
- ✅ Must handle "Tell me a joke" and other conversational requests

## 🎯 **Success Criteria**

The example is complete when:

1. **PersonalAssistant runs and responds to "Tell me a joke"**
2. **CLI discovers PersonalAssistant automatically** 
3. **CLI can send messages and get real responses**
4. **Agent can call calculator service for math questions**
5. **All communication uses Genesis built-in methods only**

## 📝 **File Structure**

```
examples/MultiAgent/
├── agents/
│   └── personal_assistant.py     # OpenAIGenesisAgent subclass
├── interface/
│   └── cli_interface.py          # MonitoredInterface subclass  
├── test_cli.py                   # Simple test script
└── README.md                     # Usage instructions
```

## 🚨 **Final Warning**

**If you find yourself:**
- Creating custom discovery logic
- Bridging between components
- Managing DDS topics manually
- Creating wrapper classes
- Writing callback registration code

**STOP. You're reinventing Genesis. Use the working examples instead.**

## 📚 **Reference Materials**

**Study these files to understand the correct patterns:**
- `genesis_lib/monitored_interface.py` - See what's already available
- `genesis_lib/openai_genesis_agent.py` - See agent patterns
- `run_scripts/comprehensive_multi_agent_test_interface.py` - Working interface example
- Any regression test that passes - These show correct usage

**The Genesis framework already does everything. Your job is to use it correctly, not recreate it.** 