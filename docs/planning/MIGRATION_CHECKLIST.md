# Repository Separation: Migration Checklist (Draft)

This checklist enumerates steps to split the project without service disruption. Execute in phases; do not move files until approved.

## Pre-Migration (Prep)

- [ ] Confirm repo names and licenses
- [ ] Reserve PyPI name and TestPyPI test package
- [ ] Finalize DDS Setup doc and link in READMEs
- [ ] Decide viewer path (separate vs. keep in examples)
- [ ] Draft READMEs for each target repo
- [ ] Draft CI templates for library and examples
- [ ] Inventory `run_scripts/` and classify sub-scripts (library unit vs. example/integration)

## Phase 1: Scaffolding

- [ ] Create empty public repos: `genesis-lib`, `genesis-examples`, `genesis-viewer` (optional)
- [ ] Initialize README, CONTRIBUTING, CODE_OF_CONDUCT
- [ ] Copy planning docs relevant to each repo

## Phase 2: Packaging

- [ ] Migrate metadata to `pyproject.toml` using PEP 621
- [ ] Define optional dependencies (providers, viz)
- [ ] Verify build with `python -m build`
- [ ] Publish 0.1.0 to TestPyPI; verify clean install

## Phase 3: Content Moves

- [ ] Move `genesis_lib/` to `genesis-lib` repo
- [ ] Move `examples/*` to `genesis-examples`
- [ ] Preserve `run_scripts/` as authoritative test orchestrator; either keep it in examples or provide a shim in `genesis-lib` that calls the examples’ copy when available
- [ ] Adapt examples to depend on `genesis-lib` from PyPI
- [ ] If splitting viewer: move UI assets and define JSON schema

## Phase 4: CI/CD

- [ ] Enable library CI (lint, tests, build, publish on tag)
- [ ] Enable examples CI (smoke runs; nightly long tests)
- [ ] Optional: self-hosted runner/container with DDS for full tests

## Phase 5: Docs & Announcements

- [ ] Publish docs site for `genesis-lib`
- [ ] Update links across repos
- [ ] Announce release and migration notes
