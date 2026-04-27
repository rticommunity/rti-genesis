# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

when testing or writing new test scripts, it is best to execute agents, services, and interfaces with a bash script with a timeout since agent, services, and interfaces are indefinately executing applications.

This project does not use pytest!  Since PyTest does not handle distributed environments well, use ./run_scripts/run_all_tests.sh for the comprehensive unit tests.

### Setup and Environment
```bash
# Initial setup (installs dependencies, configures RTI DDS, sets up virtual environment)
./setup.sh

# Activate environment for development
source venv/bin/activate && source .env

# Verify RTI DDS installation
python -c "import rti.connextdds as dds; print('RTI Connext DDS is available!')"
```
### Project structure
# library (what we are developing)

genesis_lib/

# documents

docs/

# testing scripts

run_scripts/

# supporting test functions and scripts

test_functions/

### Testing
```bash
# Run unit tests
pytest

# Run comprehensive multi-agent test suite
./run_scripts/test_agent_to_agent_communication.py

# Run all tests
./run_scripts/run_all_tests.sh

# Run specific test scripts
python test_rti_dds.py
python test_functions/test_monitoring.py

# Test with RTI DDS spy for monitoring
$NDDSHOME/bin/rtiddsspy -domainId 0 -verbosity 3
```

### Running Examples
```bash
# Hello World example (basic function calling)
cd examples/HelloWorld && ./run_hello_world.sh

# Revolutionary Multi-Agent example with agent-as-tool pattern
cd examples/MultiAgent && ./run_interactive_demo.sh

# Run multi-agent demo
./run_multi_agent_demo.sh

# Example interface with agent and service
cd examples/ExampleInterface && ./run_example.sh
```

### Development Tools
```bash
# Install package in development mode
pip install -e .

# Monitor Genesis network activity
python genesis_monitor.py

# Run DDS spy to observe all network traffic
rtiddsspy -domainId 0 -verbosity 2
```

## Architecture Overview

### Core Philosophy
GENESIS is a distributed AI agent framework built on RTI Connext DDS that enables automatic agent discovery, function sharing, and revolutionary agent-as-tool integration. The key innovation is the **agent-as-tool pattern** where agents are automatically discovered and converted to OpenAI tool schemas for seamless LLM integration.

### System Architecture
- **DDS-Powered Communication**: All discovery, function calls, and monitoring use RTI Connext DDS
- **Automatic Discovery**: Zero-configuration agent and function discovery via DDS topics
- **Agent-as-Tool Pattern**: Agents automatically become available as LLM tools
- **Function Registry**: Distributed function discovery and execution
- **Comprehensive Monitoring**: Real-time observability of all network activity

### Key Components

#### Base Classes
- `GenesisApp`: Base class providing DDS infrastructure and function registry
- `GenesisAgent`: Base agent class with DDS communication capabilities  
- `OpenAIGenesisAgent`: Enhanced agent with LLM integration and agent-as-tool support
- `GenesisInterface`: Interface for interacting with agents
- `EnhancedServiceBase`: Base class for creating function services

#### Core Services  
- `FunctionRegistry`: Manages function discovery and execution via DDS
- `AgentCommunication`: Handles agent-to-agent communication
- `MonitoringSystem`: Publishes lifecycle and chain events for observability

#### Revolutionary Features
- **@genesis_function**: Zero-boilerplate function registration with automatic schema generation
- **@genesis_tool**: Marks agent methods as auto-discoverable tools for LLMs
- **Agent-as-Tool Engine**: Automatically converts discovered agents to OpenAI tool schemas
- **Comprehensive Chaining**: Sequential, parallel, and context-preserving agent chains

### DDS Topic Structure
- `GenesisRegistration`: Agent registration and presence
- `FunctionCapability`: Function discovery and metadata
- `AgentCapability`: Agent discovery with specializations and capabilities  
- `FunctionExecutionRequest/Reply`: Function RPC calls
- `AgentAgentRequest/Reply`: Agent-to-agent communication
- `ChainEvent`: Chain execution tracking
- `ComponentLifecycleEvent`: Component state changes
- `MonitoringEvent`: General monitoring events

### Configuration
- **DDS Configuration**: `genesis_lib/config/datamodel.xml` defines all DDS types and QoS
- **Environment Variables**: 
  - `NDDSHOME`: RTI Connext DDS installation path
  - `OPENAI_API_KEY`: OpenAI API key for LLM integration
  - `ANTHROPIC_API_KEY`: Anthropic API key for Claude models
- **QoS Profiles**: Defined in USER_QOS_PROFILES.xml for reliability and performance tuning

### Development Patterns

#### Creating a Service
```python
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

class MyService(EnhancedServiceBase):
    def __init__(self):
        super().__init__("MyService", capabilities=["calculation"])
        self._advertise_functions()
    
    @genesis_function()
    async def calculate(self, x: float, y: float) -> dict:
        """Calculate something with x and y."""
        return {"result": x + y}
```

#### Creating an Agent with Tools
```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

class MyAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="MyAgent",
            enable_agent_communication=True
        )
    
    @genesis_tool(description="Process some data")
    async def process_data(self, data: str) -> dict:
        """Process the provided data."""
        return {"processed": data.upper()}
```

#### Creating an Interface
```python
from genesis_lib.monitored_interface import MonitoredInterface

interface = MonitoredInterface(
    interface_name="MyInterface",
    service_name="MyInterfaceService"
)
await interface.connect_to_agent(service_name="target_agent")
response = await interface.send_request({"message": "Hello"})
```

### Monitoring and Debugging
- Genesis publishes comprehensive monitoring events to DDS topics
- Use `genesis_monitor.py` for real-time network visualization
- RTI DDS Spy provides low-level DDS traffic inspection
- All function calls, agent communications, and chain executions are traced
- Check logs in the `logs/` directory for detailed execution traces

### Important Dependencies
- **RTI Connext DDS 7.3.0+**: Core communication middleware
- **Python 3.10**: Required Python version
- **OpenAI/Anthropic APIs**: For LLM integration
- **Pydantic**: For schema validation and type safety

### Key Breakthrough: Agent-as-Tool Pattern
GENESIS 2.0's revolutionary feature automatically discovers agents and makes them available as LLM tools:
1. Agents publish capabilities via `AgentCapability` topic
2. Primary agents auto-discover specialized agents  
3. Agent capabilities are converted to OpenAI tool schemas
4. LLM receives unified tools (functions + agents + internal tools)
5. Agent tool calls are routed via DDS agent-to-agent communication
6. Full context and monitoring are preserved across chains

This eliminates manual agent orchestration and enables natural language delegation between agents.