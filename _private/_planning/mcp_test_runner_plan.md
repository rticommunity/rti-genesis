# MCP Test Runner Service (Draft Plan)

Goal: Allow agents that cannot run DDS (e.g., sandboxed tools) to request Genesis tests to run in a DDS‑ready environment and receive structured pass/fail results and logs.

## Scope

- In‑scope: Triggering existing repo tests remotely; structured results; basic log retrieval; minimal auth and safety.
- Out‑of‑scope (initially): Browser/UI testing; multi‑tenant auth; per‑run environment provisioning.

## Architecture Overview

- MCP Server: Long‑running Python process exposing tools over MCP stdio.
- Test Runners: Shell/Python scripts already in `run_scripts/` executed by the server.
- Artifacts: Logs under `logs/` collected and returned as names and optional tails.
- Clients: Codex CLI or other MCP‑capable agents invoke tools instead of running DDS locally.

## Tools (MVP)

- `env_info`: Report DDS config (`NDDSHOME`, rtiddsspy path), Python version, redacted env keys.
- `run_triage_suite`: Run `run_scripts/run_triage_suite.sh`; return status, exit code, log artifacts.
- `run_all_tests`: Run `run_scripts/run_all_tests.sh` (long); return aggregated result.
- `run_named_test(name)`: Whitelisted scripts only (e.g., `viewer_contract`, `monitoring_graph`, `monitoring_interface_pipeline`, `math`).
- `list_logs`, `read_log(name, max_lines)`: Enumerate and tail logs.

Response contract: See `docs/planning/schemas/mcp_test_result.schema.json`.

## Transport & Deployment Options

- Primary: MCP over stdio (process runs under systemd/tmux/screen on DDS host).
- CI Bridge: GitHub Actions job SSHs into DDS host and runs triage; uploads logs (template added).
- Alternative: Self‑hosted Actions runner on DDS host to avoid SSH.
- Optional (later): Lightweight HTTP wrapper forwarding to the same runner functions.

## Execution Environment

- Host/VM/container with:
  - DDS installed (`NDDSHOME`), `rtiddsspy` present.
  - Python 3.10; repo checked out; deps installed.
  - Optional API keys for LLM‑dependent tests.
- Service user with least privileges; `logs/` writable.

## Security & Safety

- Whitelist commands; no arbitrary shell.
- Per‑call timeouts; output size limits; redaction of secrets.
- Do not expose full environment; only redacted keys.

## Observability

- Always return `artifacts` list and allow `read_log` tails.
- Consider rotating logs (size/time‑based) to cap storage.
- Optional: emit a compact JSON summary file per run into `logs/`.

## Phased Implementation

Phase 0 — Prepare
- [ ] Choose DDS host (VM or self‑hosted runner) and access method (SSH vs self‑hosted).
- [ ] Create service user; install DDS; set `NDDSHOME`; verify `rtiddsspy`.

Phase 1 — MVP Server
- [ ] Implement MCP server with `env_info`, `run_triage_suite`, `run_named_test`, `list_logs`, `read_log`.
- [ ] Enforce whitelist + timeouts; redact env.
- [ ] Manual validation from Codex CLI or a simple MCP client.

Phase 2 — CI Integration
- [ ] Add GitHub Actions job that triggers triage remotely (SSH or self‑hosted).
- [ ] Upload logs as artifacts; comment on PRs on failure; optional email alert (templates included).

Phase 3 — Hardening
- [ ] Cap log sizes; rotate old logs; add per‑tool runtime limits.
- [ ] Add `run_all_tests` tool guarded behind a label or manual dispatch.
- [ ] Add metrics summary JSON per run (status, durations).

Phase 4 — Extensibility
- [ ] Parameterize `run_named_test` to pass flags (e.g., include/exclude monitoring stages).
- [ ] Add “test packs” (e.g., `core`, `monitoring`, `viewer_contracts`).
- [ ] Optional HTTP bridge or gRPC for non‑MCP clients.

## Success Criteria

- Agents in restricted environments can request triage and receive structured results within minutes.
- Failures produce actionable PR comments and downloadable logs.
- No arbitrary code execution; secrets remain redacted.

## Open Questions

- Preferred host approach: SSH into a general DDS box or use a self‑hosted runner?
- Notification channels: PR comments only, or also email/Slack?
- Retention policy for logs/artifacts?

## Rollback / Failure Modes

- If MCP server unavailable, CI still runs lightweight contract tests.
- SSH triage job failure falls back to artifact logs from last successful run.

