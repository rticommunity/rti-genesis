# `run_all_tests.sh` Refactor Plan (Draft)

Goal: Preserve current coverage while making the suite faster to iterate with fail-fast triage and clearer stage boundaries. No code moves yet.

## Pain Points Observed

- Comprehensive tests are early, but failure triage is manual and slow.
- Mixed unit/integration coverage is orchestrated via shell scripts only.
- DDS preflight exists but could surface more actionable details.

## Objectives

- Add an optional triage mode that, on failure of a comprehensive stage, runs 1–3 targeted subtests to pinpoint the failure class (DDS env, discovery, RPC service path, multi-agent plumbing, monitoring).
- Standardize per-test metadata (name, timeout, log file) to simplify orchestration and reporting.
- Keep `run_all_tests.sh` authoritative; do not break existing usage.

## Proposed Structure

- Introduce a small registry at top of the script:
  - Stages: memory, agent_to_agent, pipeline, math_simple, calculator_client, multi_math, simple_agent, simple_client, durability, agent_functions, services_cli, framework, monitoring.
  - Each stage has: runner (script), timeout, primary log, and triage mapping.
- Add `--triage` (or `TRIAGE=true`) to enable fast subtest fallback on failure.
- Add `--continue-on-failure` for full-run diagnostics without stopping.

## Triage Map (Initial)

- memory → subtests: memory_verbose, dds_health
- agent_to_agent → subtests: pipeline, math_simple
- pipeline → subtests: math_simple, calculator_client
- math_simple → subtests: calculator_client

Subtests are thin wrappers around existing scripts with shorter timeouts and narrow assertions.

## DDS Preflight Enhancements

- Pre-run: emit explicit NDDSHOME, resolved `rtiddsspy` path, and `uname -a`.
- Optional quick `rtiddsspy -v` and a 2s topic-listen sanity.
- Provide clear remediation tips if spy not found or topics are busy.

## Logging & Reporting

- Normalize log naming and include stage prefixes.
- On failure, append a short triage summary to `logs/triage_summary.txt`.
- Summarize pass/fail and durations at the end.

## Backwards Compatibility

- Default behavior remains: stop at first failure, no triage.
- Flags opt-in to new behavior.

## Migration Alignment

- Long-term: examples repo owns this runner; library adds a lean `pytest` suite.
- CI shim: if examples checkout is present, run this suite; otherwise run unit subset.

## Work Items

1) Add stage registry and option parsing to `run_all_tests.sh` (no reordering yet)
2) Implement triage subroutines for the four primary stages
3) Normalize log names and add triage summary file
4) Add `--continue-on-failure` to gather multiple failures in one run (optional)
5) Document new flags in `run_scripts/README.md`

## Success Criteria

- On a typical failure, triage reduces time-to-signal by running 1–2 minimal subtests before exit.
- No regressions to existing runs; team can still call the same scripts directly.

