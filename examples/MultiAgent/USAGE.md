# Genesis Multi-Agent System - Usage Guide

**Detailed usage examples and troubleshooting for the @genesis_tool demo**

## 🚀 Quick Start

```bash
# 1. Set required environment variable
export OPENAI_API_KEY="your-openai-api-key"

# 2. Set optional environment variable for real weather data
export OPENWEATHERMAP_API_KEY="your-weather-api-key"

# 3. Run the demo
cd examples/MultiAgent/
./run_interactive_demo.sh
```

## 📋 Environment Setup

### **Required:**
```bash
export OPENAI_API_KEY="sk-..."  # Get from https://platform.openai.com/api-keys
```

### **Optional (but recommended):**
```bash
export OPENWEATHERMAP_API_KEY="..."  # Get free from https://openweathermap.org/api
```

### **Check Environment:**
```bash
python config/demo_config.py
```

## 🎯 Demo Scenarios

### **1. Weather Delegation (Agent-to-Agent)**

**Connect to:** PersonalAssistant
**Query:** `What's the weather in Tokyo, Japan?`

**What happens:**
1. PersonalAssistant receives your query
2. Automatically discovers WeatherAgent via DDS
3. Creates agent tool schema for WeatherAgent
4. Delegates weather query to WeatherAgent
5. WeatherAgent uses `@genesis_tool` methods to get weather data
6. Returns result through PersonalAssistant

**Example output:**
```
PersonalAssistant> What's the weather in Tokyo, Japan?
📤 Sending: What's the weather in Tokyo, Japan?
⏳ Processing...
📥 PersonalAssistant: The current weather in Tokyo is 22.5°C with partly cloudy skies. 
Humidity is at 68% and there's a light breeze at 3.2 m/s. It's a comfortable day 
for outdoor activities!
```

### **2. Function Calling (Agent-to-Service)**

**Connect to:** PersonalAssistant
**Query:** `Calculate 987 * 654`

**What happens:**
1. PersonalAssistant receives math query
2. Automatically discovers Calculator service functions
3. Creates function tool schemas for math operations
4. Calls appropriate calculator function
5. Returns mathematical result

**Example output:**
```
PersonalAssistant> Calculate 987 * 654
📤 Sending: Calculate 987 * 654
⏳ Processing...
📥 PersonalAssistant: The result of 987 × 654 is 645,498.
```

### **3. @genesis_tool Direct Usage**

**Connect to:** WeatherAgent
**Query:** `Give me a 5-day forecast for Paris, France`

**What happens:**
1. WeatherAgent receives forecast query
2. OpenAI automatically calls `get_weather_forecast()` method (decorated with `@genesis_tool`)
3. Method executes with type-safe parameters
4. Returns structured forecast data

**Example output:**
```
WeatherExpert> Give me a 5-day forecast for Paris, France
📤 Sending: Give me a 5-day forecast for Paris, France
⏳ Processing...
📥 WeatherExpert: Here's the 5-day forecast for Paris:

Day 1: 18°C, partly cloudy, 65% humidity
Day 2: 20°C, sunny, 45% humidity  
Day 3: 16°C, light rain, 80% humidity
Day 4: 19°C, overcast, 70% humidity
Day 5: 21°C, sunny, 50% humidity

Perfect week ahead with only light rain on Wednesday!
```

### **4. Mixed Capabilities**

**Connect to:** PersonalAssistant
**Query:** `What's the weather in London and calculate 15% tip on $85?`

**What happens:**
1. PersonalAssistant analyzes the compound query
2. Delegates weather part to WeatherAgent
3. Handles math calculation via Calculator service
4. Combines both results intelligently

## 🛠️ Advanced Usage

### **Interactive CLI Commands**

While connected to an agent:
- `scenarios` - Show demo scenarios
- `quit` / `exit` - Disconnect from current agent
- Any natural language query - Send to agent

### **Quick Test Mode**

Run automated tests without interaction:
```bash
python interfaces/quick_test.py
```

### **Manual Service Startup**

Start services individually for debugging:

```bash
# Terminal 1 - Calculator Service
python ../../test_functions/calculator_service.py

# Terminal 2 - WeatherAgent  
python agents/weather_agent.py

# Terminal 3 - PersonalAssistant
python agents/personal_assistant.py

# Terminal 4 - Interactive CLI
python interfaces/interactive_cli.py
```

## 🔍 Understanding @genesis_tool

### **Before @genesis_tool (Manual Schema):**
```python
# 50+ lines of manual JSON schema definition
weather_tools = [{
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get current weather conditions...",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and country"}
            },
            "required": ["location"]
        }
    }
}]
```

### **After @genesis_tool (Automatic):**
```python
@genesis_tool(description="Get current weather conditions worldwide")
async def get_current_weather(self, location: str) -> dict:
    """Get current weather conditions for a specific location."""
    return await self._fetch_weather_data(location, forecast=False)
```

**Genesis automatically:**
- Generates OpenAI schema from type hints
- Handles parameter validation
- Injects tools into OpenAI client
- Routes tool calls to methods
- Manages execution and responses

## 📊 Monitoring and Tracing

### **Agent Discovery Logs**
Watch for agent discovery in the console:
```
🔍 Will automatically discover:
   • WeatherAgent (for weather queries)
   • Calculator Service (for math operations)
```

### **Tool Generation Logs**
Genesis shows when tools are created:
```
🛠️ @genesis_tool methods will be auto-discovered and injected into OpenAI
```

### **Delegation Traces**
Look for delegation indicators:
```
📤 Delegating weather query to WeatherAgent...
📥 Received weather data from WeatherAgent
```

## 🔧 Troubleshooting

### **"No agents discovered"**

**Problem:** CLI shows no available agents
**Solutions:**
1. Wait longer (agents need 8+ seconds to start)
2. Check if agent processes are running
3. Verify OPENAI_API_KEY is set
4. Check for Genesis library import errors

### **"Failed to connect to agent"**

**Problem:** Cannot connect to discovered agent
**Solutions:**
1. Restart the demo script
2. Check agent logs for errors
3. Verify DDS is working properly
4. Try connecting to a different agent

### **"Weather delegation unsuccessful"**

**Problem:** PersonalAssistant doesn't delegate to WeatherAgent
**Solutions:**
1. Ensure WeatherAgent is running and discovered
2. Try more specific weather queries
3. Check agent capability matching
4. Verify agent-to-agent communication is enabled

### **"@genesis_tool methods not working"**

**Problem:** Tool methods not being called
**Solutions:**
1. Check method is decorated with `@genesis_tool`
2. Verify type hints are correct
3. Ensure method is `async` if needed
4. Check Genesis library version supports auto-discovery

### **"Mock weather data instead of real"**

**Problem:** Getting fake weather data
**Solutions:**
1. Set `OPENWEATHERMAP_API_KEY` environment variable
2. Get free API key from https://openweathermap.org/api
3. Restart WeatherAgent after setting API key

## 🎛️ Demo Mode Configuration

### **Clean Demo Mode (Default)**

The demo runs in **clean mode** by default, providing a professional presentation experience:

- ✅ **Minimal output** - Only essential information shown
- ✅ **Clean interactions** - No debug clutter during agent communication
- ✅ **Progress indicators** - Smart progress feedback for weather queries
- ✅ **Professional appearance** - Perfect for presentations and demos

### **Debug Mode (For Development)**

Enable full tracing for development and troubleshooting:

```python
# In config/demo_config.py
ENABLE_DEMO_TRACING = True  # Change from False to True
```

**Debug mode provides:**
- 🔍 **Full agent tracing** - See all OpenAI API calls and responses
- 🔍 **Genesis library internals** - View DDS communication and discovery
- 🔍 **Agent-to-agent communication** - Monitor delegation and RPC calls
- 🔍 **Function discovery** - Watch function registration and schema generation

### **Tracing Configuration Options**

```python
# config/demo_config.py

# Master control - turns everything on/off
ENABLE_DEMO_TRACING = False  # True for debug, False for clean demos

# Individual controls (only used if ENABLE_DEMO_TRACING is True)
ENABLE_AGENT_TRACING = True      # Agent-level tracing
ENABLE_GENESIS_TRACING = True    # Genesis library internals  
ENABLE_DDS_TRACING = False       # DDS communication (very verbose)
```

### **Dynamic Mode Switching**

The `run_interactive_demo.sh` script offers tracing control:

```bash
./run_interactive_demo.sh
# Choose between:
# 1. Clean Demo Mode (recommended for presentations)
# 2. Debug Mode (full tracing for development)
```

### **Configuration Effects**

**Clean Demo Mode:**
```
PersonalAssistant> What's the weather in London?
📤 Sending: What's the weather in London?
⏳ Processing weather query (may involve agent delegation)...
✅ 🌤️ Consulting weather specialist... completed!
📥 PersonalAssistant: [clean weather response]
```

**Debug Mode:**
```
PersonalAssistant> What's the weather in London?
📤 Sending: What's the weather in London?
🔔 PRINT: _handle_agent_requests() found 1 requests for agent WeatherExpert
📥 PRINT: Extracted request data: {'message': 'current weather in London', ...}
🔄 PRINT: About to call process_agent_request() method...
✅ PRINT: process_agent_request() returned: {...}
📤 PRINT: About to create reply sample with data: {...}
✅ 🌤️ Consulting weather specialist... completed!
📥 PersonalAssistant: [weather response with debug info]
```

## 💡 Tips and Best Practices

### **Writing Effective Queries**

**Good weather queries:**
- "What's the weather in London, UK?"
- "Give me a 5-day forecast for Tokyo"
- "How's the weather in Paris, France?"

**Good math queries:**
- "Calculate 123 * 456"
- "What's 15% of $85?"
- "Add 987 and 654"

**Good mixed queries:**
- "Weather in London and calculate 20% tip on $75"
- "Tell me about Tokyo weather and solve 456 * 789"

### **Exploring @genesis_tool Features**

Try these WeatherAgent queries:
- "Analyze weather conditions: 25°C, sunny, 60% humidity"
- "Get weather alerts for Miami, Florida"
- "Compare current weather in London vs Paris"

### **Understanding Agent Roles**

- **PersonalAssistant:** General coordinator, delegates to specialists
- **WeatherAgent:** Weather specialist using @genesis_tool
- **Calculator Service:** Math function provider

## 🎓 Learning Objectives

After completing this demo, you should understand:

1. **Zero-Boilerplate Development:** How `@genesis_tool` eliminates manual schema definition
2. **Agent Discovery:** How Genesis automatically finds and connects agents
3. **Automatic Delegation:** How PersonalAssistant routes queries to specialists
4. **Function Integration:** How external services integrate seamlessly
5. **Type Safety:** How Python type hints drive schema generation
6. **Production Readiness:** How real APIs integrate with mock fallbacks

## 🔗 Next Steps

1. **Examine the Code:** Look at `agents/weather_agent.py` to see @genesis_tool in action
2. **Create Your Own Agent:** Try adding new @genesis_tool methods
3. **Build New Services:** Create your own function services
4. **Explore Advanced Features:** Check out Genesis monitoring and tracing
5. **Read the Documentation:** Review the main README.md for architecture details

---

**🌟 The @genesis_tool decorator system transforms Genesis into a "magic" framework where developers write natural Python code and Genesis handles all distributed computing complexity automatically!** 