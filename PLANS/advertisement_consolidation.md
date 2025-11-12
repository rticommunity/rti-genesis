# Genesis Advertisement Consolidation Plan

Scope
- Consolidate discovery/advertisement topics into a single durable channel.
- Make ComponentLifecycleEvent volatile (events-only, not durable history).
- Deprecate GenesisRegistration.
- Leave RPC unchanged for now (both service and agent RPC paths).

Guiding principles
- Durable for state: advertisements, graph nodes/edges.
- Transient for activity: lifecycle and chain events.
- Incremental changes with tests between phases; avoid sweeping refactors.

Current state (as of plan creation)
- Advertisements (durable):
  - `rti/connext/genesis/FunctionCapability` (TRANSIENT_LOCAL, RELIABLE, KEEP_LAST depth ~500)
  - `rti/connext/genesis/AgentCapability` (TRANSIENT_LOCAL, RELIABLE, KEEP_LAST depth ~500)
  - `rti/connext/genesis/GenesisRegistration` (TRANSIENT_LOCAL, RELIABLE, KEEP_LAST depth ~500)
- Graph (durable):
  - `rti/connext/genesis/monitoring/GenesisGraphNode` (writers TRANSIENT_LOCAL, readers RELIABLE KEEP_ALL)
  - `rti/connext/genesis/monitoring/GenesisGraphEdge` (writers TRANSIENT_LOCAL, readers RELIABLE KEEP_ALL)
- Events (transient):
  - `rti/connext/genesis/monitoring/ChainEvent` (VOLATILE, RELIABLE, KEEP_ALL)
  - `rti/connext/genesis/monitoring/ComponentLifecycleEvent` (currently TRANSIENT_LOCAL writer; to be changed to VOLATILE)
  - `rti/connext/genesis/monitoring/MonitoringEvent` (legacy; currently durable when enabled)

Outcome targets
- Single advertisement topic: `rti/connext/genesis/Advertisement` (durable, reliable) for AGENT/FUNCTION/REGISTRATION kinds.
- ComponentLifecycleEvent is volatile, chain remains volatile, graph remains durable.
- GenesisRegistration deprecated; presence carried by AGENT advertisement.
- RPC untouched (service naming and one-to-one agent RPC remain as-is for now).

Phased plan (test early, test often)

Phase 1 — Make lifecycle events volatile
- Change writer QoS for `ComponentLifecycleEvent` to VOLATILE, RELIABLE.
- Keep graph node/edge durable and ChainEvent volatile as-is.
- Files to change:
  - Update writer QoS in: `Genesis_LIB/genesis_lib/graph_monitoring.py` (ComponentLifecycleEvent writer).
- Sanity tests:
  - Start a monitored agent and interface, observe lifecycle updates are received live and not backfilled on late join.
  - Validate graph node/edge durability unaffected (late joiners reconstruct topology).
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 2 — Define unified advertisement model (no code switching yet)
- datamodel.xml additions:
  - Enum `AdvertisementKind` = { FUNCTION, AGENT, REGISTRATION }.
  - Struct `GenesisAdvertisement` with fields:
    - `advertisement_id` (key, string 128)
    - `kind` (AdvertisementKind)
    - `name` (string 256)
    - `description` (string 2048)
    - `service_name` (string 256)
    - `provider_id` (string 128)
    - `last_seen` (int64)
    - `payload` (string 8192) — JSON with flexible details (e.g., parameter_schema, capabilities, model_info, classification, etc.)
  - Topic: `rti/connext/genesis/Advertisement`.
- QoS guidance:
  - Writers/Readers: TRANSIENT_LOCAL, RELIABLE, KEEP_LAST (depth 500), liveliness AUTOMATIC lease ~2s.
- Sanity tests:
  - Ensure types load via QosProvider and topic can be created (no writers/readers yet).
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 3 — Function advertisement: dual-publish, add reader, then cut legacy
- Step 3a: Dual-publish
  - In `FunctionRegistry` (`Genesis_LIB/genesis_lib/function_discovery.py`):
    - Add a DataWriter for `GenesisAdvertisement`.
    - When advertising a function, publish both:
      - Existing `FunctionCapability`.
      - New `GenesisAdvertisement` with `kind=FUNCTION`, payload carrying `parameter_schema`, `capabilities`, etc.
  - Add a DataReader for `GenesisAdvertisement` that updates `discovered_functions` identically to the legacy path.
  - Discovery logic prefers new advertisement if both present; otherwise falls back.
- Step 3b: Switch over
  - Update discovery to rely solely on `GenesisAdvertisement`.
  - Remove legacy `FunctionCapability` reader/writer and associated code paths.
- Tests for each step:
  - Verify functions are discovered and callable via `FunctionRequester`.
  - Confirm graph discovery callbacks still fire (edges to provider/service), as they use registry updates.
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 4 — Agent advertisement: dual-publish, add reader, then cut legacy
- Step 4a: Dual-publish
  - In `AgentCommunicationMixin` (`Genesis_LIB/genesis_lib/agent_communication.py`):
    - Add a DataWriter for `GenesisAdvertisement`.
    - When publishing agent capability, publish both legacy `AgentCapability` and new `GenesisAdvertisement` with `kind=AGENT` (payload holds `model_info`, `capabilities`, `classification_tags`, `default_capable`, etc.).
  - Add a DataReader for `GenesisAdvertisement` to populate `discovered_agents` and existing agent lookup APIs.
- Step 4b: Switch over
  - Migrate discovery to use only `GenesisAdvertisement`.
  - Remove legacy `AgentCapability` reader/writer and code paths.
- Tests for each step:
  - Interface and agent discovery continues to work (existing tests that check discovery logs and graph updates).
  - Agent-to-agent communications unaffected (RPC untouched).
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 5 — Deprecate GenesisRegistration
- Replace registration announcements with `GenesisAdvertisement(kind=AGENT)`.
  - Remove DataWriter for `GenesisRegistration` in `GenesisApp`/`GenesisAgent` and redirect presence to advertisement writer from Phase 4.
- Update tests/scripts to stop searching for `GenesisRegistration` and instead verify `Advertisement` with kind=AGENT (or presence in agent discovery path).
- Tests:
  - `tests/active/run_math_interface_agent_simple.sh` and related scripts updated to validate new presence path.
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 6 — Datamodel cleanup
- Remove `FunctionCapability`, `AgentCapability`, and `genesis_agent_registration_announce` types from `datamodel.xml`.
- Remove code paths depending on legacy types.
- Tests:
  - Full test suite; ensure advertisement-only discovery works end-to-end.
  - run tests/run_all_tests.sh to ensure nothing has broken (be aware that some tests "grep" for topics in logs that could break)

Phase 7 — Documentation and examples
- Update `README.md`, `QUICKSTART.md`, and any code snippets to use `GenesisAdvertisement`.
- Document the `payload` JSON schema expectations for AGENT and FUNCTION flavors.

Acceptance criteria per phase
- Phase 1: Lifecycle events are not backfilled; graph topology remains reconstructible.
- Phase 3: Functions can be discovered and invoked with only the new advertisement.
- Phase 4: Agent discovery APIs deliver the same information via the new advertisement.
- Phase 5: No code writes or reads `GenesisRegistration`; presence is via advertisement.
- Phase 6: No legacy types remain in `datamodel.xml` or code.

Out-of-scope (for now)
- RPC naming/model changes, including keyed services or alternate RPC routing.
- Any streaming or chunking changes to large payloads.

Risk and rollback
- Each phase is small and testable; rollback by reverting the last module changed (e.g., switch readers back to legacy topics).
- The dual-publish steps (3a, 4a) provide a stable transition point if issues arise.

Notes
- QoS consistency matters: keep advertisement and graph durable; events volatile.
- Depth and liveliness values should stay aligned with current code to avoid discovery regressions.

Provider‑Neutral Naming (planned cleanup)
- Rationale: Some topic/service names include provider‑specific labels (e.g., OpenAI). Names should be generic to support any backend.
- Targets (non‑breaking plan after consolidation):
  - Default `base_service_name` in agents: change "OpenAIChat" → "Chat"; preserve explicit overrides.
  - Replace hardcoded topic name `OpenAIAgentReply` in `genesis_lib/monitored_interface.py` with generic reply listener strategy:
    - Prefer binding to the RPC reply reader via service name rather than a fixed topic string, or
    - Use a provider‑agnostic topic name (e.g., `InterfaceAgentReply`) only if a standalone reply topic is still required.
  - Review tests/log messages that grep for provider names and update to generic labels.
- Execution order:
  1) Finish advertisement consolidation (Phases 3–6).
  2) Update defaults and topic names; adjust tests, docs.
  3) Validate: run `tests/run_all_tests.sh` and spot‑check agent/interface flows.
