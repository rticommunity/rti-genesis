# Genesis Test Suite Runner (`run_all_tests.sh`)

This README documents what the top-level test runner executes today, the order and purpose of each subtest, required environment, logs, and a proposal to make the suite fail fast with targeted triage.

## Overview

- Entry point: `run_scripts/run_all_tests.sh`
- Optional fail-fast runner: `run_scripts/run_triage_suite.sh`
- Helpers moved to `run_scripts/helpers/`
- Active test entrypoints moved to `run_scripts/active/`
- Goal: Validate Genesis end-to-end on DDS, covering memory, agent-to-agent, interface→agent→service pipelines, RPC math services, durability, framework sanity, and monitoring.
- Philosophy: Run hardest/most comprehensive checks early to fail fast.

## Prerequisites

- Python: 3.10.x
- DDS: RTI Connext DDS 7.3.0+ installed and configured
  - `NDDSHOME` set, `rtiddsspy` available
  - Optionally: `RTIDDSSPY_BIN` or `RTI_BIN_DIR` overrides
- API keys (where used): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Virtualenv activated or available at `venv/`

## Preflight and Common Behavior

- Activates `venv/` if present; sources `.env` if present.
- Verifies Python 3.10.
- Locates `rtiddsspy` using `RTIDDSSPY_BIN` → `RTI_BIN_DIR` → `$NDDSHOME/bin/rtiddsspy`.
- Creates `logs/` folder.
- Performs DDS cleanup check using `rtiddsspy` and kills lingering test processes if needed.
- Runs each test with a per-test timeout; writes per-test logs under `logs/`.
- On failure, prints the last 20 lines of relevant logs using heuristics to include related files.

## Execution Order and Coverage

1) Memory recall core test: `run_test_agent_memory.sh` (timeout 60s)
   - Validates multi-stage agent memory recall behavior.
   - Pass token in log: "✅ Multi-stage memory recall test PASSED".

2) Agent↔Agent comprehensive: `test_agent_to_agent_communication.py` (120s)
   - PersonalAssistant ⇄ WeatherAgent using `@genesis_tool` auto-discovery.
   - Verifies DDS messages, monitoring events, and successful cross-agent tool execution.

3) Interface→Agent→Service pipeline: `run_interface_agent_service_test.sh` (75s)
   - `SimpleGenesisAgent` + `CalculatorService` + `SimpleGenesisInterfaceStatic` question flow.
   - Checks DDS quiet preflight, connection, RPC client logs, and expected sum in response.

4) Math interface/agent simple: `run_math_interface_agent_simple.sh` (60s)
   - Two-phase test: registration durability then interface request/response.
   - Verifies durable GenesisRegistration, request/reply topics, and pass tokens.

5) Basic calculator client: `run_math.sh` (30s)
   - Spawns `CalculatorService` and uses `GenesisRPCClient` to verify add/sub/mul/div and div-by-zero handling.

6) Multi-instance calculator: `run_multi_math.sh` (60s)
   - Launches 3 calculator services; runs client checks across them.

7) Simple agent with services: `run_simple_agent.sh` (60s)
   - Starts Calculator/TextProcessor/LetterCounter services + `simple_agent`; verifies RPC calls to each.

8) Simple client path: `run_simple_client.sh` (60s)
   - Similar to (7) but drives via a simple client program.

9) Calculator durability: `test_calculator_durability.sh` (60s)
   - Service registration durability and function capability announcements via `rtiddsspy`.

10) Example agent with functions: `run_test_agent_with_functions.sh` (60s)
    - Requires `OPENAI_API_KEY`. Runs function and letter counter tests, checks RPC traces.

11) Services + CLI sanity: `start_services_and_cli.sh` (90s)
    - Spins up services and does a short lifecycle sanity; CLI is presently commented.

12) Framework sanity: `test_genesis_framework.sh` (120s)
    - DDS/RPC basic checks; services registration poll via `GenericFunctionClient`.

13) Monitoring test: `test_monitoring.sh` (60s)
    - Starts multiple calculator services, a monitoring script, and runs a test agent to generate events.

## Logs

- All logs under `logs/`. Common files include:
  - `test_agent_memory.log`, `test_sga_pipeline.log`, `test_calc_pipeline.log`, `test_static_interface_pipeline.log`, `rtiddsspy_*.log`, `math_test_agent.log`, `math_test_interface.log`, `serviceside_*.log`, etc.
- On failure, the runner prints the tail of the primary log and related logs (heuristics per test).

## Timeouts

- Global default: 120s; specific tests override (see list above).
- Exit code 124 is treated as timeout.

## Failure Handling Today

- Runner stops on first failure, prints relevant logs, cleans up processes, and exits non-zero.

## Proposed Improvements: Fail-Fast with Targeted Triage

- Stage ordering (already close): put comprehensive tests first, then branch to targeted subtests if they fail.
- For each comprehensive stage, define 1–3 fast subtests to isolate root cause before exiting.

Suggested triage map:
- If Memory (1) fails:
  - Run a quick DDS health check (spy only) and a minimal memory unit subset with verbose logs.
- If Agent↔Agent (2) fails:
  - Run (3) Interface→Agent→Service pipeline to see if service/RPC path is healthy.
  - If still failing, run (4) Math simple to isolate RPC + discovery without multi-agent complexity.
- If Pipeline (3) fails:
  - Run (4) Math simple and (5) run_math.sh to confirm RPC service path.
- If Math simple (4) fails:
  - Run (5) run_math.sh as the leanest RPC smoke.

Implementation notes:
- Add a `--triage` flag or `TRIAGE=true` env to enable subtest fallback.
- Encode subtests as small shell functions in `run_all_tests.sh` with shared log parsing.
- Print a short “triage summary” explaining which subtest failed and likely area (DDS env, discovery, RPC, monitoring).

## Migration Guidance (Repo Split)

- Keep `run_scripts/` as the authoritative orchestrator. When repos split:
  - Place the runner and example-heavy scripts in `genesis-examples`.
  - Add a CI shim in `genesis-lib` to invoke the examples runner when available; otherwise run a minimal library `pytest` suite.
- Inventory sub-scripts to categorize as “library unit” vs “example/integration”. Keep example/integration here; mirror pure unit tests into `genesis-lib` gradually.

## Tips

- Set `DEBUG=true` for extra debug output from the runner.
- Verify DDS quickly: `rtiddsspy -v` and ensure `NDDSHOME` and library paths are correct.
- Clean lingering DDS processes if a prior run crashed.

## Not in `run_all_tests.sh` (But Potentially Useful)

Some scripts look like tests or utilities but are not invoked by the runner today. See the full inventory and suggested actions in `docs/planning/run_scripts_inventory.md`.

- Baselines and variants: `baseline_test_agent.py`, `baseline_test_interface.py`, `run_baseline_*`, `run_math_interface_agent_test.sh`
- Durability variants: `dev/test_interface_durability.sh`, `dev/test_personal_agent_durability.sh`
- Example/demo: `helpers/interactive_memory_test.py`, `dev/run_interactive_memory_test.sh`, `dev/run_example_agent1*.sh`
- Utilities: `helpers/interface_keepalive.py`, `dev/run_math_service.sh`, `helpers/simpleGenesisInterfaceCLI.py`
- Older orchestrators: `run_tests.sh`, `test_genesis_complete.sh`

These are candidates to either (a) fold into the fail-fast triage path, (b) remain as documented dev utilities, or (c) move to the examples repo during the split.

## Structure

- `run_scripts/`: top-level orchestrators only (and docs).
- `run_scripts/active/`: scripts invoked by `run_all_tests.sh` and/or `run_triage_suite.sh`.
- `run_scripts/helpers/`: Python helpers and drivers used by the runners. Includes:
  - `baseline_test_agent.py`
  - `baseline_test_interface.py`
  - `interactive_memory_test.py`
  - `interface_keepalive.py`
  - `math_test_agent.py`
  - `math_test_interface.py`
  - `simpleGenesisAgent.py`
  - `simpleGenesisInterfaceCLI.py`
  - `simpleGenesisInterfaceStatic.py`
  - `test_agent.py`
  - `test_agent_memory.py`
  - `comprehensive_multi_agent_test_interface.py`

All referencing scripts have been updated to use `run_scripts/helpers/...` paths.

## Critical Entry Points (Do Not Remove)

- `run_all_tests.sh`: Full suite orchestrator invoked before merges.
- `run_triage_suite.sh`: Fail-fast orchestrator used in debugging.
- Core tests used by both suites (now under `active/`):
  - `active/run_test_agent_memory.sh`
  - `active/test_agent_to_agent_communication.py`
  - `active/run_interface_agent_service_test.sh`
  - `active/run_math_interface_agent_simple.sh`
  - `active/run_math.sh`
  - `active/run_multi_math.sh`
  - `active/run_simple_agent.sh`
  - `active/run_simple_client.sh`
  - `active/test_calculator_durability.sh`
  - `active/test_monitoring_graph_state.py`
  - `active/test_monitoring_interface_agent_pipeline.py`
  - `active/test_monitoring.sh` (optional when no `OPENAI_API_KEY`)
  - `active/test_viewer_contract.py`

Other groupings:
- `run_scripts/dev/`: development or ad-hoc tests (e.g., `run_math_interface_agent_test.sh`, `run_example_agent1*.sh`, `run_baseline_*`, `limited_mesh_test.sh`, `test_interface_durability.sh`).
- `run_scripts/legacy/`: older orchestrators retained for reference (`run_tests.sh`, `test_genesis_complete.sh`).

If relocating any of these, update both orchestrators accordingly.

## Monitoring Consistency Test (New)

- `test_monitoring_graph_state.py`: Validates GraphMonitor/GraphState invariants using `CalculatorService`:
  - One unique node per endpoint (service and each function)
  - `SERVICE→FUNCTION` edges exist for advertised functions
  - For each function call, a `BUSY→READY` pair is observed on the service node (closed reply)

Run:
```bash
python run_scripts/test_monitoring_graph_state.py
```
Requirements: DDS installed (`NDDSHOME`), Python 3.10.
### New Triage Runner

- Use `run_triage_suite.sh` to run: Memory → Agent↔Agent → Pipeline → Monitoring.
- On failure, it runs targeted subtests in-order to isolate likely causes:
  - For Agent↔Agent: Pipeline → Math Simple → Math Client
  - For Pipeline: Math Simple → Math Client
- Includes an advisory DDS writer sweep filtered to Genesis topics, logging warnings instead of aborting.
- Keeps `run_all_tests.sh` unchanged.

Monitoring
- Included by default as Stage 4.
- 4a: `test_monitoring_graph_state.py` (no API keys) validates GraphMonitor/GraphState invariants (unique nodes, service→function edges, BUSY→READY pairing for a call).
- 4a.2: `test_monitoring_interface_agent_pipeline.py` runs the interface→agent→service pipeline and asserts INTERFACE→AGENT edge plus INTERFACE_REQUEST_START→COMPLETE activity pairing.
- 4b: `test_monitoring.sh` (requires `OPENAI_API_KEY`) exercises the heavier monitoring path; skipped with a warning if key is missing.

Viewer Contract
- `test_viewer_contract.py` validates that the library exports a stable viewer topology JSON:
  - Converts an in-memory graph (GenesisNetworkGraph) to viewer JSON via `genesis_lib.viewer_export`.
  - Validates against `docs/planning/schemas/viewer_topology.schema.json`.
  - Enforces a small back-compat gate on counts and required fields.
- `mcp/`: Optional MCP server to run tests from Cursor/assistants.
  - `mcp/test_runner_server.py` provides tools: `preflight`, `run_triage`, `run_all_tests`, `run_active_test`, `tail_log`, `sweep_dds`.
  - `.cursor/mcp.json` registers the server to run via your project `venv`.

### MCP Usage (optional)

1) Ensure venv exists and install the `mcp` package if missing:
   - `source venv/bin/activate && pip install mcp`
2) Start automatically in Cursor: `.cursor/mcp.json` runs `mcp/start_server.sh` which:
   - sources `.env` (NDDSHOME, API keys), runs `mcp/preflight.sh`, then starts the server if OK.
   - If preflight fails, fix issues and retry.
3) Tools available:
   - `preflight` → prints Python, NDDSHOME, `rtiddsspy` path, API keys presence.
   - `run_triage` / `run_all_tests` → runs the suites, returns exit code and stdout/stderr.
   - `run_active_test {name}` → runs a single script from `run_scripts/active/`.
   - `tail_log {filename}` → returns the tail of a file under `logs/`.
   - `sweep_dds` → runs an advisory `rtiddsspy -printSample` sweep.
