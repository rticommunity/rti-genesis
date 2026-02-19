# Genesis LIB: Repository Separation and Release Plan

This document outlines how to split the project into clearly scoped repositories, how to package and publish the core library, and what documentation and CI/CD each area maintains. It is a plan only; no code or files are being moved yet.

## Goals

- Separation of concerns: Split core library, examples, visualization, and business docs.
- Easy adoption: Publish to PyPI so users can `pip install genesis-lib`.
- Sustainable workflow: Independent CI/CD, versioning, and documentation per area.

## Target Repositories

- `genesis-lib` (public): Core runtime, stable APIs, typed, tested, docs, published to PyPI.
- `genesis-examples` (public): Runnable examples, orchestration scripts, integration demos; depends on `genesis-lib` via PyPI.
- `genesis-viewer` (public, optional): Reusable visualization UI if/when generalized; otherwise remain in examples until stable.
- `genesis-business` (private): SBIR/internal docs, milestones, reporting, and proprietary materials.

## What Goes Where

- Core Library (`genesis-lib`):
  - Public APIs: `genesis_lib/interface.py`, `genesis_lib/openai_genesis_agent.py`, `genesis_lib/monitored_interface.py`, and related stable modules.
  - DDS as a first-class requirement: the library assumes Connext DDS is installed and configured; no attempt to abstract it away for a “non-DDS mode”.
  - Lightweight CLI (e.g., version, quickstart, diagnostics) including DDS diagnostics.
  - LLM/provider integrations as optional extras (e.g., OpenAI/Anthropic), but DDS is core.
  - Unit and integration tests that rely on DDS; where CI cannot run DDS, mark and document skips.
  - Public docs: quickstart, API reference, architecture overview, contribution guide, and a central DDS installation guide shared with examples.

- Examples (`genesis-examples`):
  - Example networks/apps and services (e.g., `examples/*`).
  - Runner/orchestration scripts (e.g., `run_scripts/*`).
  - Integration tests and flows that exercise DDS (DDS is required across the board).
  - Walkthrough docs per example with troubleshooting, linking to the central DDS setup section.

Note on `run_scripts/` and current tests

- Today, `run_scripts/run_all_tests.sh` is the canonical entrypoint that orchestrates both unit and integration tests, and many unit tests are invoked through its sub-scripts.
- We will not remove or wholesale relocate `run_scripts/` until an equivalent (or better) test harness exists. Any repo split must preserve this runner intact.
- Near-term, plan for either:
  - Keeping `run_scripts/` in the main workspace (or examples repo) and providing a shim in `genesis-lib` CI to call it when the examples repo is present; or
  - Duplicating a minimal subset of scripts needed for core library unit tests inside `genesis-lib`, while integration/example-heavy scripts live in `genesis-examples`.
  - In all cases, `run_all_tests.sh` remains authoritative during transition.

- Viewer (`genesis-viewer`):
  - UI assets, templates, and dev server if reusable; define a stable JSON schema produced by examples/services.
  - If not yet general-purpose, keep within `genesis-examples` until stabilized.

- Business (`genesis-business`):
  - SBIR reports, milestone tables, planning, and any proprietary info (e.g., `docs/business/sbir/*`).

## Packaging & Distribution (PyPI)

- Project name: `genesis-lib` (confirm availability/reservation).
- Build system: `pyproject.toml` using `setuptools` (PEP 517/518). Keep `setup.py` until full PEP 621 migration.
- Python: `>=3.10,<3.11` initially (per current guidance).
- DDS is a core runtime requirement for `genesis-lib`. It is provided by RTI and installed outside of pip; the library detects and uses the installed Connext DDS at runtime. We will document installation and environment configuration explicitly.
- Optional extras keep non-DDS features modular:
  - `openai`, `anthropic` for LLM providers
  - `viz` for optional visualization helpers
  - Example: `pip install genesis-lib[openai]`
- Entry points: `genesis` CLI with `--version`, `quickstart`, and diagnostics; keep current monitoring entry points.
- DDS compatibility: Document RTI Connext DDS 7.3.0+ requirement and environment configuration (see DDS Setup section). Connext Express will be the default license path; a dedicated subsection will describe obtaining/activating Express.

### DDS Setup (shared doc referenced by both repos)

- Central document: a single “DDS Setup” page referenced by `genesis-lib` and `genesis-examples` READMEs.
- Covers installation on macOS, Linux, and Windows; version ≥ 7.3.0.
- Environment variables and paths:
  - `NDDSHOME` pointing to installation (e.g., `$HOME/rti_connext_dds-7.3.0`).
  - Platform paths: `LD_LIBRARY_PATH` (Linux), `DYLD_LIBRARY_PATH` (macOS), `Path` (Windows).
  - License var if needed: `RTI_LICENSE_FILE` (note: Connext Express guidance to be finalized).
  - Sourcing vendor scripts: `rticonnextdds-installation/scripts/rtisetenv.*` as a reliable alternative.
- Quick verification: `rtiddsspy -v`, `rtiddsgen -version`, and a minimal Python import/run check.
- Troubleshooting: common path issues, architecture mismatches, and how to print effective env.

## Documentation

- `genesis-lib`: Quickstart, API reference, architecture overview, plugin system, CONTRIBUTING, changelog.
- `genesis-examples`: Example catalog with run instructions; links back to library docs.
- `genesis-viewer`: Data contract (JSON schema), usage, and embedding options.
- `genesis-business`: Remains private; public docs may link out as appropriate.

## Testing & CI

- `genesis-lib`: `pytest`, type checks (`mypy`), linting. Many tests require DDS; where CI agents cannot provide DDS, mark those tests and document how to run them locally (with DDS). Consider a self-hosted runner or container image with DDS for full coverage.
- `run_scripts/` compatibility: Until migration completes, library CI may invoke `run_scripts/run_all_tests.sh` via a shim when the examples repo is available (e.g., as a submodule or checked out in CI). The authoritative runner remains `run_all_tests.sh` and its sub-scripts.
- `genesis-examples`: Preserve full-suite scripts (e.g., `run_all_tests.sh`), or incrementally migrate to `pytest`/`tox` while keeping existing semantics.
- CI pipelines:
  - Library: lint → type-check → unit tests → build → test install → publish on tag.
  - Examples: smoke runs per example; long-running tests on nightly schedule.
  - Viewer: build, lint, and optionally deploy demo site.

## Release & Versioning

- SemVer for `genesis-lib`.
- Examples track major compatibility or version independently.
- Deprecations documented with warnings and a one-release grace period.

## Two-Week Execution Plan

Week 1

1) Repo scaffolding: Create `genesis-lib`, `genesis-examples`, and optionally `genesis-viewer`; add baseline READMEs and CONTRIBUTING.
2) Package skeleton: Add `pyproject.toml` with `setuptools` build system; retain `setup.py` while migrating.
3) API audit: Mark public APIs (stabilize `interface.py`, `openai_genesis_agent.py`, `monitored_interface.py`) and define extension points/extras.
4) Docs quickstart: Draft “Install and Hello World” for `genesis-lib`; stub example catalog.
5) CI setup: Lint, tests, build, and release workflows for `genesis-lib`.

Week 2

1) Migrate examples: Move `examples/*`, `run_scripts/*`, and DDS-heavy tests to `genesis-examples`; adapt to use `pip install genesis-lib`.
2) Viewer decision: If reusable, extract to `genesis-viewer` and define JSON schema; else keep under `genesis-examples`.
3) Integration tests: Wire up full-suite script in `genesis-examples`; document DDS setup.
4) First release: Publish `genesis-lib` 0.1.0 to TestPyPI; validate; then publish to PyPI.
5) Docs publish: Host `genesis-lib` docs (e.g., GitHub Pages); cross-link from examples.

## Success Criteria

- `pip install genesis-lib` works and `genesis --version` runs.
- `genesis-examples` instructions run end-to-end using PyPI `genesis-lib`.
- Library docs published; examples catalog clear; business docs are private.
- Green CI pipelines; release pipeline publishes on tags.

## Risks & Mitigations

- DDS dependency: Keep as optional extra; isolate DDS tests; clear setup docs.
- Viewer scope: Start in examples; split when contract stabilizes.
- API churn: Gate behind SemVer; maintain changelog and deprecation notes.

## Open Questions

- Preferred PyPI name and reservation?
- Viewer: split now or later?
- Licensing for public repos (Apache-2.0, MIT, other)?
- Minimum examples to ship with Week 2?
