# Testing Strategy and `run_scripts/` Transition (Draft)

This document captures how we will preserve the current `run_scripts/`-based testing while preparing for a cleaner split across repos.

## Current State

- `run_scripts/run_all_tests.sh` orchestrates both unit and integration tests.
- Many unit tests are invoked through sub-scripts under `run_scripts/`.
- DDS is required for a majority of tests.

## Principles

- Do not break the canonical runner (`run_all_tests.sh`).
- Keep tests runnable by users via existing scripts during the entire transition.
- Improve granularity over time, but prioritize continuity.

## Near-Term Plan (No Moves Yet)

- Treat `run_scripts/` as the single source of truth for test orchestration.
- Document that the library CI may call `run_scripts/run_all_tests.sh` when an examples checkout is available (e.g., via submodule or CI checkout).
- Add markers/comments (in planning only) about which sub-scripts are library-unit vs. example/integration focused for future factoring.

## Migration Path (Phased)

1) Inventory and Tagging
- Identify sub-scripts that run pure library unit tests vs. example/integration tests.
- Tag or list them in a map (planning doc) to guide separation later.

2) Library Unit Tests into `pytest`
- Gradually mirror pure library unit tests into a `pytest` suite inside `genesis-lib`.
- Maintain the original `run_scripts/` calls during this phase; both paths should succeed.

3) Example/Integration Tests Remain Scripted
- Keep integration and long-running tests under `genesis-examples/run_scripts/` once repos split.
- `run_all_tests.sh` in examples continues to orchestrate end-to-end validation.

4) CI Shims
- Library CI: when examples are present (submodule or checkout), invoke `run_scripts/run_all_tests.sh` to preserve exhaustive coverage.
- Otherwise, run the library’s `pytest` subset.

5) De-risking and Cleanup
- When parity is achieved, announce deprecation timeline for relying on `run_scripts/` for pure unit tests.
- Keep `run_all_tests.sh` as the end-to-end suite orchestrator long-term.

## Success Criteria

- Users can continue to run `./run_scripts/run_all_tests.sh` throughout.
- Library CI runs a reliable unit subset even without examples; full coverage available when examples are present.
- Clear documentation on which tests live where and how to run them.

