# HelloWorld Genesis_LIB Example

This example demonstrates how to use the Genesis_LIB framework to connect an agent with a weather service using natural language queries.

## Prerequisites

- Python 3.8+
- [OpenAI API Key](https://platform.openai.com/account/api-keys)

## Setup Instructions

### 1. Start the Weather MCP Server

Open a terminal and run:

```bash
cd <INST_DIR>/Genesis_LIB/examples/HelloWorld/mcp_simple_server
python -m venv venv
source venv/bin/activate
pip install -r [requirements.txt](http://_vscodecontentref_/0)
python weather.py
```

This will start the weather service server.

### 2. Start the Genesis Service Example

Open a second terminal and run:

```bash
cd <INST_DIR>/Genesis_LIB/
[setup.sh](http://_vscodecontentref_/1)
# Follow the on-screen instructions
cd examples/HelloWorld
python mcp_hello_world_service.py
```

### 3. Start the Agent

Open a second terminal and run:

```bash
source venv/bin/activate
source .env
export OPENAI_API_KEY=<YOUR_KEY>
python hello_world_agent_interactive.py
```

#### Usage 

Once the agent is running, you'll see a prompt where you can ask questions in natural language. For example:

What is the weather in San Francisco?

The agent will discover the get_forecast function provided by the Genesis service, call the MCP server, and return the weather information.

Is there any alert for California?

The agent will discover the get_alert function, call the MCP server, and return any relevant alerts.