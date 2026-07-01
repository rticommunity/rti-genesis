# Genesis Test Suite

The test suite validates Genesis end-to-end: DDS transport, function discovery, RPC calls, agent-to-agent communication, monitoring, and durability.

**Requirements before running tests:**

- RTI Connext DDS 7.7.0+ fully installed (`NDDSHOME` set, `rtiddsspy` in PATH)
- Python 3.10, venv activated (`source .venv/bin/activate && source .env`)
- `OPENAI_API_KEY` (required for LLM-dependent tests)

If you haven't set up the dev environment yet, start with [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Running the Tests

```bash
# Full suite (recommended before any PR)
./run_all_tests.sh

# Fail-fast triage suite (faster, good for debugging a specific failure)
./run_triage_suite.sh

# Parallel runner
./run_all_tests_parallel.sh
```

All tests write logs to `logs/`. On failure, the runner prints the tail of the relevant log.

---

## Test Coverage and Order

Tests run from most comprehensive to most targeted. The suite stops on first failure and prints the relevant log.

| # | Test | Script | Timeout | What it validates |
|---|------|---------|---------|------------------|
| 1 | Memory recall | `active/run_test_agent_memory.sh` | 60s | Multi-stage agent memory recall |
| 2 | Agent↔Agent | `active/test_agent_to_agent_communication.py` | 120s | PersonalAssistant ⇄ WeatherAgent via `@genesis_tool` |
| 3 | Interface→Agent→Service pipeline | `active/run_interface_agent_service_test.sh` | 75s | Full RPC pipeline: interface → agent → calculator |
| 4 | Math interface simple | `active/run_math_interface_agent_simple.sh` | 60s | Registration durability + request/reply |
| 5 | Basic calculator RPC | `active/run_math.sh` | 30s | `GenesisRPCClient` add/sub/mul/div + div-by-zero |
| 6 | Multi-instance calculator | `active/run_multi_math.sh` | 60s | 3 calculator services in parallel |
| 7 | Simple agent + services | `active/run_simple_agent.sh` | 60s | Calculator + TextProcessor + LetterCounter |
| 8 | Simple client | `active/run_simple_client.sh` | 60s | Client-driven RPC path |
| 9 | Calculator durability | `active/test_calculator_durability.sh` | 60s | Service registration survives restarts |
| 10 | Agent with functions | `active/run_test_agent_with_functions.sh` | 60s | Requires `OPENAI_API_KEY` |
| 11 | Services + CLI sanity | `active/start_services_and_cli.sh` | 90s | Lifecycle sanity check |
| 12 | Framework sanity | `active/test_genesis_framework.sh` | 120s | DDS/RPC basics, service registration poll |
| 13 | Monitoring | `active/test_monitoring.sh` | 60s | Graph events across multiple services |

### Monitoring Tests (Stage 4 in triage)

- `active/test_monitoring_graph_state.py` — validates `GraphMonitor`/`GraphState` invariants: unique nodes per endpoint, `SERVICE→FUNCTION` edges, `BUSY→READY` pairs per call. **No API key needed.**
- `active/test_monitoring_interface_agent_pipeline.py` — runs interface→agent→service pipeline and asserts monitoring edges and activity pairing.
- `active/test_monitoring.sh` — full monitoring path with LLM. Skipped automatically if `OPENAI_API_KEY` is not set.

### Viewer Contract

`active/test_viewer_contract.py` — validates that `genesis_lib.viewer_export` produces stable topology JSON (nodes, edges, timestamp, version fields). Runs without DDS or API keys.

---

## Triage Guide

If a test fails, the triage runner (`run_triage_suite.sh`) runs targeted subtests to isolate the cause:

| Failing stage | Check next |
|---------------|-----------|
| Memory (1) | DDS health: `rtiddsspy -v` |
| Agent↔Agent (2) | Run Pipeline (3) — if it passes, the issue is in multi-agent routing |
| Pipeline (3) | Run Math simple (4) and Math client (5) to confirm RPC path |
| Math simple (4) | Run Math client (5) as the leanest RPC smoke test |

Set `DEBUG=true` for verbose runner output:

```bash
DEBUG=true ./run_all_tests.sh
```

---

## Structure

```
tests/
├── run_all_tests.sh          full suite orchestrator
├── run_triage_suite.sh       fail-fast triage orchestrator
├── run_all_tests_parallel.sh parallel runner
├── active/                   scripts invoked by the suite runners
├── helpers/                  shared Python drivers used by tests
│   ├── math_test_agent.py
│   ├── math_test_interface.py
│   ├── simpleGenesisAgent.py
│   ├── test_agent.py
│   ├── test_agent_memory.py
│   └── ...
├── stress/                   stress and topology tools
└── logs/                     test output (git-ignored)
```

---

## MCP Test Runner (optional)

An MCP server lets you run tests from Cursor or other assistants:

```bash
source .venv/bin/activate && pip install mcp
# .cursor/mcp.json auto-starts the server via mcp/start_server.sh
```

Available tools: `preflight`, `run_triage`, `run_all_tests`, `run_active_test {name}`, `tail_log {filename}`, `sweep_dds`.

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
