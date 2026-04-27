# CodingGenesisAgent

A Genesis agent that delegates coding tasks to **Claude Code** or **OpenAI Codex** via subprocess, using **subscription pricing** instead of API billing.

See [VISION.md](VISION.md) for the full technical design.

## Prerequisites

- Python 3.10+
- RTI Connext DDS 7.3.0+ (for DDS-based tests)
- `claude` CLI installed and logged in (`claude login`)
- OR `codex` CLI installed and logged in (`codex login`)

## Quick Start

```bash
# From repo root
source venv/bin/activate && source .env
cd examples/CodingAgent

# Run end-to-end (agent + interactive interface)
bash run_example.sh

# With Codex backend
bash run_example.sh --backend codex

# With custom options
bash run_example.sh --backend claude --working-dir /path/to/project --timeout 600

# Or run agent only (no interface)
bash run_claude_agent.sh
bash run_codex_agent.sh
```

## Architecture

```
CodingGenesisInterface (MonitoredInterface)
      |
  DDS RPC (discover + connect)
      |
      v
CodingGenesisAgent (MonitoredAgent)
      |
  asyncio.subprocess
      |
  +---v---+    +---v---+
  | claude |   | codex  |
  |   -p   |   |  exec  |
  +---------+  +---------+
  Subscription  Subscription
```

Both the agent and interface extend Genesis base classes — zero genesis_lib modifications needed.

## Tests

```bash
cd examples/CodingAgent

# Unit tests (no DDS required)
python test_coding_agent.py

# Including live CLI tests
python test_coding_agent.py --include-live

# Individual test suites
python tests/test_backends.py      # Parser, command builder, env sanitization
python tests/test_auth.py          # Auth probing logic
python tests/test_agent_mock.py    # Mock subprocess event processing

# DDS integration tests (requires DDS environment)
bash tests/test_agent_lifecycle.sh # Agent start/stop lifecycle
bash tests/test_e2e_request.sh     # Full RPC request round-trip
```

## File Layout

```
examples/CodingAgent/
    VISION.md                    # Technical design document
    README.md                    # This file
    coding_genesis_agent.py      # CodingGenesisAgent class
    coding_interface.py          # Interactive CLI interface
    run_example.sh               # End-to-end launch (agent + interface)
    run_claude_agent.sh          # Launch agent only (Claude)
    run_codex_agent.sh           # Launch agent only (Codex)
    test_coding_agent.py         # Master test runner
    specs/                       # GWT specification files (14)
    backends/
        __init__.py              # Package re-exports
        events.py                # CodingEvent dataclass
        base.py                  # CodingBackend ABC
        claude_backend.py        # Claude Code parser
        codex_backend.py         # Codex parser
        auth.py                  # Auth probing
        stream_reader.py         # Async event stream reader
    tests/
        test_backends.py         # Backend unit tests
        test_auth.py             # Auth unit tests
        test_agent_mock.py       # Mock subprocess tests
        test_live_backend.py     # Live CLI tests
        test_agent_lifecycle.sh  # DDS lifecycle test
        test_e2e_request.sh      # E2E request test
        e2e_client.py            # E2E DDS client
        run_backend_tests.sh     # Backend test runner
        run_live_tests.sh        # Live test runner
```
