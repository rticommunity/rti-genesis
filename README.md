# GENESIS — Distributed AI Agent Framework

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![RTI Connext DDS](https://img.shields.io/badge/RTI%20Connext%20DDS-7.7.0+-green.svg)](https://www.rti.com/)
[![License](https://img.shields.io/badge/license-RTI-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-RC1-orange.svg)]()

**GENESIS** (Generative Networked System for Intelligent Services) is a Python framework for building distributed AI agent networks. Agents and services discover each other automatically — no IP addresses, no ports, no configuration files — using RTI Connext DDS as the communication backbone.

---

## Install

```bash
pip install genesis-lib
```

This pulls the full RTI Connext DDS runtime automatically (bundled in the package). The only RTI-specific step is a free license file.

### Get an RTI License

Genesis requires a license to activate the DDS runtime:

1. Fill out the form at [rti.com/get-connext](https://www.rti.com/get-connext) — select **Free 60-day evaluation**
2. A file named `rti_license.dat` will arrive by email within a few minutes
3. Point Genesis to it:

```bash
export RTI_LICENSE_FILE="/path/to/rti_license.dat"
```

Add this to your `~/.zshrc` or `~/.bashrc` to make it permanent.

### Set an API Key

```bash
export OPENAI_API_KEY="your_openai_key"
# or
export ANTHROPIC_API_KEY="your_anthropic_key"
# or use local inference with Ollama (no API key needed — see docs/guides/local-inference.md)
```

---

## Your First Service (30 seconds)

Create `calc_service.py`:

```python
import asyncio
from genesis_lib.monitored_service import MonitoredService
from genesis_lib.decorators import genesis_function

class CalculatorService(MonitoredService):
    def __init__(self):
        super().__init__("Calculator", capabilities=["math"])
        self._advertise_functions()

    @genesis_function()
    async def add(self, x: float, y: float) -> dict:
        """Add two numbers."""
        return {"result": x + y}

    @genesis_function()
    async def multiply(self, x: float, y: float) -> dict:
        """Multiply two numbers."""
        return {"result": x * y}

asyncio.run(CalculatorService().run())
```

Run it:

```bash
python calc_service.py
```

---

## Your First Agent (30 seconds)

In a second terminal, create `agent.py`:

```python
import asyncio
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

class MathAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="MathAssistant"
        )

async def main():
    agent = MathAgent()
    await asyncio.sleep(2)  # let DDS discovery settle

    response = await agent.process_message("What is 127 + 384?")
    print(response)

asyncio.run(main())
```

**Option: local inference with Ollama (no API costs)**

```python
from genesis_lib.local_genesis_agent import LocalGenesisAgent

class MathAgent(LocalGenesisAgent):
    def __init__(self):
        super().__init__(model_name="nemotron-mini:latest", agent_name="MathAssistant")
```

Run it (keep the service running in the other terminal):

```bash
python agent.py
```

Within 2–3 seconds the agent discovers the calculator service via DDS and routes your question to it automatically.

---

## What's Happening

```
agent.py                           calc_service.py
    │                                    │
    │── DDS discovery ──────────────────>│ (finds Calculator on the network)
    │                                    │
    │── "What is 127 + 384?" ──> LLM    │
    │                              │     │
    │               classifies as math   │
    │                              │     │
    │── RPC call: add(127, 384) ────────>│
    │<─ {"result": 511} ─────────────────│
    │                                    │
    "127 + 384 = 511"
```

No broker. No configuration. Components on different machines work the same way.

---

## Key Features

| Feature | Description |
|---------|-------------|
| Zero-config discovery | Agents and services find each other via DDS — no IP addresses or ports |
| Intelligent windowing | Classifiers select 5–10 relevant functions from 200+, reducing LLM tokens by 90%+ |
| Agent-as-Tool pattern | Agents automatically become callable tools for other agents |
| Multi-LLM support | OpenAI, Anthropic, Ollama — swap with one line |
| Real-time performance | Sub-millisecond DDS communication, peer-to-peer (no broker) |
| Production-grade transport | Same middleware used in surgical robots and flight control systems |
| Monitoring built-in | Real-time network graph, chain tracing, lifecycle events |

---

## Architecture

```
┌────────────────────────────────────────┐
│ ProviderAgent (OpenAI / Anthropic / …) │  provider-specific API calls
└────────────────────┬───────────────────┘
                     │ inherits
┌────────────────────▼───────────────────┐
│ MonitoredAgent                          │  state, graph topology, event tracking
└────────────────────┬───────────────────┘
                     │ inherits
┌────────────────────▼───────────────────┐
│ GenesisAgent                            │  discovery, tool routing, orchestration
└────────────────────────────────────────┘
          │ communicates via DDS
┌─────────▼──────────────────────────────┐
│ Services / Other Agents                 │  @genesis_function, @genesis_tool
└────────────────────────────────────────┘
```

---

## Examples

| Example | What it shows | Location |
|---------|--------------|----------|
| **Hello World** | Minimal agent + service + interface | `examples/HelloWorld/` |
| **MultiAgent** | Agent-as-tool with real APIs | `examples/MultiAgent/` |
| **Graph Interface** | Chat + live network visualization | `examples/GraphInterface/` |
| **Standalone Graph Viewer** | Network topology server | `examples/StandaloneGraphViewer/` |
| **Persistent Memory** | Agent with cross-session memory | `examples/PersistentMemory/` |

Run the MultiAgent demo:

```bash
cd examples/MultiAgent && ./run_interactive_demo.sh
```

---

## Documentation

| Doc | What's in it |
|-----|-------------|
| [Guides](docs/guides/) | How to build services, agents, interfaces, monitoring |
| [Reference](docs/reference/) | DDS topics, function RPC, configuration |
| [Architecture](docs/architecture/) | Internals for contributors |

---

## Use Cases

- **Critical infrastructure AI** — leverage DDS reliability for high-availability AI pipelines
- **Distributed AI pipelines** — chain agents and services across machines
- **Real-time AI** — sub-millisecond latency for robotics, IoT, edge AI
- **Large-scale agent networks** — DDS tested to thousands of nodes

---

## Support

Email: [genesis@rti.com](mailto:genesis@rti.com?subject=Genesis%20Support%20Request)

Include your OS, Python version, RTI Connext version, and any error output.

For bugs: [open a GitHub issue](../../issues).

For contributors and developers: see [CONTRIBUTING.md](CONTRIBUTING.md).

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
