# MCP Test Runner (Prototype)

Run Genesis tests from an MCP-enabled agent without running DDS locally.

## Prereqs

- Host has DDS installed (`NDDSHOME` set) and can run repo tests normally.
- Python 3.10, and packages: `pip install mcp jsonschema`.

## Start the server

```bash
cd /path/to/Genesis_LIB
python tools/mcp_test_runner/server.py
```

This starts an MCP server named `genesis-test-runner` over stdio.

## Tools

- `env_info()`: Returns Python/DDS info and redacted env keys.
- `run_triage_suite()`: Runs `run_scripts/run_triage_suite.sh`.
- `run_all_tests()`: Runs `run_scripts/run_all_tests.sh` (long).
- `run_named_test(name)`: One of `viewer_contract`, `monitoring_graph`, `monitoring_interface_pipeline`, `math`.
- `list_logs()`: Lists recent `logs/*.log` files.
- `read_log(name, max_lines=200)`: Tails a specific log.

Each run returns JSON with `status`, `exit_code`, `summary`, `artifacts`, and `output` (stdout/stderr).

## Using from an Agent

- Connect via MCP command transport to the server process.
- Call `env_info` to verify DDS.
- Call `run_triage_suite` or a specific `run_named_test`.
- Retrieve logs with `list_logs` / `read_log`.

## Notes

- This is a prototype and not bound into CI. Keep it on a secure host.
- Extend `SAFE_TESTS` in `server.py` for more whitelisted tests.

