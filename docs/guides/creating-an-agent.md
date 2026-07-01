# Creating an Agent

An agent is the central component in Genesis — it receives requests, calls tools (functions, other agents, or its own methods), and returns responses. This guide covers the three main patterns.

---

## 1. Basic Agent (cloud LLM)

Subclass `OpenAIGenesisAgent` or `AnthropicGenesisAgent`:

```python
import asyncio
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

class MyAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="MyAgent",
            description="An agent that does useful things"
        )

async def main():
    agent = MyAgent()
    await asyncio.sleep(2)  # let DDS discovery settle
    response = await agent.process_message("Hello, what can you do?")
    print(response)
    await agent.close()

asyncio.run(main())
```

**For Anthropic:**
```python
from genesis_lib.anthropic_genesis_agent import AnthropicGenesisAgent

class MyAgent(AnthropicGenesisAgent):
    def __init__(self):
        super().__init__(model_name="claude-opus-4-5", agent_name="MyAgent")
```

---

## 2. Local Agent (Ollama, no API costs)

```python
from genesis_lib.local_genesis_agent import LocalGenesisAgent

class MyLocalAgent(LocalGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="nemotron-mini:latest",  # or any Ollama model
            agent_name="MyLocalAgent"
        )
```

Before running, ensure Ollama is running and the model is pulled:
```bash
ollama serve
ollama pull nemotron-mini:latest
```

See [local-inference.md](local-inference.md) for more detail.

---

## 3. Agent with Internal Tools

Use `@genesis_tool` to expose agent methods as tools the LLM can call directly:

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

class CalculatorAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(model_name="gpt-4o", agent_name="CalculatorAgent")

    @genesis_tool(description="Add two numbers and return the result")
    async def add(self, a: float, b: float) -> dict:
        return {"result": a + b}

    @genesis_tool(description="Convert Celsius to Fahrenheit")
    async def celsius_to_fahrenheit(self, celsius: float) -> dict:
        return {"fahrenheit": celsius * 9 / 5 + 32}
```

The LLM sees `add` and `celsius_to_fahrenheit` as callable tools alongside any external services it has discovered.

---

## 4. Agent that Calls Other Agents (agent-as-tool)

Enable `agent_communication` to let the agent discover and call other agents on the network:

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

class PersonalAssistant(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant",
            enable_agent_communication=True  # enables agent-as-tool
        )
```

With this flag set, any other agents running on the network are automatically discovered and presented to the LLM as callable tools. No extra configuration needed. See [agent-as-tool.md](../architecture/agent-as-tool.md) for how this works internally.

---

## 5. Agent with Advertised Capabilities

Publish what your agent specialises in so other agents and interfaces can discover it:

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

class WeatherAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="WeatherExpert",
            description="Specialised in weather, meteorology, and climate queries",
            capabilities=["weather", "meteorology", "climate"],
            specializations=["current_weather", "weather_forecast"]
        )
```

See [capabilities.md](capabilities.md) for the full capabilities reference.

---

## 6. Creating an Interface

An interface is how users or applications talk to an agent. It discovers agents on the network and sends them requests:

```python
import asyncio
from genesis_lib.monitored_interface import MonitoredInterface

async def main():
    interface = MonitoredInterface(
        interface_name="MyCLI",
        service_name="MyCLIService"
    )

    # Wait for and connect to an agent
    await interface.connect_to_agent(service_name="MyAgent")

    # Send a request
    response = await interface.send_request({"message": "What is 2 + 2?"})
    print(response)

asyncio.run(main())
```

---

## Runtime Behaviour

When an agent starts it:

1. Connects to DDS on domain 0 (or `GENESIS_DOMAIN_ID`)
2. Publishes its identity so interfaces and other agents can find it
3. Starts discovering function services and other agents on the network
4. Processes incoming requests, calls tools via DDS RPC, and returns responses

### Domain Isolation

Run components on a different DDS domain for network isolation:

```bash
export GENESIS_DOMAIN_ID=5
python my_agent.py
```

All components (agent, service, interface) must use the same domain to communicate.

### Enable Tracing

```python
agent = MyAgent()
agent.enable_tracing = True  # verbose tool call logging
```

---

## Next Steps

- **Add services**: See [creating-a-service.md](creating-a-service.md) to give your agent external functions to call
- **Monitor the network**: See [monitoring.md](monitoring.md) for real-time graph visualization
- **Understand agent-as-tool internals**: See [architecture/agent-as-tool.md](../architecture/agent-as-tool.md)
- **Add a new LLM provider**: See [architecture/add-provider.md](../architecture/add-provider.md)

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
