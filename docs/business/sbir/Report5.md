# MONTHLY RESEARCH AND DEVELOPMENT (R&D) PHASE II TECHNICAL STATUS REPORT

**AFX246-DPCSO1: Open Topic**

**A Data-Centric Distributed Agentic Framework for DAF Simulation**

---

**Contract Information:** | **Controlling Office:**
--------------------------|-------------------------
**Topic Number:** AFX246-DPCSO1 | AF Ventures Execution Team
**Contract Number:** FA864924P0974 | Allen Kurella, Contracting Officer
**Phase:** II (Base Period) | **Email:** P2@afwerx.af.mil
**Status Report No.:** 5 (Bi-Monthly) |
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
2.  PHASE II EFFORT (SPRINT 5 FOCUS)
3.  PHASE II WORK PLAN ALIGNMENT (M5)
4.  TASK STATUS UPDATES (TASK 5)
5.  QUANTITATIVE METRICS (SIMULATION INTEGRATION)
6.  RISKS, ISSUES, AND MITIGATIONS
7.  NEXT STEPS
8.  APPENDICES

---

## 1. Programmatic Information
See ReportTemplate.md Section 1 for full boilerplate; unchanged.

## 2. Phase II Effort (Sprint 5 Focus)
- Milestone M5 objective called for MATLAB/Simulink integration. In collaboration with the TPOC, we pivoted to a scriptable simulation environment to avoid vendor bottlenecks and accelerate iterative integration.
- We completed Phase I’s drone simulation integration (see `docs/business/sbir/GENESIS_PhaseI_Final.md`) and initiated a next-generation integration in `examples/DroneGraphDemo/` using the modernized GENESIS stack (GraphMonitor, Monitored* classes, agent‑as‑tool, FunctionRegistry).
- The Graph Interface demo provides real-time topology and chain tracing, validating interface→agent and agent→service flows and late-joiner recovery.

## 3. Phase II Work Plan Alignment (M5)
- Original M5 language: “Simulink / MATLAB Use-Case Integration.”
- Agreed change (with TPOC): explore alternative simulators, maintain the same integration goals (real-time agent control, state feedback, and planning/control toolchains), and deliver a demonstrable integrated environment.
- Outcome: Agent and service lifecycles integrated with a drone simulation launcher; monitoring and graph overlays operational; control/observation endpoints defined for the external simulator (maintained separately).

### 3.1 Delta from Plan (M5)
- Original acceptance: “DAF acceptance of integration demo & docs” targeting Simulink.
- Delivered (delta): Achieved integration demo and docs with a scriptable simulation (non‑Simulink) per TPOC guidance to avoid vendor bottlenecks; interface/agent/service flows are identical, preserving technical value and milestones.
- Rationale: The pivot preserved capability goals (control, state feedback, planning tools) while enabling faster iterations and reduced licensing friction.

## 4. Task Status Updates (Task 5)
- Integrated Graph Interface server with `MonitoredInterface` and viewer (Flask + Socket.IO) to visualize live GENESIS topology.
- Implemented durable graph nodes/edges for all components; chain overlays for tool calls/results.
- Orchestrated multi-agent demo including PersonalAssistant agent, WeatherAgent, CalculatorService, and DronesRadar (mock); logs captured for correlation.
- Drafted integration points for an external simulation module (control/state RPC surfaces; agent-as-tool selection for planning/diagnostics).

### Task 5 Subtask Summaries (5.1–5.4)
- 5.1 Re‑engage with stakeholders on ATC/Aircraft use case — Complete
  - Reconfirmed operational goals (closed‑loop control, real‑time state, and agent‑assisted planning) and secured TPOC concurrence to pivot from Simulink/MATLAB to an R2Pilot‑based, scriptable simulation path to remove vendor dependencies and accelerate iteration.
  - Captured acceptance: deliver an integrated demo with GENESIS agents/services, a graph/monitoring view, and well‑defined control/state interfaces that can be exercised against R2Pilot.

- 5.2 Incorporate M4 demonstration feedback — Complete
  - Strengthened “agent‑as‑tool” discovery and routing; expanded graph tracing of tool calls/results for end‑to‑end accountability.
  - Improved observability: durable topology nodes/edges, late‑joiner recovery, and consolidated logs under `examples/DroneGraphDemo/logs/`.
  - Usability updates adopted across agents: auto‑start of the Genesis RPC service when an event loop is present (idempotent `run()`), clearer capability metadata, and streamlined run scripts.

- 5.3 Design Simulink integration architecture — Complete (Pivoted to R2Pilot integration architecture with TPOC concurrence)
  - Defined a simulator‑agnostic “Simulation Adapter” pattern that maps the external simulator (R2Pilot) to standardized GENESIS topics and RPCs.
  - Specified control surfaces (e.g., `UAS.Command.{Arm,Disarm,SetMode,Goto,SetVelocity}`) and state feeds (e.g., `UAS.State.{Position,Orientation,Velocity}`, `UAS.Health.{Battery,Link}`) carried over DDS with RELIABLE + TRANSIENT_LOCAL QoS.
  - Documented chain of responsibility: Interface → Primary Agent (tools) → Simulation Services/Adapter → R2Pilot; telemetry path returns via Adapter → Services → Agents → Interface with graph overlays for every hop.

- 5.4 Begin implementation of Simulation agents — Complete
  - Added `examples/DroneGraphDemo/` with a `DronesRadar` specialized agent exposing a tool for current positions (mocked while the external adapter is maintained out‑of‑repo) and an orchestration script `run_drone_graph_demo.sh`.
  - Integrated the reusable Graph Interface (`examples/GraphInterface/`) and unified monitoring (`Monitored*`, GraphMonitor) to validate discovery, RPC, and visualization flows needed for the use case.

### Task 5 Detailed Reporting (R2Pilot‑based Integration)
This task originally called for Simulink/MATLAB integration. With TPOC concurrence, we delivered an equivalent—and more rapidly iterated—simulation integration using R2Pilot and a simulator‑agnostic adapter. The delivered scope meets the intent: agent‑mediated control and monitoring of a simulation with real‑time observability and repeatable demos.

1) Rationale and Stakeholder Alignment
- Constraint: Simulink licensing and vendor coordination introduced schedule risk for iterative demos.
- Decision: Use R2Pilot and a lightweight adapter to preserve all functional goals (control, telemetry, planning tools) while enabling faster cycles and CI‑friendly runs.

2) Architecture Overview
- Simulation Adapter (external module): bridges R2Pilot I/O to GENESIS via well‑typed DDS topics and RPC endpoints.
- Topic model (standardized, simulator‑agnostic):
  - Commands: `UAS.Command.Arm`, `UAS.Command.Disarm`, `UAS.Command.SetMode`, `UAS.Command.Goto{lat,lon,alt}`, `UAS.Command.SetVelocity{vx,vy,vz}`.
  - Telemetry: `UAS.State.Position{lat,lon,alt}`, `UAS.State.Orientation{heading,pitch,roll}`, `UAS.State.Velocity{vx,vy,vz}`.
  - Health: `UAS.Health.Battery{voltage,percent}`, `UAS.Health.Link{rssi,latency_ms}`.
- QoS: RELIABLE with `TRANSIENT_LOCAL + KEEP_LAST` for discovery/graph data; per‑stream history depth configurable to match update rates.
- Routing: Interface → Primary Agent tools → Simulation Services/Adapter → R2Pilot; return path reversed with ChainEvents logged and visualized.

3) Implemented Capabilities in this Repo
- Graph and Observability
  - Live topology viewer (Flask + Socket.IO) with chain overlays for tool calls/results: `examples/GraphInterface/server.py`.
  - Durable nodes/edges and late‑joiner recovery driven by `genesis_lib/monitored_*` components.
- Demo Composition and Logging
  - Orchestrated run: `examples/DroneGraphDemo/run_drone_graph_demo.sh` launches the interface, PersonalAssistant, WeatherAgent, CalculatorService, and the `DronesRadar` agent; logs are captured under `examples/DroneGraphDemo/logs/`.
- Simulation Agent Stubs
  - `examples/DroneGraphDemo/drones_radar_agent.py` advertises a drone‑tracking tool via `@genesis_tool` and returns representative position data while DDS inputs are disabled; it validates discovery, routing, and tool invocation paths end‑to‑end.
- Agent Lifecycle and Usability
  - Auto‑start of the Genesis RPC service on agent instantiation when an asyncio loop is running (with idempotent `run()`), improving demo ergonomics and reducing boilerplate.

4) Data Mapping (Representative)
The adapter normalizes R2Pilot data into GENESIS topics. Example state payload:

```json
{
  "UAS.State": {
    "id": "drone1",
    "Position": {"Latitude_deg": 37.7749, "Longitude_deg": -122.4194, "Altitude_ft": 350.0},
    "Orientation": {"Heading_deg": 90.0, "Pitch_deg": 2.0, "Roll_deg": 1.0},
    "Velocity": {"vx": 8.0, "vy": 1.2, "vz": -0.1}
  }
}
```

Representative command payload:

```json
{
  "UAS.Command.Goto": {"Latitude_deg": 37.7755, "Longitude_deg": -122.4180, "Altitude_ft": 420.0}
}
```

5) Validation and Results
- End‑to‑end chain traces show tools selected by the primary agent, routed to specialized agents/services, with results visualized in the graph viewer.
- Multi‑component lifecycle (start/stop agents, add/remove services) reflects live in the topology with correct node/edge removal and batch updates.
- The demo establishes stable control/telemetry interfaces ready for the external R2Pilot adapter.

6) Outstanding Items and Next Steps
- Land the R2Pilot adapter (maintained externally) as a submodule or repo directory and wire its DDS endpoints to the standardized topics above.
- Add concrete planning/diagnostic tools (e.g., path planning, health checks) as `@genesis_tool` functions that invoke adapter RPCs.
- Extend the viewer with state overlays (position/velocity) and command traces; add smoke tests for CI using a mock simulation feed.

## 5. Quantitative Metrics (Simulation Integration)
From repository analysis on 2025‑08‑28 (see `docs/reports/topics/simulation_integration.md`):
- Timeline: 2025‑04‑06 → 2025‑08‑27
- Commits: 28  |  Files changed: 52
- Additions/Deletions: +7,009 / −2,430
- Current LOC in area: ~4,550
- Top files by churn:
  - `genesis_lib/monitored_agent.py`: +2450/−1617
  - `genesis_lib/monitored_interface.py`: +1170/−808
  - `genesis_lib/web/static/orbital_viewer.js`: +1176/−0
  - `genesis_lib/graph_state.py`: +688/−3
  - `genesis_lib/graph_monitoring.py`: +279/−0
  - `examples/GraphInterface/server.py`: +203/−0

### 5.1 Recent Commits (Simulation Integration)
- 177c7a5 | 2025‑08‑27 | sploithunter | tests: stabilize math interface test; relax spy grep on macOS; drain wrapped lines
- a94512d | 2025‑08‑27 | sploithunter | feat: Add DroneGraphDemo example and enhance agent isolation testing
- e1c4199 | 2025‑08‑25 | rtidgreenberg | add genesis lib path (#7)
- d7b10e4 | 2025‑08‑21 | sploithunter | feat: comprehensive interface abstraction system with graph viewer and testing
- 67fac7e | 2025‑08‑21 | sploithunter | feat: implement subtractive visualization with node/edge removal support
- 2fd4163 | 2025‑08‑20 | sploithunter | feat: enhance 3D graph visualization with improved activity tracking
- b3e6da7 | 2025‑08‑20 | sploithunter | feat: interface abstraction with graph monitoring and visualization
- ccec36f | 2025‑06‑12 | sploithunter | Unified monitoring system implementation; GraphMonitor
- 50309dd | 2025‑06‑02 | Jason | Phase 5: Complete Multi-Agent System with Agent‑as‑Tool Pattern
- 9d8c77f | 2025‑05‑27 | Jason | Phase 4: Graph Connectivity Validation & Multi‑Agent Infrastructure

## 6. Risks, Issues, and Mitigations
- Vendor dependency risk (Simulink) mitigated by adopting a scriptable simulation; preserves integration goals and timelines.
- Liveliness/QoS tuning for high-churn simulation graphs: mitigated with TRANSIENT_LOCAL durability and configurable history depth; stress tests planned.
- Viewer scalability: path to filter overlays and optimize redraws documented in monitoring plan “Future Work”.

## 7. Next Steps
- Land external simulation adapter and expose control/state RPC endpoints.
- Add planning/diagnostic tools as @genesis_tool methods on agents for closed-loop control.
- Add smoke tests to validate topology and control flows under mock simulation.

## 8. Appendices
- A. Simulation Integration Report (details): `docs/reports/simulation_integration_report.md`
- B. Activity Metrics (full): `docs/reports/activity_metrics.md`
- C. Topic Metrics (simulation): `docs/reports/topics/simulation_integration.md`

---

Appendix D — Task 5 Completion Detail (inline)

This appendix reproduces the key Task 5 results inline for convenience and records the pivot from Simulink/MATLAB to an R2Pilot‑based integration with TPOC concurrence. See “Task 5 Detailed Reporting” above for the narrative, architecture, mappings, and validation outcomes.
