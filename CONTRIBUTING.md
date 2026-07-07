# Contributing to GENESIS

This guide is for developers who want to contribute to Genesis, run the test suite, or extend the framework. If you just want to build with Genesis, see [README.md](README.md).

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | 3.10.x (required) |
| **RTI Connext DDS** | 7.7.0+ — full installation (not just the pip package) |
| **API Keys** | OpenAI and/or Anthropic (for LLM-dependent tests) |

### Why a full RTI Connext DDS installation?

The `rti-connext` pip package bundles the DDS runtime for users, but contributors need the full installation for:
- `rtiddsspy` — DDS traffic inspector used by the test suite
- Build tools and headers
- `NDDSHOME`-dependent test scripts

### Install RTI Connext DDS

Run the setup wizard:

```bash
./rti_setup.sh
```

Or follow the manual steps in [RTI_SETUP.md](RTI_SETUP.md).

---

## Setup

```bash
# Clone the repo
git clone https://github.com/rticommunity/rti-genesis.git
cd rti-genesis

# Run the setup script (creates venv, installs in editable mode)
./setup.sh

# Activate the environment
source .venv/bin/activate
source .env
```

Verify:

```bash
python -c "import genesis_lib; print('OK')"
rtiddsspy --help
```

---

## Running Tests

See [tests/README.md](tests/README.md) for the full test documentation.

Quick start:

```bash
cd tests && ./run_all_tests.sh
```

---

## Project Structure

```
genesis_lib/       core library
examples/          example agents, services, interfaces
tests/             test suite
docs/
  guides/          user how-to guides
  reference/       stable reference material
  architecture/    contributor internals
```

---

## Contribution Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run the test suite: `cd tests && ./run_all_tests.sh`
5. Submit a pull request

### Code Patterns

See [docs/architecture/](docs/architecture/) for internals documentation:

- [Architecture Overview](docs/architecture/overview.md) — component model and communication patterns
- [Agent Hierarchy](docs/architecture/agent-hierarchy.md) — class hierarchy and abstract methods
- [Add a Provider](docs/architecture/add-provider.md) — add a new LLM provider in ~150 lines
- [Function Discovery](docs/architecture/function-discovery.md) — how `@genesis_function` and discovery work
- [Monitoring System](docs/architecture/monitoring-system.md) — graph monitoring and event types

---

## Architecture Quick Reference

```
genesis_lib/
├── agent.py                  GenesisAgent — base, discovery, tool routing
├── monitored_agent.py        MonitoredAgent — state machine, graph publishing
├── openai_genesis_agent.py   OpenAIGenesisAgent — OpenAI provider
├── anthropic_genesis_agent.py AnthropicGenesisAgent — Anthropic provider
├── local_genesis_agent.py    LocalGenesisAgent — Ollama / local inference
├── monitored_service.py      MonitoredService — service base class
├── monitored_interface.py    MonitoredInterface — interface base class
├── decorators.py             @genesis_function, @genesis_tool
├── function_discovery.py     FunctionRegistry — DDS-based discovery
├── graph_monitoring.py       GraphMonitor — topology events
└── config/datamodel.xml      DDS type definitions and QoS profiles
```

---

## Support

For Genesis issues: [genesis@rti.com](mailto:genesis@rti.com)
For RTI Connext issues: [RTI Support](https://www.rti.com/support)

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
