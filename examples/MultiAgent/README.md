# Genesis Multi-Agent System Example

Modern multi-agent system demonstrating Genesis's `@genesis_tool` decorator for automatic tool discovery, schema generation, and agent-to-agent communication.

## Quick Start

```bash
# From examples/MultiAgent directory
export OPENAI_API_KEY="your-key"  # Required
export OPENWEATHERMAP_API_KEY="your-key"  # Optional (for real weather data)

./run_interactive_demo.sh
```

## What This Demonstrates

- **`@genesis_tool` decorators** - Zero-boilerplate tool development with automatic schema generation
- **Agent-to-agent communication** - Automatic discovery and delegation between agents
- **Function services** - Integration with computational services (Calculator)
- **Real API integration** - Live weather data from OpenWeatherMap

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ PersonalAssistant│◄──►│   WeatherAgent   │    │ Calculator      │
│ (Coordinator)   │    │ (@genesis_tool)  │    │ (Service)       │
│                 │    │                  │    │                 │
│ • Delegation    │    │ • Weather data   │    │ • Math ops      │
│ • Routing       │    │ • Forecasts      │    │ • Calculations  │
│ • Coordination  │    │ • Auto-discovery │    │ • Functions     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Directory Structure

```
examples/MultiAgent/
├── README.md                    # This file
├── run_interactive_demo.sh      # Launch the demo
├── agents/                      # Agent implementations
│   ├── personal_assistant.py    # General coordinator agent
│   └── weather_agent.py         # Specialized weather agent
├── interfaces/                  # User interfaces
│   ├── interactive_cli.py       # Chat interface
│   ├── gui_interface.py         # Web interface
│   └── quick_test.py           # Automated test
└── config/                     # Configuration
    └── demo_config.py          # Environment settings
```

## Key Features

### @genesis_tool Decorator

**Before (Manual Schema):**
```python
# 50+ lines of manual JSON schema definition
weather_tools = [{
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get current weather...",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            }
        }
    }
}]
```

**After (@genesis_tool):**
```python
@genesis_tool(description="Get current weather conditions worldwide")
async def get_current_weather(self, location: str) -> dict:
    """Get current weather for a location."""
    return await self.get_weather_data(location)
```

### Automatic Agent Discovery

PersonalAssistant automatically discovers WeatherAgent and creates tools for delegation:

```python
# Auto-generated tools based on discovered agents:
# - use_weather_service(query: str)
# - delegate_to_weather_expert(location: str)
```

## Demo Scenarios

### 1. Weather Delegation (Agent-to-Agent)
```
You: What's the weather in Tokyo?
PersonalAssistant → WeatherAgent → OpenWeatherMap API
Response: Current weather is 22.5°C with partly cloudy skies...
```

### 2. Function Calling (Agent-to-Service)
```
You: Calculate 987 * 654
PersonalAssistant → Calculator Service
Response: The result is 645,498
```

### 3. Direct Specialization
```
You: Give me a 5-day forecast for Paris
WeatherAgent → OpenWeatherMap API
Response: [Detailed 5-day forecast]
```

### 4. Mixed Capabilities
```
You: Weather in London and calculate 15% tip on $85
PersonalAssistant → WeatherAgent (weather) + Calculator (math)
Response: [Weather data] and the 15% tip is $12.75
```

## Running the Demo

### Interactive Mode (Recommended)
```bash
./run_interactive_demo.sh

# Choose interface:
# 1. Interactive CLI - Chat interface
# 2. Web GUI - Modern web interface with visualization
# 3. Quick Test - Automated test scenarios
```

### Quick Test Mode
```bash
python interfaces/quick_test.py
```

### Manual Mode (Advanced)
```bash
# Terminal 1: Calculator Service
python ../../test_functions/services/calculator_service.py

# Terminal 2: WeatherAgent
python agents/weather_agent.py

# Terminal 3: PersonalAssistant
python agents/personal_assistant.py

# Terminal 4: Interface
python interfaces/interactive_cli.py
```

## Prerequisites

**Required:**
- Python 3.8+
- OpenAI API key: `export OPENAI_API_KEY="sk-..."`

**Optional:**
- OpenWeatherMap API key for real weather data: `export OPENWEATHERMAP_API_KEY="..."`
- Get free key at: https://openweathermap.org/api
- Without it, WeatherAgent uses mock data

**Check Environment:**
```bash
python config/demo_config.py
```

## What Makes This Example Special

1. **Zero Boilerplate** - `@genesis_tool` eliminates manual schema definition
2. **Type Safety** - Leverages Python type hints for robust development  
3. **Auto-Discovery** - Agents find each other automatically via DDS
4. **Production Ready** - Real API integration with error handling
5. **Clean Demo Mode** - Professional output for presentations
6. **Multi-Agent Patterns** - Demonstrates coordination and delegation

## Example Output

```bash
$ ./run_interactive_demo.sh

🚀 Genesis Multi-Agent System v3.0
🤖 Model: gpt-4o
✅ All services started successfully!

Choose agent:
  1. PersonalAssistant (General coordinator)
  2. WeatherAgent (Weather specialist)

PersonalAssistant> What's the weather in Tokyo and calculate 50 * 25?

📤 Sending query...
⏳ Processing (delegating to WeatherAgent)...
⏳ Processing (calling Calculator)...

📥 Response:
The current weather in Tokyo is 22.5°C with partly cloudy skies and 68% 
humidity. It's a pleasant day!

The result of 50 × 25 is 1,250.
```

## Troubleshooting

**"OPENAI_API_KEY not set"**
- Export your key: `export OPENAI_API_KEY="sk-..."`

**"No weather data"**
- Either set `OPENWEATHERMAP_API_KEY` or use mock data (automatic)

**"Services not connecting"**
- Wait 5-10 seconds for DDS discovery
- Check all services are running in demo script output

**"Agent not responding"**
- Check terminal output for errors
- Verify API keys are valid
- Try debug mode for detailed logs

## See Also

- `examples/StandaloneGraphViewer/` - Visualize multi-agent interactions
- `tests/stress/` - Stress testing tools for large-scale deployments
- Genesis documentation for advanced agent development
