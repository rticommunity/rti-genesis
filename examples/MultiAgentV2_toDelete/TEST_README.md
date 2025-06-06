# Multi-Agent System Testing

This directory contains comprehensive tests for the Genesis Multi-Agent system, demonstrating dynamic agent discovery and capability-driven interactions.

## Test Architecture

The test system follows proper Genesis principles:

### 🏗️ **Production Code**: Dynamic & Event-Driven
- Interface discovers agents based on advertised capabilities
- No hardcoded agent types or assumptions
- Truly generic multi-agent interaction patterns

### 🧪 **Test Code**: Deterministic & Controlled  
- Starts specific known agents for reproducible testing
- Validates dynamic discovery works correctly
- Tests both agent types with known expected behaviors

## Available Tests

### 1. Automated Test Suite
```bash
./test_multi_agent_system.sh auto
```

**What it does:**
- Cleans up any existing agents
- Starts Calculator Service, PersonalAssistant, WeatherAgent
- Tests dynamic discovery (interface finds agents automatically)
- Tests capability extraction (agents advertise what they can do)
- Tests PersonalAssistant interaction (jokes, conversations)
- Tests WeatherAgent interaction (weather queries)
- Tests math capability (PersonalAssistant → Calculator Service)
- Validates all communication chains work
- Cleans up automatically

**Expected Results:**
```
🧪 Starting Comprehensive Multi-Agent Test
🧹 Cleaning up existing agent processes...
🧮 Starting Calculator Service...
🚀 Starting test agents...
⏳ Waiting for agents to initialize...
🔍 Testing Dynamic Agent Discovery...
📊 Discovered 2 agents
🎯 Testing Capability Extraction...
💬 Testing interaction with personal agent...
💬 Testing interaction with weather agent...
🎉 ALL TESTS PASSED! Multi-agent system working correctly
```

### 2. Manual Interactive Testing
```bash
./test_multi_agent_system.sh manual
```

**What it does:**
- Starts the same agents as automated test
- Launches interactive CLI for manual testing
- Allows you to chat with different agent types
- Demonstrates real-time discovery and interaction

**Example Session:**
```
📊 Discovery Results:
============================================================
🤖 1. PersonalAssistant
   ID: abc123def456...
   Service: OpenAIChat
   Capabilities: text_generation, conversation

🤖 2. WeatherAgent  
   ID: def789ghi012...
   Service: WeatherService
   Capabilities: weather, meteorology, forecasting

🎯 Agent Selection:
Choose which agent to connect to:

Enter agent number (1-2): 1
🔗 Connecting to PersonalAssistant...
✅ Connected to PersonalAssistant!

💬 Welcome to Genesis Multi-Agent Chat!
You: Tell me a joke
PersonalAssistant: Why don't scientists trust atoms? Because they make up everything!

You: What's 123 + 456?
PersonalAssistant: Let me calculate that for you... 123 + 456 = 579

You: What's the weather in London?
PersonalAssistant: I'll check the weather for you... *calls WeatherAgent*
The current weather in London is partly cloudy with a temperature of 15°C...
```

### 3. Cleanup Only
```bash
./test_multi_agent_system.sh clean
```

Kills any running agent processes without starting new ones.

## Integration with Main Test Suite

The automated test is integrated into the main Genesis test suite:

```bash
cd ../../run_scripts
./run_all_tests.sh
```

The multi-agent test runs as part of the comprehensive Genesis validation.

## Key Test Validations

### ✅ Dynamic Discovery
- Interface discovers agents without hardcoded knowledge
- Capability extraction works from agent advertisements
- Multiple agent types are properly recognized

### ✅ Agent Communication  
- PersonalAssistant can handle general conversations
- WeatherAgent provides specialized weather data
- PersonalAssistant can call Calculator Service for math
- Agent-to-agent communication works (PersonalAssistant → WeatherAgent)

### ✅ Architecture Principles
- **Production**: Interface remains generic and capability-driven
- **Testing**: Uses deterministic agents for reproducible results
- **Separation**: Test code doesn't pollute production with hardcoded assumptions

## Troubleshooting

### No Agents Discovered
```bash
# Check if agents are running
ps aux | grep "personal_assistant\|weather_agent"

# Check DDS connectivity
rtiddsspy -printSample
```

### Test Timeouts
- Increase timeout in test script if needed
- Check for API key availability (OpenAI for PersonalAssistant)
- Verify calculator service can start

### Connection Failures
- Ensure proper cleanup between test runs
- Check for port conflicts or DDS domain issues
- Verify all dependencies are installed

## Architecture Benefits

This test system demonstrates the power of Genesis architecture:

1. **Extensibility**: Add new agent types without changing interface code
2. **Modularity**: Each agent advertises its own capabilities
3. **Testability**: Deterministic tests validate dynamic behavior
4. **Maintainability**: Clear separation between production and test logic

The interface will work with any agents that follow Genesis patterns, making the system truly scalable and composable. 