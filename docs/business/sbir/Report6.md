# MONTHLY RESEARCH AND DEVELOPMENT (R&D) PHASE II TECHNICAL STATUS REPORT

**AFX246-DPCSO1: Open Topic**

**A Data-Centric Distributed Agentic Framework for DAF Simulation**

---

**Contract Information:** | **Controlling Office:**
--------------------------|-------------------------
**Topic Number:** AFX246-DPCSO1 | AF Ventures Execution Team
**Contract Number:** FA864924P0974 | Allen Kurella, Contracting Officer
**Phase:** II (Base Period) | **Email:** P2@afwerx.af.mil
**Status Report No.:** 6 (Bi-Monthly) |
**Period of Performance:** 14 AUGUST 2024 – 18 MAY 2026 |

---

**Principal Investigator:** | **TPOC:**
-------------------------|-----------
**Name:** Dr. Jason Upchurch | **Name:** Mr. Kevin Kelly, AFLCMC/HBE
**Email:** jason@rti.com | **Email:** kevin.kelly.34@us.af.mil

---

**Contractor:**
- **Name:** Real-Time Innovations, Inc.
- **Phone:** 408-990-7400
- **Address:** 232 East Java, Sunnyvale, CA. 94089

---

**Report Authors:**
Jason Upchurch, Gianpiero Napoli, Paul Pazandak

**SBIR/STTR DATA RIGHTS:**
Expiration of SBIR Data Rights: 14-AUGUST-2044. The Government's rights to use, modify, reproduce, release, perform, display, or disclose technical data or computer software marked with this legend are restricted during the period shown as provided in paragraph (b)(5) of the Rights In Other Than Commercial Technical Data and Computer Software—Small Business Innovation Research (SBIR) Program clause contained in the above identified contract. After the expiration date shown above, the Government has perpetual government purpose rights as provided in paragraph (b)(5) of that clause. Any reproduction of technical data, computer software, or portions thereof marked with this legend must also reproduce the markings.

**DISTRIBUTION STATEMENT B:** Distribution authorized to U.S. Government Agencies Only: Proprietary Information (18-NOV-2024) DFARS SBIR/STTR data rights - DFARS 252.227-7018

---

## TABLE OF CONTENTS

1.  PROGRAMMATIC INFORMATION
2.  PHASE II EFFORT (SPRINT 7 FOCUS)
3.  PHASE II WORK PLAN ALIGNMENT (M7)
4.  TASK STATUS UPDATES (TASK 7)
5.  QUANTITATIVE METRICS (SERVICE REGISTRY)
6.  ARCHITECTURE SUMMARY (DISTRIBUTED REGISTRY)
7.  RISKS, ISSUES, AND MITIGATIONS
8.  NEXT STEPS (SECURITY STAGED)
9.  APPENDICES

---

## 1. Programmatic Information
See ReportTemplate.md Section 1 for full boilerplate; unchanged.

## 2. Phase II Effort (Sprint 7 Focus)
- Milestone M7 objective: “Agent Service Registry – Design, Implementation & Demo.”
- We transitioned from a brokered registry to a fully distributed design on DDS. Functions are advertised via `FunctionCapability` and discovered by agents network‑wide; invocation is performed by RPC to the advertised `service_name`.
- This distributed approach eliminated SPOFs, enabled real-time composition, and underpins the agent‑as‑tool model.
 - Note on sequencing: M7 was completed before M6 (out of order) by agreement with the TPOC to unblock downstream integrations and demos.

## 3. Phase II Work Plan Alignment (M7)
- Delivered a working distributed registry and demo with agents and services joining/leaving dynamically. Discovery, targeting, and invocation validated in examples.
- Monitoring integrated: agents publish agent→service edges upon discovery; services publish service→function edges on advertisement. Graph viewer displays full topology.

### 3.1 Delta from Plan (M7)
- Original acceptance: “DAF acceptance of registry functionality” via a demo and technical documentation.
- Delivered (delta): Implemented a fully distributed registry (DDS advertisements + RPC) instead of a broker. This exceeds the original design goals by removing SPOFs and enabling real-time composition. A working demo and extensive docs are included (see Appendices).
- Rationale: Distributed registry was a prerequisite for reliable security and scale; brokered approach would have throttled dynamic composition and mixed trust domains.

## 4. Task Status Updates (Task 7)
- Implemented capability advertisement/discovery and standardized function metadata (name, description, JSON schema, provider_id, service_name).
- Enhanced service base class to auto‑register functions and publish capabilities on startup; added durable re‑publish for late joiners.
- Agent side: cached discovered functions and routed calls via `FunctionRequest/Reply` to the correct service endpoint.
- Integrated with OpenAIGenesisAgent: unified toolset now includes discovered functions; LLM’s tool selections trigger the correct DDS RPC calls.

### Task 7 Subtask Summaries (7.1–7.4)
- 7.1 Analyze and select target frameworks — Complete
  - Benchmarked modern agent ecosystems (e.g., OpenAI function/tool calling, Anthropic tool use, LangChain/LlamaIndex/Autogen patterns, Semantic Kernel actions) focusing on: portable tool schemas, asynchronous execution, streaming, and multi‑agent composition.
  - Selection outcome: standardize on OpenAI/JSON‑schema tool format as the lingua franca; keep GENESIS agent library neutral and provide light adapters for other ecosystems. This ensures broad interoperability without coupling to a single framework.

- 7.2 Evaluate mechanisms for heterogeneous inter‑agent communication — Complete
  - Defined DDS topics and RPC messages enabling cross‑framework operation: `FunctionCapability` (advertisement), `FunctionRequest/Reply` (RPC), `AgentCapability` (agent metadata), `AgentAgentRequest/Reply` (agent‑to‑agent), with `conversation_id` for context flow.
  - Added error/timeout/idempotency semantics and schema validation at the service boundary to protect against drift across stacks.

- 7.3 Architect the agent service registry — Complete (Distributed, library‑integrated)
  - Replaced the standalone registry process with in‑library capability advertisements on DDS. Services auto‑advertise on startup and refresh at interval; agents maintain a discovery cache with TTL, priority, version, and most‑recent tie‑breakers.
  - Invocation routes over DDS RPC to the published `service_name`; monitoring publishes `Service→Function` and `Agent→Service` edges for full traceability in the graph.

- 7.4 Demonstration and stakeholder feedback — Complete
  - Demonstrated live join/leave of services and agents, unified toolsets in the LLM call, and real‑time topology/chain tracing using the GraphInterface example. Showed out‑of‑order milestone execution (M7 before M6) as agreed with TPOC to unblock downstream work.
  - Feedback incorporated: emphasize SPOF removal, improve late‑joiner durability, and add conflict resolution for duplicate capability ads (priority and `advertised_at`).

## 5. Quantitative Metrics (Service Registry)
From repository analysis on 2025‑08‑28 (see `docs/reports/topics/service_registry.md`):
- Timeline: 2025‑04‑06 → 2025‑08‑20
- Commits: 30  |  Files changed: 57
- Additions/Deletions: +6,043 / −1,907
- Current LOC in area: ~4,136
- Top files by churn:
  - `genesis_lib/openai_genesis_agent.py`: +2140/−554
  - `genesis_lib/enhanced_service_base.py`: +1383/−966
  - `genesis_lib/function_discovery.py`: +1345/−278
  - `genesis_lib/rpc_service.py`: +389/−26
  - `genesis_lib/rpc_client.py`: +355/−59
  - `genesis_lib/config/datamodel.xml`: +274/−24

### 5.1 Recent Commits (Service Registry)
- 2fd4163 | 2025‑08‑20 | sploithunter | feat: enhance 3D graph visualization with improved activity tracking
- b3e6da7 | 2025‑08‑20 | sploithunter | feat: implement interface abstraction with graph monitoring and visualization
- c32c874 | 2025‑07‑11 | sploithunter | feat: Complete Genesis memory subsystem implementation
- ccec36f | 2025‑06‑12 | sploithunter | Unified monitoring system implementation and comprehensive plan; GraphMonitor + SERVICE component type
- 55e09d1 | 2025‑06‑06 | Jason | feat: Complete agent-to-agent communication fix and clean demo mode
- 1438ac7 | 2025‑06‑06 | Jason | 🎉 Implement @genesis_tool Auto-Discovery System – Phase 1 Complete
- 789c086 | 2025‑06‑06 | Jason | feat: Major Genesis enhancements – agent-to-agent comms, internal tools, tracing
- 50309dd | 2025‑06‑02 | Jason | Phase 5: Complete Multi-Agent System with Agent‑as‑Tool Pattern
- 9d8c77f | 2025‑05‑27 | Jason | Phase 4: Graph Connectivity Validation & Multi‑Agent Infrastructure
- 6098e05 | 2025‑05‑12 | Jason | Prevent service‑to‑service discovery; isolate services from discovery listeners

## 6. Architecture Summary (Distributed Registry)
- Advertisement: Services publish `FunctionCapability` with `function_id`, `name`, `description`, JSON `parameter_schema`, `provider_id`, and `service_name`.
- Discovery: Agents listen and maintain a discovery cache. Late joiners recover from durable QoS.
- Invocation: Agents send `FunctionRequest` (JSON args) and receive `FunctionReply` (JSON result) via DDS RPC to the published `service_name`.
- Monitoring: GraphMonitor publishes service→function edges; agents publish agent→service edges as functions are discovered.
 - Elimination of standalone process: the “service registry” is now a library capability (no external process). Services auto‑advertise at startup and re‑advertise periodically; agents consume and cache with TTL/refresh rules.
 - Conflict handling & versioning: duplicate functions resolve by most‑recent `advertised_at` timestamp and highest `priority` field; semantic `version` field enables safe upgrades.

## 7. Risks, Issues, and Mitigations
- Service/Function churn in large deployments: mitigated by durable discovery and re‑publish; graph-based monitoring aids diagnosis.
- Schema drift between services and agents: mitigated with strict JSON schema validation at service boundary and @genesis_tool schemas for internal tools.

## 8. Next Steps (Security Staged)
- DDS Security profiles for request/reply topics and capability advertisements.
- Authorship verification for capability ads and requester identity mapping.
- Access control per environment/partition; threat model and tests (replay, spoofing, malformed ads).

## 9. Appendices
- A. Service Registry Report (details): `docs/reports/service_registry_report.md`
- B. Activity Metrics (full): `docs/reports/activity_metrics.md`
- C. Topic Metrics (service registry): `docs/reports/topics/service_registry.md`
 - D. Detailed Sprint 7 Addendum: `docs/business/sbir/Report6_detailed.md`
