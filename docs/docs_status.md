# Documentation Audit and Status

This index tracks the current status of key docs after the repo reorg. Use it to prioritize updates and avoid drift.

## Up-to-Date (no action needed)
- `docs/guides/function_call_flow.md`: Verified against code; minor clarifications already applied.
- `docs/guides/genesis_function_rpc.md`: Matches current FunctionRequest/Reply + advertisement flow.
- `docs/architecture/architecture.md`: New overview.
- `docs/architecture/architecture_detailed.md`: New detailed mapping to code.
- `docs/guides/Genesis_LIB_Explorer.md`: Quick engineer’s map; paths updated.

## Needs Minor Update (align wording/examples)
- `docs/architecture/monitoring_system.md`: Reflects current monitoring but predates unified GraphMonitor terminology in some places; add a short note pointing to GraphMonitor and current state.
- `docs/agents/agent_to_agent_communication.md`: Plan largely implemented via `genesis_lib/agent_communication.py`; add “Implemented notes” section with current class/method references and QoS used.
- `docs/planning/refactoring_genesis_app_interface_agent.md`: Most guidance implemented; keep as rationale, ensure links point to `docs/guides/function_call_flow.md` (fixed).

## Needs Major Update (superseded by implementation)
- `docs/planning/unified_monitoring_system_plan.md`: Substantially implemented via GraphMonitor (`genesis_lib/graph_monitoring.py`, `graph_state.py`).
  - Action: add a banner “Status: Implemented; see monitoring_system.md and GraphMonitor code” and either fold remaining deltas into a follow-on plan or mark completed.
- `docs/planning/event_driven_function_discovery_plan.md`: Event-driven discovery via `FunctionRegistry` listener/callbacks is implemented.
  - Action: update to reflect current APIs (capability listener, callbacks, discovery cache) or move to “completed plans”.
- `docs/planning/monitoring_v3_implementation_plan.md`: V3 goals largely reflected in code; consolidate residual “future work” into Issues/Next Steps.

## Merge/Consolidate Candidates
- Monitoring
  - Merge: `docs/planning/unified_monitoring_system_plan.md` → `docs/architecture/monitoring_system.md` as a “Design + Implementation” doc.
- Discovery
  - Merge: `docs/planning/event_driven_function_discovery_plan.md` → a short “Design notes” subsection in `docs/guides/genesis_function_rpc.md` or `docs/architecture/architecture_detailed.md`.

## Keep as Historical/Background (archive label)
- `docs/architecture/early_prototype_documentation.md`: Describes v0.x prototype; useful historical context.
- `docs/architecture/ModularComposableAgents.md`: Background pattern; keep under architecture.
- `docs/architecture/SelfAdaptation.md`, `docs/architecture/LifeLongLearning.md`: Vision/plans; not core to current code.
- `docs/planning/ToolkitPlan.md`, `docs/planning/cognativeTools_plan.md`, `docs/planning/function_injection_plan.md`, `docs/agents/agent_function_injection.md`: Inform direction; some parts superseded by @genesis_tool + agent-as-tool.

## Backlog/Planning (active but optional)
- `docs/planning/graph_topology_abstraction_plan.md`: In-progress effort aligned with interface abstraction viewer; valid.
- `docs/planning/genesis_implementation_plan.md`: Keep as roadmap; prune or link to Issues/Projects if desired.
- `docs/architecture/current_monitoring_analysis.md`: Keep as a deep-dive reference; optionally fold into monitoring_system.md.

## Suggested Next Edits (small, high-impact)
- Add “Status: Implemented (see …)” banner to:
  - `docs/planning/unified_monitoring_system_plan.md`
  - `docs/planning/event_driven_function_discovery_plan.md`
  - `docs/planning/monitoring_v3_implementation_plan.md`
- Update `docs/architecture/monitoring_system.md` intro with a one-paragraph GraphMonitor summary and links to `graph_monitoring.py`.
- Add an “Implementation Notes” section to `docs/agents/agent_to_agent_communication.md` with references to:
  - `AgentCommunicationMixin._setup_agent_discovery`
  - `AgentCommunicationMixin._setup_agent_rpc_service`
  - `AgentCommunicationMixin.send_agent_request`

## Verification Pointers
- Graph monitor implementation: `genesis_lib/graph_monitoring.py`, `genesis_lib/graph_state.py`
- Agent communication: `genesis_lib/agent_communication.py`
- Function discovery/ads: `genesis_lib/function_discovery.py`
- OpenAI agent tool flow: `genesis_lib/openai_genesis_agent.py`

---
Maintainers: update this file when significant docs are added/changed to keep the audit current.
