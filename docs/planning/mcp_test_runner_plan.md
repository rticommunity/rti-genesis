# MCP Test Runner Service (Draft)

Goal: Allow agents that cannot run DDS (e.g., sandboxed tools) to request
Genesis tests to run in a preconfigured environment and get structured results.

## Approach

- Provide a small MCP server that exposes tools to run tests from this repo:
  - `run_triage_suite`: Runs `run_scripts/run_triage_suite.sh` and returns pass/fail plus summaries.
  - `run_all_tests`: Runs `run_scripts/run_all_tests.sh` (long), returns aggregated result.
  - `run_named_test`: Runs a specific script (whitelisted) and returns output + exit code.
  - `list_logs` / `read_log`: Enumerate and tail logs under `logs/`.
  - `env_info`: Report DDS config (`NDDSHOME`, resolved `rtiddsspy` path), Python version, etc.

## Transport

- Primary: MCP (Model Context Protocol) over stdio using the Python SDK.
- Optional bridge: Systemd/PM2 keeps the server running; agent connects via `command` transport.
- Fallback: Simple HTTP wrapper that calls the same runner functions (for environments without MCP clients).

## Execution Environment

- Host/VM/container with:
  - DDS installed and `NDDSHOME` configured; `rtiddsspy` available.
  - Python 3.10 and this repo checked out.
  - Optional API keys set for LLM-related tests.
- Service user with least privileges; logs isolated to `logs/`.

## Outputs

- JSON-serializable result with fields:
  - `status`: `pass` | `fail` | `error`
  - `exit_code`: integer
  - `summary`: short string
  - `artifacts`: list of log filenames produced (relative to `logs/`)
  - `tails`: map of filename → last N lines (optional size-limited)

## Security

- Whitelist runnable scripts to avoid arbitrary command execution.
- Enforce per-call timeouts and max output sizes.
- Do not echo env secrets; redact known keys from output.

## Deployment

- Standalone process (systemd or tmux) in the repo root:
  - `python tools/mcp_test_runner/server.py`
- Optionally bake into a VM image with DDS preinstalled.

## Next Steps

- Implement `tools/mcp_test_runner/server.py` with MCP tools above.
- Add `tools/mcp_test_runner/README.md` with usage and test commands.
- (Optional) Add HTTP bridge if needed later.

