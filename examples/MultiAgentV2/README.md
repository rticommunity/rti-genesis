# Genesis Multi-Agent Demo V2

A complete demonstration of the Genesis framework's advanced multi-agent capabilities, featuring **multiple specialized agents**, **agent-to-agent communication**, **function calling**, and **interactive chat**.

## 🌟 Features

- **🤖 Multiple AI Agents**: PersonalAssistant (general) and WeatherAgent (specialized)
- **🔗 Agent-to-Agent Communication**: Agents can discover and call each other as tools
- **🔧 Function Services**: Calculator service for mathematical operations
- **🌤️ Real API Integration**: Weather data via OpenWeatherMap API (optional)
- **💬 Interactive Agent Selection**: Choose which agent to connect to
- **🔍 Auto-Discovery**: All agents and services discover each other automatically
- **📊 Full Monitoring**: Complete Genesis framework monitoring and logging
- **🚀 One-Click Launch**: Everything starts with a single command

## 🏗️ Architecture

### Multi-Agent Ecosystem
```
User Interface
    ├── PersonalAssistant (General Agent)
    │   ├── Can call → WeatherAgent (for weather queries)
    │   └── Can call → Calculator Service (for math)
    └── WeatherAgent (Weather Specialist)
        └── Direct weather expertise
```

### Demo Scenarios

1. **Agent-to-Agent Delegation**
   - Connect to PersonalAssistant
   - Ask: "What's the weather in London?"
   - PersonalAssistant → discovers and calls → WeatherAgent

2. **Direct Specialization**
   - Connect to WeatherAgent  
   - Ask: "How's the weather in Tokyo?"
   - Direct weather expertise without delegation

3. **Function Calling**
   - Connect to PersonalAssistant
   - Ask: "What is 123 + 456?"
   - PersonalAssistant → calls → Calculator Service

## 🚀 Quick Start

### Prerequisites

1. **OpenAI API Key**: Required for both agents
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

2. **Weather API Key**: Optional for real weather data
   ```bash
   export OPENWEATHERMAP_API_KEY="your-weather-api-key"
   ```
   Get a free key at: https://openweathermap.org/api
   
   Without this key, WeatherAgent uses realistic mock data.

3. **Python Environment**: Ensure dependencies are installed
   ```bash
   cd examples/MultiAgentV2
   pip install openai aiohttp  # for weather API
   ```

### 🎮 Run Interactive Demo

```bash
cd examples/MultiAgentV2
./run_interactive_demo.sh
```

The demo will:
1. ✅ Start Calculator Service
2. ✅ Start PersonalAssistant  
3. ✅ Start WeatherAgent
4. ✅ Launch Interactive CLI with agent selection

### 🧪 Run Quick Test (No Interaction)

```bash
cd examples/MultiAgentV2  
./run_multi_agent_demo.sh
```

## 💬 What You Can Try

### With PersonalAssistant
- **"Tell me a joke"** - Conversational AI
- **"What is 42 * 1337?"** - Function calling to Calculator
- **"How's the weather in Paris?"** - Agent delegation to WeatherAgent
- **"What's 100 + 200 and also the weather in Berlin?"** - Multi-tool usage

### With WeatherAgent  
- **"What's the weather in London?"** - Current weather data
- **"Weather forecast for Tokyo"** - Multi-day forecast
- **"Is it sunny in California?"** - Weather conditions
- **"Temperature in New York"** - Specific weather metrics

### Multi-Agent Patterns
- **Agent Discovery**: Both agents automatically discover each other
- **Tool Delegation**: PersonalAssistant can call WeatherAgent when needed
- **Service Integration**: Both agents can call Calculator Service
- **Graceful Fallback**: WeatherAgent works with or without API key

## 🛠️ Technical Implementation

### Agent Types

**PersonalAssistant** (`agents/personal_assistant.py`)
- Based on `OpenAIGenesisAgent`
- Enables `agent_communication=True` for tool discovery
- Can discover and call other agents as OpenAI tools
- Handles general conversation and delegates specialized tasks

**WeatherAgent** (`agents/weather_agent.py`)  
- Based on `OpenAIGenesisAgent`
- Specialized for weather queries and analysis
- Real API integration with OpenWeatherMap
- Fallback to realistic mock data when no API key
- Advertises weather-specific capabilities for discovery

### Function Services

**Calculator Service** (`../../test_functions/calculator_service.py`)
- Provides add, subtract, multiply, divide functions
- Automatically discovered by both agents
- Used via OpenAI function calling

### Interactive Interface

**MultiAgentInteractiveCLI** (`interactive_cli.py`)
- Based on `MonitoredInterface`
- Groups agents by specialization (general vs weather)
- Provides user-friendly agent selection
- Supports rich conversational interface

## 🔧 Configuration

### Environment Variables
- `OPENAI_API_KEY` - **Required** for LLM functionality
- `OPENWEATHERMAP_API_KEY` - **Optional** for real weather data

### Logging Levels
```bash
# Verbose logging
export GENESIS_LOG_LEVEL=DEBUG

# Quiet logging (default)
export GENESIS_LOG_LEVEL=WARNING
```

## 📊 Expected Behavior

### Startup Sequence
1. ✅ Calculator service advertises 4 math functions
2. ✅ PersonalAssistant starts and discovers calculator + enables agent communication
3. ✅ WeatherAgent starts and advertises weather capabilities  
4. ✅ Both agents discover each other automatically
5. ✅ Interactive CLI discovers both agents and presents selection

### Agent Selection
- **Auto-select** if only one agent available
- **Manual selection** with clear descriptions of capabilities
- **Graceful handling** of connection failures

### Communication Patterns
- **Function Calls**: Agent → Calculator Service  
- **Agent Calls**: PersonalAssistant → WeatherAgent
- **Direct Queries**: User → WeatherAgent
- **Mixed Interactions**: User → PersonalAssistant → (WeatherAgent + Calculator)

## 🚨 Troubleshooting

### Common Issues
1. **No agents discovered**: Check if services started properly
2. **OpenAI errors**: Verify `OPENAI_API_KEY` is set correctly
3. **Weather mock data**: Expected without `OPENWEATHERMAP_API_KEY`
4. **Connection timeouts**: Agents may need more time to discover each other

### Debug Mode
```bash
export DEBUG=true
./run_interactive_demo.sh
```

## 🎯 Key Learning Points

This demo showcases the **complete Genesis agent-as-tool pattern**:

1. **Dynamic Discovery** - Agents find each other automatically
2. **Capability-Based Routing** - PersonalAssistant routes weather queries to WeatherAgent
3. **Tool Composition** - Single conversation can use multiple tools/agents
4. **Specialization vs Generalization** - Direct specialist vs delegating generalist
5. **Real-World Integration** - Actual APIs + service composition
6. **User Choice** - Flexibility in how to access capabilities

This demonstrates how Genesis enables building **scalable, composable AI systems** where specialized agents can work together seamlessly!

---

**🚀 This showcases the complete Genesis framework in action!**