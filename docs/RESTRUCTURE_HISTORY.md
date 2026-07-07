# Documentation Restructure History

**Status:** Complete  
**Date:** 2026-07-01  
**Context:** Full audit of ~120 markdown files revealed overlapping setup instructions, planning docs
mixed with user docs, scratch notes committed to the repo, and no clear audience separation.

---

## Key Decisions

- `README.md` is the single user entry point — merged QUICKSTART.md into it
- pip is the canonical install path for users; DDS runtime is bundled in the `rti-connext` wheel
- RTI license file is the only RTI-specific user step
- `INSTALL.md` → renamed `CONTRIBUTING.md`, scoped to developer/contributor path
- `RTI_SETUP.md` → kept, developer-only (full DDS install for tools and test workflows)
- Test documentation lives in `tests/README.md`
- Internal/business/planning content staged in `_private/` — **still needs to move to a private repo**

---

## Target Structure vs Actual State

```
rti-genesis/
├── README.md          ✅ rewritten — pip install + license + first agent/service + examples
├── CONTRIBUTING.md    ✅ created (was INSTALL.md) — developer path
├── RTI_SETUP.md       ✅ kept, now developer-only
│
├── tests/
│   └── README.md      ✅ rewritten — DDS setup, test table, triage guide
│
└── docs/
    ├── README.md      ✅ updated as master index
    │
    ├── guides/
    │   ├── creating-a-service.md    ✅ done (was user-guides/function_service_guide.md)
    │   ├── creating-an-agent.md     ✅ done — new file written from genesis_api_overview.md
    │   ├── capabilities.md          ✅ done (was USER_CAPABILITIES_GUIDE.md)
    │   ├── monitoring.md            ✅ done (was V2_MONITORING_USAGE.md)
    │   └── local-inference.md       ✅ done (was NEMOTRON_INTEGRATION.md)
    │
    ├── reference/
    │   ├── topics.md                ✅ done (was GENESIS_TOPICS.md)
    │   ├── function-rpc.md          ✅ done (was genesis_function_rpc.md)
    │   ├── function-call-flow.md    ✅ done (was function_call_flow.md)
    │   ├── dds-configuration.md     ✅ done (was DDS_CONFIGURATION.md)
    │   ├── known-issues.md          ✅ done (was docs/notes/known_issues.md)
    │   └── rti-rpc-api.md           ✅ done (was RTI_7.3_RPC.md)
    │
    └── architecture/
        ├── overview.md              ✅ done — merged architecture.md + architecture_detailed.md
        ├── agent-hierarchy.md       ✅ done (was AGENT_ARCHITECTURE_QUICK_REFERENCE.md)
        ├── capability-system.md     ✅ done (was CAPABILITY_SYSTEM_ARCHITECTURE.md)
        ├── function-discovery.md    ✅ done — renamed + agent discovery section added
        ├── agent-as-tool.md         ✅ done — new file written from private sources
        ├── monitoring-system.md     ✅ done (was monitoring_system.md)
        ├── multi-provider.md        ✅ done (was MULTI_PROVIDER_ARCHITECTURE.md)
        ├── add-provider.md          ✅ done (was NEW_PROVIDER_GUIDE.md)
        └── explorer.md              ✅ done (was Genesis_LIB_Explorer.md)
```

**Unplanned files resolved:**
- `docs/architecture/api-overview.md` — content extracted into `docs/guides/creating-an-agent.md`, then deleted.
- `sequenceDiagram.mmd` — stray copy in `docs/guides/` deleted; copy in `docs/reference/` kept (function RPC diagram).

---

## File-by-File Status

### Rename / repurpose
| File | Action | Status |
|------|--------|--------|
| `INSTALL.md` | Rename → `CONTRIBUTING.md`, rewrite | ✅ Done |
| `RTI_SETUP.md` | Keep, link only from `CONTRIBUTING.md` / `tests/README.md` | ✅ Done |

### Merge into `README.md`, then delete
| File | Status |
|------|--------|
| `QUICKSTART.md` | ✅ Merged and deleted |

### Delete
| File | Status |
|------|--------|
| `docs/setup/dds_setup.md` | ✅ Deleted |
| `SUMMARY-GENESIS.md` | ✅ Deleted |
| `SUMMARY-A2A.md` | ✅ Deleted |
| `SUMMARY-NeMO.md` | ✅ Deleted |
| `docs/docs_status.md` | ✅ Deleted |
| `docs/architecture/memory_architecture.md` | ✅ Deleted |
| `docs/agents/agent_classification_refactor_summary.md` | ✅ Deleted |
| `docs/agents/agent_to_agent_implementation_checklist.md` | ✅ Deleted |
| `docs/notes/GrokClarifications1.md` | ✅ Deleted |
| `docs/notes/LinchpinIdeaTwo.md` | ✅ Deleted |
| `docs/notes/comment_history.md` | ✅ Deleted |
| `docs/notes/commit_history.md` | ✅ Deleted |

### Moved to `_private/` (still needs to go to a private repo)
| File | Status |
|------|--------|
| `MCP-vs-A2A.md` | ✅ In `_private/_root/` |
| `NeMo-vs-Genesis.md` | ✅ In `_private/_root/` |
| `docs/ReleaseBlog.md` | ✅ In `_private/_root/` |
| `docs/CONNEXT_DX_PROPOSAL.md` | ✅ In `_private/_root/` |
| `docs/GENESIS_DEVELOPER_PAGE.md` | ✅ In `_private/_root/` |
| `docs/planning/` (18 files) | ✅ In `_private/_planning/` |
| `docs/business/` (all files) | ✅ In `_private/_business/` |
| `docs/reports/` (all files) | ✅ In `_private/_reports/` |
| `docs/design/coding_agent_design.md` | ✅ In `_private/_planning/` |
| `docs/architecture/messaging_interfaces_vision.md` | ✅ In `_private/_planning/` |

### Move / rename
| From | To | Status |
|------|----|--------|
| `docs/user-guides/GENESIS_TOPICS.md` | `docs/reference/topics.md` | ✅ Done |
| `docs/user-guides/genesis_function_rpc.md` | `docs/reference/function-rpc.md` | ✅ Done |
| `docs/user-guides/function_call_flow.md` | `docs/reference/function-call-flow.md` | ✅ Done |
| `docs/user-guides/DDS_CONFIGURATION.md` | `docs/reference/dds-configuration.md` | ✅ Done |
| `docs/notes/known_issues.md` | `docs/reference/known-issues.md` | ✅ Done |
| `docs/user-guides/Genesis_LIB_Explorer.md` | `docs/architecture/explorer.md` | ✅ Done |
| `docs/NEMOTRON_INTEGRATION.md` | `docs/guides/local-inference.md` | ✅ Done |
| `DESIGN.md` | `examples/MultiAgent/DESIGN.md` | ✅ Done |
| `docs/reference/dds_guid_identification.md` | `docs/reference/dds-guid.md` | ✅ Done |

### Merges
| Planned merge | Status |
|---------------|--------|
| `architecture.md` + `architecture_detailed.md` → `overview.md` | ✅ Done |
| `agent_function_injection.md` content → `function-discovery.md` | ✅ Done — agent discovery section added to function-discovery.md |
| `agent_to_agent_communication.md` → `agent-as-tool.md` (new) | ✅ Done |
| `genesis_api_overview.md` → `creating-an-agent.md` (guide) | ✅ Done — extracted into user guide, source deleted |

---

## Remaining Work

| Item | What to do |
|------|-----------|
| `_private/` | Move entire folder to a separate private repository and remove from this repo |
