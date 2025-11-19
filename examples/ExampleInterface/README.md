# Example Interface: Complete AI Agent Pipeline

A simple example showing an AI agent, a backend service, and a CLI interface working together.

## Quick Start

### Prerequisites

```bash
# 1. Set your OpenAI API key
export OPENAI_API_KEY=your_key_here

# 2. Ensure Genesis LIB is installed (from Genesis_LIB root)
pip install .
```

### Run It

```bash
./run_example.sh
```

That's it! The script will:
1. Start a calculator service in the background
2. Start an AI agent in the background  
3. Launch an interactive CLI where you can select the agent and chat with it

**Quiet mode** (cleaner output):
```bash
QUIET_MODE=yes ./run_example.sh
```

## What You'll See

```
Starting Example Service...
Starting Example Agent...
Starting Example Interface...

Updated/Added discovered function: add
Updated/Added discovered function: divide
Updated/Added discovered function: multiply
Updated/Added discovered function: subtract

  1. Name: 'SimpleGenesisAgentForTheWin', ID: '...', Service: 'OpenAIChat'

Select agent by number: 1

Successfully connected to agent: 'SimpleGenesisAgentForTheWin'.
You can now send messages. Type 'quit' or 'exit' to stop.

To [SimpleGenesisAgentForTheWin]: Hello!
Agent response: Hi! How can I help you today?
```

Type `quit` or press `Ctrl+C` to stop everything.

## Components

- **`example_service.py`**: Calculator service with add/subtract/multiply/divide operations
- **`example_agent.py`**: OpenAI-powered agent that responds to messages
- **`example_interface.py`**: CLI for discovering and chatting with agents
- **`run_example.sh`**: Orchestration script that manages all components

## Logs

- `logs/service.log` - Service output
- `logs/agent.log` - Agent output
- Console - Your interaction with the agent

## Troubleshooting

**Shared memory warnings on macOS?**
```
ERROR RTIOsapiSharedMemorySegment_createOrAttach:ENOSPC
```
Safe to ignore. DDS automatically falls back to UDP transport.

**Need more details?**
Run without quiet mode or check the log files.

## What This Demonstrates

- **MonitoredService** - Service with automatic function registration via `@genesis_function`
- **OpenAIGenesisAgent** - AI agent with built-in OpenAI integration
- **MonitoredInterface** - Automatic agent discovery and RPC communication
- **Process orchestration** - Multi-component startup/shutdown management

## Advanced Usage

Run components individually (useful for debugging):

```bash
# Terminal 1
python3 example_service.py

# Terminal 2  
python3 example_agent.py -q    # -q for quiet, -v for verbose

# Terminal 3
python3 example_interface.py
```
