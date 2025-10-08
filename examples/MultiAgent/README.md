# Genesis Multi-Agent System Example

**Modern Multi-Agent System Featuring @genesis_tool Auto-Discovery**

This example demonstrates Genesis's revolutionary `@genesis_tool` decorator system that eliminates boilerplate and provides automatic tool discovery, schema generation, and execution.

## 🚀 Quick Start

```bash
# From examples/MultiAgent directory
./run_interactive_demo.sh
```

## 🎯 What This Demonstrates

### **Zero-Boilerplate Tool Development**
- **@genesis_tool decorators** automatically generate OpenAI tool schemas
- **Type-safe development** using Python type hints
- **No manual JSON schema definition** required
- **Automatic tool injection** into LLM clients

### **Advanced Multi-Agent Communication**
- **Agent-to-agent delegation** with automatic discovery
- **Specialized agents** with domain expertise
- **Function services** for computational tasks
- **Real-time monitoring** and tracing

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ PersonalAssistant│◄──►│   WeatherAgent   │    │ Calculator      │
│ (General Agent) │    │ (Specialized)    │    │ (Function)      │
│                 │    │                  │    │                 │
│ • Chat          │    │ • @genesis_tool  │    │ • Math ops      │
│ • Delegation    │    │ • Auto-discovery │    │ • Arithmetic    │
│ • Coordination  │    │ • Real weather   │    │ • Calculations  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📂 Directory Structure

```
examples/MultiAgent/
├── README.md                    # This file
├── USAGE.md                     # Detailed usage examples
├── run_interactive_demo.sh      # Start the demo
├── agents/                      # Agent implementations
│   ├── personal_assistant.py    # General-purpose agent
│   └── weather_agent.py         # @genesis_tool weather specialist
├── interfaces/                  # User interfaces
│   ├── interactive_cli.py       # Chat interface
│   └── quick_test.py           # Automated test
└── config/                     # Configuration files
    └── demo_config.py          # Demo settings
```

## 🛠️ Key Features Demonstrated

### 1. **@genesis_tool Decorator Magic**

**OLD WAY (Manual Schema Definition):**
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
                "location": {"type": "string", "description": "..."}
            },
            "required": ["location"]
        }
    }
}]
```

**NEW WAY (@genesis_tool Decorator):**
```python
@genesis_tool(description="Get current weather conditions worldwide")
async def get_current_weather(self, location: str) -> dict:
    """Get current weather conditions for a specific location."""
    return await self.get_weather_data(location, forecast=False)
```

### 2. **Automatic Agent Discovery**

Agents automatically discover each other and create tool schemas based on capabilities:

```python
# PersonalAssistant automatically discovers WeatherAgent and creates:
# - get_weather_info tool
# - get_meteorology_info tool  
# - use_weather_service tool
```

### 3. **Clean Demo Mode**

Professional presentation experience with configurable tracing:

- **Clean Mode (Default)**: Minimal output, perfect for demos and presentations
- **Debug Mode**: Full tracing for development and troubleshooting
- **Smart Progress Indicators**: Visual feedback during agent-to-agent communication
- **Dynamic Configuration**: Switch between modes via demo script

### 4. **Real Multi-Agent Scenarios**

**Weather Delegation:**
```
User → PersonalAssistant: "What's the weather in London?"
PersonalAssistant → WeatherAgent: Automatic delegation
WeatherAgent → OpenWeatherMap API: Real weather data
WeatherAgent → PersonalAssistant: Weather response
PersonalAssistant → User: Natural language weather report
```

**Function Calling:**
```
User → PersonalAssistant: "What is 123 * 456?"
PersonalAssistant → Calculator Service: Math function call
Calculator Service → PersonalAssistant: Result
PersonalAssistant → User: "The result is 56,088"
```

## 🧪 Demo Scenarios

### **Scenario 1: Weather Delegation**
1. Connect to PersonalAssistant
2. Ask: *"What's the weather in Tokyo, Japan?"*
3. **Result**: PersonalAssistant automatically discovers and delegates to WeatherAgent

### **Scenario 2: Direct Specialization**
1. Connect to WeatherAgent  
2. Ask: *"Give me a 5-day forecast for Paris"*
3. **Result**: WeatherAgent uses @genesis_tool methods to provide detailed forecast

### **Scenario 3: Function Calling**
1. Connect to PersonalAssistant
2. Ask: *"Calculate 987 * 654 + 321"*
3. **Result**: PersonalAssistant calls Calculator service functions

### **Scenario 4: Mixed Capabilities**
1. Connect to PersonalAssistant
2. Ask: *"What's the weather in London and calculate 15% tip on $85?"*
3. **Result**: PersonalAssistant handles both weather delegation AND math functions

## 🔧 Prerequisites

### **Required:**
- Python 3.8+
- OpenAI API key (`OPENAI_API_KEY` environment variable)

### **Optional:**
- OpenWeatherMap API key (`OPENWEATHERMAP_API_KEY`) for real weather data
- Without it, WeatherAgent uses realistic mock data

## 📋 Environment Setup

```bash
# Set OpenAI API key (required)
export OPENAI_API_KEY="your-openai-api-key"

# Set weather API key (optional - get free key at openweathermap.org)
export OPENWEATHERMAP_API_KEY="your-weather-api-key"
```

## 🚀 Running the Demo

### **Interactive Mode (Recommended)**
```bash
cd examples/MultiAgent/
./run_interactive_demo.sh
```

**The demo script offers two modes:**
- **Clean Demo Mode**: Professional output perfect for presentations
- **Debug Mode**: Full tracing for development and troubleshooting

### **Quick Test Mode**
```bash
cd examples/MultiAgent/
python interfaces/quick_test.py
```

### **Manual Mode**
```bash
# Terminal 1: Start Calculator Service
python ../../test_functions/calculator_service.py

# Terminal 2: Start WeatherAgent  
python agents/weather_agent.py

# Terminal 3: Start PersonalAssistant
python agents/personal_assistant.py

# Terminal 4: Start Interactive CLI
python interfaces/interactive_cli.py
```

## 🎯 Key Innovations

1. **Zero Boilerplate**: `@genesis_tool` eliminates manual schema definition
2. **Type Safety**: Leverages Python type hints for robust development
3. **Auto-Discovery**: Genesis automatically finds and registers tools
4. **Multi-LLM Ready**: Schema generation works with OpenAI, Anthropic, etc.
5. **Production Ready**: Real API integration with error handling
6. **Clean Demo Mode**: Professional presentation experience with configurable tracing
7. **Smart Progress Indicators**: Visual feedback during complex multi-agent operations

## 📚 Learning Path

1. **Start Here**: Run `./run_interactive_demo.sh` and try the demo scenarios
2. **Explore Code**: Examine `agents/weather_agent.py` for @genesis_tool examples
3. **Understand Flow**: Check logs to see agent-to-agent communication (enable debug mode)
4. **Experiment**: Try different queries and watch automatic delegation
5. **Build**: Create your own @genesis_tool methods

## 🔗 Related Documentation

- [Complexity Reduction Plan](../../docs/architecture/complexity.md) - The vision behind @genesis_tool
- [Agent Communication Guide](../../docs/agents/agent_to_agent_communication.md) - How agents work together
- [Function Services](../../docs/guides/function_service_guide.md) - External function integration

---

**🎉 This example showcases Genesis's transformation into a "magic decorator" system where developers write natural Python code and Genesis handles all distributed computing complexity automatically!**
