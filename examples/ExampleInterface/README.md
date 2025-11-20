# Example Interface: Complete AI Agent Pipeline

A simple example showing an AI agent, a backend service, and a CLI interface working together.

## Quick Start

### Prerequisites

- Python 3.10.x (Genesis LIB requires >=3.10,<3.11)
- Outbound access to the OpenAI API; requests will bill to your account
- An OpenAI API key exported in your shell

```bash
export OPENAI_API_KEY=your_key_here

# Install Genesis LIB (from Genesis_LIB root)
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

**Verbosity controls**
- Default run prints INFO-level logs.
- Set `QUIET_MODE=yes` to suppress most agent/interface chatter.
- Pass `-v` or `-q` to `example_agent.py` and/or `example_interface.py` if you launch them manually.

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

To [SimpleGenesisAgentForTheWin]: First multiply 37 by 12, then divide by 8.
Agent response: (from calculator) (37 * 12) / 8 = 55.5
```

Type `quit` or press `Ctrl+C` to stop everything.

If the interface exits after ~30 seconds with "No agents found," the agent or service probably failed to start (bad API key, blocked network, or Python version mismatch). Check `logs/agent.log` and `logs/service.log` for the error.

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
- **Tracing enabled** - The example agent sets `enable_tracing=True` so you can see detailed call flow in the logs
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
