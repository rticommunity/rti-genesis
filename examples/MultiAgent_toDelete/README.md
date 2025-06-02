# Multi-Agent Example: Smart Assistant Ecosystem

## 🚀 Quick Start

Welcome to the Genesis Multi-Agent Smart Assistant Ecosystem! This example demonstrates how multiple AI assistants can work together to provide comprehensive help across different domains.

### Prerequisites

- Python 3.8+
- OpenAI API key (for AI assistants)
- OpenWeatherMap API key (optional, for weather features)

### Installation

1. **Clone and navigate to the example:**
   ```bash
   cd examples/MultiAgent
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export OPENWEATHERMAP_API_KEY="your-weather-api-key"  # optional
   ```

4. **Launch the system:**
   ```bash
   ./run_multi_agent_demo.sh
   ```

## 🎯 What This Example Demonstrates

This example showcases the key capabilities of the Genesis framework:

- **🔄 Automatic Agent Discovery** - Agents find each other without manual configuration
- **🤖 Multi-Agent Collaboration** - AI assistants work together on complex tasks
- **🛠️ Capability-based Routing** - Agents call each other based on expertise, not names
- **📊 Real-time Monitoring** - See how requests flow through the system
- **🔧 Easy Extensibility** - Add new agents without modifying existing ones

## 🏗️ Genesis Framework Principles

**Genesis Handles All Complexity**: This example demonstrates how Genesis manages everything automatically:

- ✅ **Zero DDS Knowledge Required** - No manual topic subscription or callback registration
- ✅ **Automatic Discovery & Communication** - Agents find and talk to each other seamlessly  
- ✅ **Built-in Monitoring** - Request tracking and performance metrics included
- ✅ **Resource Management** - Cleanup and lifecycle handled by the framework
- ✅ **Error Recovery** - Built-in resilience and reconnection capabilities

**Developer Experience**: Write business logic, let Genesis handle the infrastructure. If you encounter issues, check the regression tests in `/run_scripts/` for working reference implementations.

## 🏗️ System Architecture

### Assistant Types

#### **General Assistants** (Choose one to interact with)
- **🤝 Personal Assistant** - Friendly, helpful general-purpose AI
- **💼 Business Assistant** - Professional, efficiency-focused AI
- **🎨 Creative Assistant** - Artistic, imaginative AI for creative tasks

#### **Specialized Experts** (Called automatically as needed)
- **🌤️ Weather Expert** - Real weather data and forecasting
- **✈️ Travel Planner** - Trip planning and destination recommendations  
- **💰 Finance Advisor** - Financial calculations and investment advice
- **🏃 Health & Wellness** - Health tips and wellness recommendations

#### **Function Services** (Computational tools)
- **🧮 Calculator** - Mathematical computations
- **📝 Text Processor** - Text analysis and manipulation
- **📊 Data Analyzer** - Statistical analysis and reporting

## 💬 Example Interactions

### 🌟 Travel Planning Scenario
```
You: "I want to plan a weekend trip to Paris"

Personal Assistant:
├── Consults Travel Planner → "Paris weekend itinerary recommendations"
├── Consults Weather Expert → "Paris weather forecast this weekend"  
├── Consults Calculator → "Budget estimation for 2-day Paris trip"
└── Provides comprehensive travel plan with weather considerations
```

### 💼 Business Analysis Scenario
```
You: "Analyze this quarter's sales growth"

Business Assistant:
├── Consults Data Analyzer → "Statistical analysis of sales figures"
├── Consults Calculator → "Growth rate and trend calculations"
├── Consults Text Processor → "Generate executive summary"
└── Provides detailed business report with insights
```

### 🎨 Creative Project Scenario
```
You: "Help me plan a themed dinner party"

Creative Assistant:
├── Consults Travel Planner → "Cultural themes from different countries"
├── Consults Weather Expert → "Seasonal ingredients and considerations"
├── Consults Finance Advisor → "Budget planning for party expenses"
└── Creates themed party plan with cultural elements and budget
```

## 🖥️ User Interface

### Main Menu
When you launch the system, you'll see:

```
🤖 Genesis Multi-Agent Assistant Ecosystem
============================================

Available General Assistants:
1. 🤝 Personal Assistant - Friendly, helpful general-purpose AI
2. 💼 Business Assistant - Professional, efficiency-focused AI  
3. 🎨 Creative Assistant - Artistic, imaginative AI

System Status:
✅ 3 General Agents   ✅ 4 Specialized Agents   ✅ 3 Services

Choose an assistant (1-3) or:
[s] System Status  [h] Help  [q] Quit
```

### Conversation Mode
After selecting an assistant:

```
🤝 Personal Assistant Ready!
I can help with general tasks and automatically consult specialists as needed.

Connected Specialists: Weather Expert, Travel Planner, Finance Advisor, Health & Wellness
Available Services: Calculator, Text Processor, Data Analyzer

You: I need help planning a vacation
Personal Assistant: I'd be happy to help you plan a vacation! Let me gather some information...

[Consulting Travel Planner for destination recommendations...]
[Consulting Weather Expert for seasonal considerations...]

Based on specialist consultation, here are some great vacation ideas...
```

### System Status View
```
🔍 System Status Dashboard
=========================

General Agents (3):
✅ Personal Assistant    Response: 1.2s    Calls: 15
✅ Business Assistant    Response: 0.9s    Calls: 8  
✅ Creative Assistant    Response: 1.5s    Calls: 12

Specialized Agents (4):
✅ Weather Expert        Response: 2.1s    Calls: 7
✅ Travel Planner        Response: 1.8s    Calls: 5
✅ Finance Advisor       Response: 1.1s    Calls: 9
✅ Health & Wellness     Response: 1.3s    Calls: 3

Function Services (3):
✅ Calculator           Response: 0.1s    Calls: 22
✅ Text Processor       Response: 0.3s    Calls: 11
✅ Data Analyzer        Response: 0.8s    Calls: 6

Recent Activity:
• Personal Assistant → Travel Planner: "Paris weekend recommendations"
• Travel Planner → Weather Expert: "Paris weather forecast"  
• Business Assistant → Calculator: "Q3 growth rate calculation"
```

## 🛠️ Technical Details

### How Agent Discovery Works

1. **Automatic Discovery**: When launched, each agent automatically announces its capabilities
2. **Real-time Updates**: New agents are discovered immediately when they join
3. **Capability Mapping**: Agents are made available as tools based on their specializations
4. **Dynamic Routing**: The LLM chooses which specialist to consult based on the user's request

### Agent Communication Flow

```
User Request → General Assistant → LLM Analysis → Tool Selection → Specialist Agent → Response
                     ↑                                    ↓
              Context Preservation ←←←←←←←←←←←← Response Integration
```

### Configuration

The system uses sensible defaults but can be customized:

- **Agent Personalities**: Modify `config/agent_configs.py`
- **System Settings**: Adjust `config/system_settings.py`
- **API Keys**: Set via environment variables
- **Logging**: Configure in launch script

## 🔧 Customization

### Adding a New Specialized Agent

1. **Create the agent file** in `agents/specialized/`
2. **Define capabilities and specializations**
3. **Implement the processing logic**
4. **Launch with the system** - it will be discovered automatically!

Example:
```python
class MusicAgent(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="MusicExpert",
            base_service_name="MusicService", 
            agent_type="SPECIALIZED_AGENT",
            enable_agent_communication=True
        )
        self.set_agent_capabilities(
            supported_tasks=["music_recommendations", "playlist_creation"],
            additional_capabilities={
                "specializations": ["music", "audio", "entertainment"],
                "capabilities": ["song_search", "artist_info", "genre_analysis"]
            }
        )
```

### Adding a New Function Service

1. **Create service file** in `agents/services/`
2. **Extend EnhancedServiceBase**
3. **Register functions** with `@genesis_function` decorator
4. **Launch with the system**

## 🐛 Troubleshooting

### Common Issues

**"No agents discovered"**
- Check that all processes are running
- Verify network connectivity
- Wait a few seconds for discovery to complete

**"OpenAI API errors"**
- Verify your `OPENAI_API_KEY` is set correctly
- Check your API usage limits
- Ensure you have access to the required models

**"Weather features not working"**
- Set your `OPENWEATHERMAP_API_KEY` environment variable
- Weather features will gracefully degrade without the API key

**"Slow responses"**
- Check your internet connection
- Monitor system resources
- Review the system status dashboard for bottlenecks

### Debug Mode

Launch with debug mode for detailed logging:
```bash
DEBUG=1 ./run_multi_agent_demo.sh
```

### Getting Help

- Check the logs in `logs/` directory
- Review the design document (`DESIGN.md`)
- Check the implementation checklist (`IMPLEMENTATION_CHECKLIST.md`)

## 🎓 Learning Objectives

After using this example, you'll understand:

1. **Multi-Agent Architecture** - How to design collaborative agent systems
2. **Automatic Discovery** - How agents find and communicate with each other
3. **Capability-based Routing** - How LLMs choose the right specialist for each task
4. **Service Integration** - How to combine agents with function services
5. **User Experience Design** - How to build intuitive interfaces for agent systems
6. **Production Practices** - Error handling, monitoring, and scalability patterns

## 🚀 Next Steps

- Try all three general assistants to see their different personalities
- Test complex multi-step scenarios that require multiple specialists
- Monitor the system status to understand the communication patterns
- Experiment with adding your own specialized agents
- Explore the code to understand the implementation patterns

This example demonstrates the power and simplicity of the Genesis framework for building production-ready multi-agent systems. Have fun exploring! 🎉 