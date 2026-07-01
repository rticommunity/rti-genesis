# `run_scripts/` Inventory and Coverage (Draft)

This document lists all scripts under `run_scripts/`, whether they are executed by `run_all_tests.sh`, how they’re referenced by other scripts, and suggested actions. The goal is to surface useful scripts not covered by the main runner and decide whether to fold them into triage or keep as utilities.

Legend:
- Covered: invoked directly by `run_all_tests.sh`
- Indirect: not invoked by the runner, but used by a script that is
- Orphan: not invoked by the runner and not used by invoked scripts
- Action: keep, fold-into-triage, migrate-to-examples, retire, or clarify-as-utility

## Covered by `run_all_tests.sh`

- run_all_tests.sh — main orchestrator
- run_test_agent_memory.sh — Covered; calls test_agent_memory.py (Indirect)
- test_agent_to_agent_communication.py — Covered
- run_interface_agent_service_test.sh — Covered; uses simpleGenesisAgent.py, calculator_service.py, simpleGenesisInterfaceStatic.py (Indirect)
- run_math_interface_agent_simple.sh — Covered; uses math_test_agent.py, math_test_interface.py (Indirect)
- run_math.sh — Covered
- run_multi_math.sh — Covered
- run_simple_agent.sh — Covered
- run_simple_client.sh — Covered
- test_calculator_durability.sh — Covered
- run_test_agent_with_functions.sh — Covered; calls test_agent.py (Indirect)
- start_services_and_cli.sh — Covered
- test_genesis_framework.sh — Covered
- test_monitoring.sh — Covered; calls test_monitoring.py (Indirect)

## Indirect dependencies (used by covered scripts)

- test_agent_memory.py — used by run_test_agent_memory.sh
- math_test_agent.py — used by run_math_interface_agent_simple.sh
- math_test_interface.py — used by run_math_interface_agent_simple.sh
- simpleGenesisAgent.py — used by run_interface_agent_service_test.sh
- simpleGenesisInterfaceStatic.py — used by run_interface_agent_service_test.sh
- test_agent.py — used by run_test_agent_with_functions.sh, test_monitoring.sh
- test_monitoring.py — used by test_monitoring.sh

## Orphans and Utilities (not executed by the runner today)

- README_interactive_memory_test.md — doc
- baseline_test_agent.py — Orphan; baseline agent tests
- baseline_test_interface.py — Orphan; baseline interface tests
- comprehensive_multi_agent_test_interface.py — Orphan; comprehensive interface tests
- interactive_memory_test.py — Orphan; interactive memory scenario
- interface_keepalive.py — Utility; not a test (keepalive helper)
- limited_mesh_test.sh — Orphan; mesh scenario
- run_baseline_agent_with_spy.sh — Orphan; baseline + rtiddsspy
- run_baseline_interface_agent_test.sh — Orphan; baseline interface/agent
- run_example_agent1.sh — Orphan; example agent
- run_example_agent1_with_functions.sh — Orphan; example agent + functions
- run_interactive_memory_test.sh — Orphan; wraps interactive_memory_test.py
- run_interface_agent_agent_service_test.sh — Orphan; alt pipeline variant
- run_math_interface_agent_test.sh — Orphan; alt math interface/agent variant
- run_math_service.sh — Utility; service-only helper
- run_tests.sh — Orphan; older orchestrator
- simpleGenesisInterfaceCLI.py — Orphan; CLI variant of interface
- test_genesis_complete.sh — Orphan; umbrella script
- test_interface_durability.sh — Orphan; interface-side durability variant
- test_memory_router.py — Orphan; appears unit-ish
- test_memory_with_tools.py — Orphan; memory + tools
- test_personal_agent_durability.sh — Orphan; personal agent durability

## Suggested Actions

- Fold-into-triage (as fast isolators after failures):
  - baseline_test_agent.py, baseline_test_interface.py
  - run_baseline_agent_with_spy.sh, run_baseline_interface_agent_test.sh
  - run_math_interface_agent_test.sh (as lighter alternative to the simple variant if faster)
  - test_interface_durability.sh, test_personal_agent_durability.sh (map to durability failure triage)
  - limited_mesh_test.sh (mesh-specific triage when agent↔agent fails)

- Keep as dev utilities (document in run_scripts/README.md):
  - interface_keepalive.py, run_math_service.sh, simpleGenesisInterfaceCLI.py

- Migrate-to-examples (post-split; keep runnable docs):
  - run_example_agent1.sh, run_example_agent1_with_functions.sh
  - interactive_memory_test.py, run_interactive_memory_test.sh
  - comprehensive_multi_agent_test_interface.py, test_genesis_complete.sh

- Evaluate/Retire (if superseded by covered tests):
  - run_tests.sh (older orchestrator; likely superseded)
  - run_interface_agent_agent_service_test.sh (duplicate of pipeline test)

- Library-unit candidates (mirror into pytest later):
  - test_memory_router.py, test_memory_with_tools.py

## Next Steps (No code moves yet)

- Tag each orphan with a header comment noting its category (triage, dev utility, example) when we start refactoring.
- Add a “Not in run_all_tests” section in `run_scripts/README.md` linking to this inventory.
- Prioritize a minimal set to fold into triage mode for quick isolation.

