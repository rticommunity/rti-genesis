# Report: Distributed Service Registry Evolution

Date: 2025-08-28

## Executive Summary
We transitioned the service/function registry from a brokered design to a fully distributed architecture built on DDS. Functions are advertised network‑wide via `FunctionCapability` and discovered dynamically by agents and tools. This shift unlocked scalability, resilience, and real‑time composition, and it underpins the agent‑as‑tool pattern.

## Background & Milestones
- Early versions used a broker for function registration and dispatch.
- Milestone schedule (see `docs/business/sbir/MileStoneTable.md`) identified a distributed registry as a prerequisite before security hardening.
- The distributed registry is now implemented and in daily use; security (DDS Security) is staged for the next report.

## Architecture Overview
- Advertisement: Services publish `FunctionCapability` with `function_id`, `name`, `description`, JSON `parameter_schema`, `provider_id` (writer GUID), and `service_name` (RPC endpoint).
- Discovery: Agents subscribe to `FunctionCapability`, maintaining a discovery cache keyed by `function_id`/`name`.
- Invocation: Agents call functions via `FunctionRequest/Reply` (Python IDL) using the `service_name` resolved from discovery.
- Monitoring: GraphMonitor publishes service→function edges; agents publish agent→service edges upon discovery.

## Key Implementations (code)
- `genesis_lib/function_discovery.py` — Capability advertisement, discovery listener, callbacks, and cache.
- `genesis_lib/enhanced_service_base.py` — Auto‑registration and advertisement of service functions; edges for service→function.
- `genesis_lib/rpc_service.py` / `genesis_lib/rpc_client.py` — Request‑reply loop for function calls with JSON args/results.
- `genesis_lib/datamodel.py` — Python IDL for function requests/replies.
- `genesis_lib/config/datamodel.xml` — DDS types for `FunctionCapability` and monitoring/graph topics.
- `genesis_lib/openai_genesis_agent.py` — Unified toolset builder; calls functions by name using discovered metadata.

## Outcomes
- Zero central broker; no single point of failure.
- Dynamic composition: services can join/leave; functions appear/disappear and are reflected in real time.
- Interoperability: any compliant service can advertise functions; any agent can discover and call them.
- Traceability: advertisements and calls are observable via GraphMonitor and ChainEvents.

## Work Volume (indicative)
- Significant changes across discovery, services, agents, and monitoring (see git history on the files above).
- New abstractions (GraphMonitor) to present relationships as durable graph nodes/edges.

## Next Steps (security staged)
1. Apply DDS Security profiles for request/reply topics and capability advertisements.
2. Add integrity/authorship fields in capability ads where applicable (signatures or guid→identity mapping).
3. Access control: partitioning or participant permissions per environment/domain.
4. Threat model and tests: malformed ads, replay, and endpoint spoofing defenses.
