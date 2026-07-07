# Bringing AI to RTI Connext: Enabling the Intelligent DDS Application

**Author:** Gianpiero Napoli  
**Date:** 2026-04-20  
**Status:** Draft for Discussion

---

## Overview

AI and distributed systems are converging. The most capable AI systems today are not single models; they are networks of agents that perceive, reason, and act across distributed infrastructure. At the same time, the most demanding distributed systems (autonomous vehicles, surgical robots, defense platforms) are beginning to require AI-driven decision-making at their core.

RTI Connext DDS sits at the intersection of both worlds. It is the connectivity fabric trusted for the most demanding real-time distributed systems on the planet. The question is: **can it also become the connectivity fabric for the next generation of intelligent, AI-driven systems?**

This document proposes a path to get there. The ideas here are grounded in lessons learned from **GENESIS**, an internal prototype that embedded AI agent capabilities directly into a Connext-based framework. GENESIS proved the concept. What follows is a set of concrete proposals for bringing those capabilities into the standard Connext ecosystem, not as a separate AI framework bolted on top, but as a natural extension of the tools and APIs Connext developers already use.

The goal is to make every Connext developer an AI-capable developer. Not by asking them to learn a new stack, but by meeting them where they are: in their existing applications, their existing data models, and their existing DDS domains, and giving those systems the ability to reason, converse, and collaborate.

Each suggestion below is self-contained and can be evaluated independently. Together they form a layered path from **developer ergonomics** (Suggestion 1) to **AI-native distributed systems** (Suggestion 4).

| # | Suggestion | Status |
|---|---|---|
| 1 | [Python Decorator API](#suggestion-1-python-decorator-api) | Draft |
| 2 | [LLM-Driven DDS Interaction via MCP](#suggestion-2-llm-driven-dds-interaction-via-mcp) | Draft |
| 3 | [Agent Enablement for Existing DDS Applications](#suggestion-3-agent-enablement-for-existing-dds-applications) | Draft |
| 4 | [Peer-to-Peer Agent Discovery and Delegation](#suggestion-4-peer-to-peer-agent-discovery-and-delegation) | Draft |

---

## Background

The GENESIS prototype demonstrated that the most common DDS programming patterns (exposing a function over RPC, publishing data on a timer, subscribing to a topic) require 50–80 lines of boilerplate each: loading XML type definitions, constructing participants, configuring QoS, managing topics and pub/sub entities, then writing a polling loop. This cost is paid before a single line of domain logic is written, and it repeats for every endpoint.

Several of the patterns GENESIS introduced to address this are general-purpose and have no dependency on its AI/agent layer. This document proposes folding them into the **standard RTI Connext Python API**.

---

## Suggestion 1: Python Decorator API

### Current State

The `rti.connextdds` and `rti.rpc` Python packages expose a full-featured but low-level API. Standing up a minimal RPC service today requires:

```python
# 1. Load XML type definitions
provider = dds.QosProvider("datamodel.xml")
req_type = provider.type("my_lib", "MyRequest")
rep_type = provider.type("my_lib", "MyReply")

# 2. Create participant and configure QoS
participant = dds.DomainParticipant(domain_id=0)
writer_qos = provider.datawriter_qos_from_profile("MyLib::MyProfile")
reader_qos = provider.datareader_qos_from_profile("MyLib::MyProfile")

# 3. Create the replier
replier = rpc.Replier(
    request_type=req_type,
    reply_type=rep_type,
    participant=participant,
    service_name="my/service/name",
    datawriter_qos=writer_qos,
    datareader_qos=reader_qos,
)

# 4. Polling loop
while True:
    requests = replier.receive_requests(max_wait=dds.Duration(1))
    for req, info in requests:
        result = my_business_logic(req["x"], req["y"])
        reply = dds.DynamicData(rep_type)
        reply["result"] = result
        replier.send_reply(reply, info)
```

This is roughly 25–30 lines for the simplest possible case. A full service with discovery advertisement, QoS tuning, and error handling reaches 80+ lines before any domain logic is written.

The Python API currently has **no decorator-based helpers**. There is no mechanism to declare a DataReader, DataWriter, or RPC endpoint from a function signature.

### Proposal

We propose three new Python decorators for the `rti.connextdds` package:

| Decorator | Purpose |
|---|---|
| `@rti.rpc` | Expose a function as a DDS RPC endpoint (request/reply) |
| `@rti.writer` | Publish a function's return value to a DDS topic on a schedule |
| `@rti.reader` | Subscribe to a DDS topic and handle incoming data |

Each decorator:
- infers the DDS type from Python type hints (or accepts an explicit type name / Pydantic model)
- manages all DDS entity lifecycle internally
- lets the developer write only the function body

---

### `@rti.rpc`: Remote Procedure Call

#### Concept

Annotating a method with `@rti.rpc` automatically creates the `rti.rpc.Replier` infrastructure needed to make that method callable from any other Connext application on the network.

#### Proposed Syntax

```python
import rti.connextdds as dds

class CalculatorService(dds.Service):

    @rti.rpc(service_name="calculator/add")
    def add(self, x: float, y: float) -> float:
        return x + y

    @rti.rpc(service_name="calculator/stats", qos_profile="MyLib::HighReliability")
    def get_statistics(self, window_seconds: int) -> dict:
        return {"mean": ..., "stddev": ..., "count": ...}

service = CalculatorService(domain_id=0)
service.run()  # blocks, dispatches incoming RPC calls
```

#### What the decorator does internally

1. Inspects the function signature via `inspect` + `typing` to infer request/reply field names and types
2. Dynamically constructs the DDS type definitions (equivalent to what today requires an XML file)
3. Creates `rpc.Replier` with sensible default QoS (reliable, volatile, with override via `qos_profile=`)
4. Wraps the function body in a dispatch loop: receive → unpack fields → call → pack reply → send
5. Registers the endpoint for lifecycle management by `dds.Service.run()`

#### Calling from another application (no change to caller API)

The caller continues to use the existing `rti.rpc.Requester` API, or a symmetric `@rti.rpc_client` helper (future work):

```python
requester = rpc.Requester(
    request_type=..., reply_type=...,
    participant=participant,
    service_name="calculator/add"
)
req = dds.DynamicData(req_type)
req["x"] = 3.0
req["y"] = 4.0
id = requester.send_request(req)
requester.wait_for_replies(dds.Duration(5), related_request_id=id)
reply = requester.take_replies(related_request_id=id)[0].data
print(reply["return"])  # 7.0
```

#### Supported type mappings

| Python type | DDS field type |
|---|---|
| `int` | `int32` |
| `float` | `float64` |
| `str` | `string<256>` |
| `bool` | `boolean` |
| `list[T]` | `sequence<T>` |
| `dict` | `string<4096>` (JSON-serialized) |
| Pydantic `BaseModel` | Struct with matching fields |

---

### `@rti.writer`: Periodic Data Publishing

#### Concept

Annotating a method with `@rti.writer` turns it into a **periodic publisher**. The method is called at a fixed frequency; its return value (a `dict` or Pydantic model) is automatically mapped to `DynamicData` and written to a DDS topic.

#### Proposed Syntax

```python
class SensorNode(dds.Node):

    @rti.writer(topic="sensors/temperature", frequency_hz=10.0)
    def publish_temperature(self) -> dict:
        return {
            "sensor_id": self.sensor_id,
            "value_celsius": self.read_sensor(),
            "timestamp_ns": time.time_ns(),
        }

    @rti.writer(
        topic="sensors/imu",
        frequency_hz=100.0,
        qos_profile="SensorLib::HighThroughput",
        type_name="ImuSample",   # explicit DDS type name if desired
    )
    def publish_imu(self) -> ImuSample:  # Pydantic model
        return ImuSample(ax=..., ay=..., az=..., gx=..., gy=..., gz=...)

node = SensorNode(domain_id=0)
node.run()
```

#### Behavior

- The return value **must** be a `dict` or a Pydantic `BaseModel`. Any other return type is a configuration error raised at startup, not at runtime.
- The `dict` keys become DDS struct field names; values are type-inferred.
- `frequency_hz` controls a `dds.Duration`-based periodic timer internally.
- If `frequency_hz` is omitted, the writer is **on-demand**: calling `self.publish_temperature()` directly triggers a single write (useful for event-driven publishing).
- QoS defaults to `RELIABLE` / `KEEP_LAST 1` unless overridden via `qos_profile=`.

#### Example: on-demand variant

```python
@rti.writer(topic="alerts/collision_warning")
def publish_alert(self, severity: int, message: str) -> dict:
    return {"severity": severity, "message": message, "source": self.node_name}

# called explicitly in response to an event
self.publish_alert(severity=2, message="obstacle detected")
```

---

### `@rti.reader`: Data Subscription

#### Concept

Annotating a method with `@rti.reader` subscribes to a DDS topic and **calls the method for every sample received**. The framework handles DataReader creation, listener setup, and data unpacking.

#### Proposed Syntax

##### Callback form (recommended)

```python
class Dashboard(dds.Node):

    @rti.reader(topic="sensors/temperature")
    def on_temperature(self, sample: dict, info: dds.SampleInfo):
        print(f"[{info.source_timestamp}] temp = {sample['value_celsius']:.1f} °C")

    @rti.reader(topic="sensors/imu", type_name="ImuSample")
    def on_imu(self, sample: ImuSample, info: dds.SampleInfo):
        self.update_attitude(sample.ax, sample.ay, sample.az)
```

The method is invoked on every `on_data_available` event. `sample` is either a `dict` or a Pydantic model (matching the type annotation), automatically unpacked from `DynamicData`.

##### Print-to-screen form (zero handler code)

If no method body is needed (for quick debugging or monitoring), the decorator can be applied to a bare `...` stub:

```python
@rti.reader(topic="sensors/temperature", print_fields=["sensor_id", "value_celsius"])
def monitor_temperature(self, sample, info): ...
```

This spawns a background thread that prints the specified fields at every update. `print_fields` defaults to all fields if omitted.

##### Frequency-decimated form

```python
@rti.reader(topic="sensors/imu", max_callback_hz=10.0)
def on_imu_decimated(self, sample: dict, info: dds.SampleInfo):
    # called at most 10 times/sec regardless of publish rate
    self.update_ui(sample)
```

#### Content filtering

```python
@rti.reader(
    topic="sensors/temperature",
    filter="value_celsius > %0",
    filter_params=["50.0"],
)
def on_overheat(self, sample: dict, info: dds.SampleInfo):
    self.trigger_alarm(sample["sensor_id"])
```

---

### Putting It All Together

A complete bidirectional service + monitoring node in ~30 lines:

```python
import rti.connextdds as dds
import rti

class RobotArmService(dds.Service):

    def __init__(self):
        super().__init__(domain_id=0, name="RobotArmService")
        self.joint_angles = [0.0] * 6

    @rti.rpc(service_name="robot_arm/move_to")
    def move_to(self, angles: list[float], speed: float) -> dict:
        self.joint_angles = angles
        return {"success": True, "eta_ms": len(angles) * speed * 10}

    @rti.writer(topic="robot/joint_state", frequency_hz=50.0)
    def publish_state(self) -> dict:
        return {"angles": self.joint_angles, "timestamp_ns": time.time_ns()}

    @rti.reader(topic="robot/emergency_stop")
    def on_estop(self, sample: dict, info: dds.SampleInfo):
        self.joint_angles = [0.0] * 6
        self.log.warning("E-stop received, joints zeroed")

service = RobotArmService()
service.run()
```

Without decorators, the equivalent code is approximately 120–150 lines of DDS plumbing.

---

### Design Principles

#### 1. Zero XML required
Types are inferred from Python signatures. XML overrides remain available for interop with existing IDL-defined types (`type_name="MyExistingType"`).

#### 2. Opt-in, not all-or-nothing
Decorators compose freely with handwritten DDS code. A developer can use `@rti.rpc` on new endpoints while keeping existing `rti.rpc.Replier` code unchanged.

#### 3. No new abstractions for the caller
Only the **service/publisher side** gains new decorator syntax. The requester, subscriber, and discovery APIs stay unchanged. Interoperability with C++, Java, and non-decorated Python applications is preserved.

#### 4. Explicit over magic
Configuration lives in the decorator arguments (topic name, QoS profile, frequency), not hidden in framework internals. A developer can always inspect exactly what DDS entities were created.

#### 5. Event-driven, not polling
All readers use `on_data_available` listeners internally. No polling loops are introduced.

---

### Open Questions

1. **Type inference depth**: How far should automatic DDS type generation go? Nested Pydantic models? Enums? Union types? A conservative first version could support flat structs only.
2. **QoS defaults**: What QoS profile should be the default for each decorator? RELIABLE/KEEP_LAST_1 is safe but may not match user expectations for high-throughput sensors.
3. **Async support**: Should callback methods support `async def`? This requires an event loop integration strategy.
4. **Discovery / advertisement**: Should `@rti.rpc` also advertise the endpoint on a well-known topic so other applications can discover available services at runtime (as GENESIS does)?
5. **Code generation vs. runtime inference**: Should the decorator generate a `.py` stub file (inspectable, IDE-friendly) or build the DDS entities purely at runtime (simpler, but harder to debug)?

---

### Relationship to GENESIS

The decorators proposed here are intentionally **provider-agnostic and AI-free**. GENESIS's `@genesis_function` and `@genesis_tool` were designed for LLM tool-calling and include JSON Schema generation, function classification, and agent routing. Those concerns belong in the AI layer.

What we are proposing is the **DDS plumbing layer** that GENESIS proved was viable: the insight that Python type hints carry enough information to auto-generate DDS entities. The AI features of GENESIS would then compose on top of these decorators in a future integration.

---

*This proposal is based on patterns validated in the GENESIS prototype. Implementation effort for Suggestion 1 is estimated at 2–3 engineer-weeks for a v1 covering flat struct types, the three core decorators, and the `dds.Service`/`dds.Node` base classes.*

---

## Suggestion 2: LLM-Driven DDS Interaction via MCP

### Concept

GENESIS embedded an LLM inside the framework to discover and invoke DDS endpoints. This tight coupling has a cost: every deployment must manage an LLM provider, API keys, and model selection as part of the DDS application itself.

This suggestion inverts the relationship. Instead of the framework owning the LLM, we expose DDS endpoints **to whatever LLM the developer is already using** (Claude Code, GitHub Copilot, or any other MCP-capable assistant) through a standard bridge layer.

The bridge is a **Connext MCP Server**: a lightweight process that connects to a DDS domain, discovers all live RPC endpoints, DataReaders, and DataWriters, and surfaces them as MCP tools. The LLM harness connects to the MCP server and can then discover, inspect, and interact with the DDS network through natural language, with no knowledge of DDS required.

### How It Works

```
┌─────────────────────────────────────────────────────┐
│  Developer's IDE (VS Code / Connext Studio)         │
│                                                     │
│   ┌─────────────────┐       ┌──────────────────┐   │
│   │  LLM Harness    │◄─────►│ Connext MCP      │   │
│   │  (Claude Code / │  MCP  │ Server           │   │
│   │   Copilot / ...) │       │                  │   │
│   └─────────────────┘       └────────┬─────────┘   │
│                                       │ DDS         │
└───────────────────────────────────────┼─────────────┘
                                        │
              ┌─────────────────────────▼──────────────────────┐
              │  DDS Domain                                     │
              │                                                 │
              │  [RPC: calculator/add]  [Writer: sensors/imu]  │
              │  [RPC: robot_arm/move]  [Reader: alerts/estop]  │
              └─────────────────────────────────────────────────┘
```

**Step 1: Discovery.** The MCP server subscribes to the DDS discovery topic (the same `Advertisement` topic used by GENESIS). As endpoints come online or go offline, the server dynamically registers or removes the corresponding MCP tools.

**Step 2: Tool registration.** Each discovered endpoint becomes an MCP tool:
- An RPC endpoint becomes a callable tool with input/output schema derived from the DDS type
- A DataWriter becomes a tool that publishes a sample to the topic
- A DataReader becomes a tool that reads the latest sample(s) from the topic

**Step 3: LLM interaction.** The developer asks the assistant a question in natural language:

> *"What services are available on domain 0?"*  
> *"Call calculator/add with x=3 and y=4"*  
> *"What is the current value on sensors/temperature?"*  
> *"Send an emergency stop to robot/estop"*

The LLM resolves the intent, selects the appropriate MCP tool, and executes the DDS call. Results are returned as structured data and summarized in natural language.

### What GENESIS Proved

GENESIS validated the core of this idea: that DDS endpoint metadata (name, parameter types, description) is sufficient for an LLM to correctly route and invoke calls, even across a large number of live endpoints. Its `FunctionClassifier` reduced hundreds of discovered functions to a relevant subset before presenting them to the LLM, a technique that would carry over directly to the MCP server's tool list management.

The key difference is that in GENESIS the LLM was a first-class citizen of the framework. Here it is an **optional, external consumer**: the DDS network operates identically whether or not an LLM is connected.

### Relationship to Connext Studio

The MCP server could be delivered as:
- A **standalone process** that any MCP-capable client can connect to
- A **Connext Studio plugin** that surfaces the MCP server and a chat interface within the IDE
- Both, with the plugin being a thin wrapper around the standalone server

In the Connext Studio context, the developer would have a live view of the DDS network topology alongside a chat panel, essentially the same experience as GENESIS's `GraphInterface` example, but powered by whatever LLM the developer already has access to.

### Open Questions

1. **Deployment form**: Should this be a standalone MCP server process, a VS Code extension, a Connext Studio plugin, or all three? Each has different distribution and maintenance implications.

2. **Scope of interaction**: Should the MCP server be read-only (inspect topology, read samples, call RPC) or also allow writing to arbitrary topics? Write access raises safety concerns in production environments.

3. **Type presentation to the LLM**: Should DDS types be surfaced as raw IDL/XML schemas, as JSON Schema (as GENESIS did), or as natural-language descriptions? The choice affects how well the LLM can reason about parameters.

4. **Authentication and domain isolation**: In multi-domain or secured DDS deployments, how does the MCP server authenticate and scope its discovery? Should it support RTI Security Plugins?

5. **Dynamic vs. static tool list**: MCP clients may not handle a dynamically changing tool list well. Should the server snapshot the tool list at connection time, or support live updates as endpoints come and go?

6. **Function classifier**: GENESIS used an LLM pre-filter to avoid overwhelming the model with hundreds of tools. Should the MCP server implement a similar relevance filter, or rely on the host LLM's tool selection capabilities?

7. **Connext Studio vs. IDE-agnostic**: Tight integration with Connext Studio provides a richer experience (topology graph, type browser) but limits reach. A standalone MCP server works with any IDE. These are not mutually exclusive. Is there a phased approach?

### Relationship to GENESIS

GENESIS embedded discovery, classification, and LLM invocation in a single Python process. This suggestion extracts only the **discovery and invocation layer** into a reusable, LLM-agnostic server. The classification logic (GENESIS's `FunctionClassifier` and `AgentClassifier`) either moves into the MCP server as an optional semantic filter, or is left entirely to the host LLM.

The result is that a Connext developer gets LLM-assisted DDS interaction without adopting any AI framework; they just point their existing assistant at the MCP server.

---

## Suggestion 3: Agent Enablement for Existing DDS Applications

### Concept

GENESIS requires developers to build agents from scratch by subclassing `GenesisAgent`. This is the right approach for new applications, but it leaves the large installed base of existing Connext applications untouched.

This suggestion proposes a way to **retrofit any existing DDS application with agent capabilities**, without modifying its architecture, rewriting its communication layer, or adopting a new framework. The developer opts in with a single call, and the application immediately gains a conversational interface.

### The Core Idea

Given an existing DDS `DomainParticipant`, the framework inspects what it already owns (its DataReaders, DataWriters, and RPC endpoints) and uses that as the agent's toolset. No manual tool registration required.

```python
import rti.agent as agent

# Existing application (unchanged)
participant = dds.DomainParticipant(domain_id=0)
my_writer = dds.DataWriter(participant, my_topic)
my_reader = dds.DataReader(participant, my_topic)
# ... rest of existing app setup ...

# One line to enable agent capabilities
a = agent.enable(participant, llm="nemotron")

# Now the application can be queried in natural language
response = a.ask("What is the current temperature on sensors/temperature?")
response = a.ask("Publish a new joint state with angles [0, 45, 90, 0, 0, 0]")
```

The `enable()` call:
1. Introspects the participant's existing entities to build the agent's tool inventory
2. Connects an LLM backend (local or cloud)
3. Exposes the `ask()` API in three ways simultaneously (see below)

### Three Ways to Reach the Agent

Once enabled, the agent is reachable through any combination of the following interfaces, all active at the same time, all backed by the same LLM and the same tool inventory:

#### 1. Direct Python API

```python
response = a.ask("What services are running on this participant?")
print(response.text)
```

Suitable for programmatic use: integration tests, CLI wrappers, scripted interactions.

#### 2. MCP Server

The agent exposes itself as an MCP server, making it immediately available to Claude Code, GitHub Copilot, or any MCP-capable IDE. The developer's assistant can then interact with the running application directly from the editor:

> *"Ask the robot arm application to move to the home position."*  
> *"What is the application currently publishing on the joint state topic?"*

#### 3. DDS Request/Reply

The agent listens on a well-known RPC topic (`rti/connext/agent/{participant_name}/ask`). Any other application on the DDS domain, regardless of language or platform, can send a natural-language string and receive a structured reply. This makes agent interaction a first-class DDS operation, consistent with the rest of the system.

```
[Any DDS App] ──RPC request: "What is the robot's current state?"──► [Agent-enabled Participant]
              ◄──RPC reply: "Joint angles are [0, 45, 90, ...], published 12ms ago"──
```

### LLM Configuration

The LLM backend is selected at `enable()` time and can be changed at runtime. The framework ships with built-in support for:

| Provider | How | Notes |
|---|---|---|
| **Nemotron** (NVIDIA) | Local via Ollama | No API key, no network egress, air-gap friendly |
| **OpenAI** | Cloud API | GPT-4o and variants |
| **Anthropic** | Cloud API | Claude Sonnet / Opus |
| **Any OpenAI-compatible endpoint** | Cloud or local | Custom deployments, vLLM, LM Studio |

**Nemotron is the recommended default for production environments** where data sovereignty, air-gap operation, or latency requirements make cloud LLMs impractical, which describes the majority of RTI's target verticals (defense, medical, industrial). This also positions RTI as a natural partner for NVIDIA in the agentic AI space.

```python
# Local inference (no API key, no egress)
a = agent.enable(participant, llm="nemotron")

# Cloud fallback
a = agent.enable(participant, llm="openai", model="gpt-4o")

# Switch at runtime
a.set_llm("nemotron")
```

### What the Agent Can Do

The agent's capabilities are bounded by what the participant already owns:

| Participant entity | Agent capability |
|---|---|
| DataWriter | Publish samples described in natural language |
| DataReader | Read and summarize the latest samples |
| RPC Replier (`@rti.rpc`) | Answer questions by invoking its own functions |
| RPC Requester | Call remote services on behalf of a user request |
| Any combination | Multi-step reasoning across all of the above |

The agent does not gain access to anything outside the participant's existing entity set. It cannot read topics the participant is not already subscribed to, and cannot publish to topics the participant does not own a writer for. **The DDS security boundary is preserved.**

### Relationship to GENESIS

GENESIS agents were purpose-built: they inherited from `GenesisAgent`, registered tools explicitly, and were designed to be agents from the start. This suggestion targets the **retrofit case**: an application that was built as a DDS node and should stay that way, but gains conversational capabilities as an add-on.

The two approaches are complementary. A GENESIS agent built with `OpenAIGenesisAgent` and a legacy DDS node upgraded with `agent.enable()` are both first-class participants on the same domain, and either can call the other's endpoints.

### Open Questions

1. **Introspection depth**: How much can be inferred automatically from a participant's existing entities? DDS built-in discovery provides topic names and type names, but not semantic descriptions. Should the developer be required to annotate entities with descriptions, or should the LLM attempt to infer intent from names alone?

2. **Safety and write access**: Allowing the LLM to publish arbitrary samples on behalf of a user is powerful but potentially dangerous in safety-critical systems. Should write operations require explicit opt-in, a confirmation step, or be disabled by default?

3. **Statefulness**: Should the agent maintain a conversation history (as GENESIS's `SimpleMemoryAdapter` does), or be stateless per `ask()` call? Statefulness enables multi-turn interactions but adds memory management complexity.

4. **Multi-participant support**: Should `agent.enable()` be scoped to a single participant, or should it be able to aggregate across multiple participants in the same process?

5. **Nemotron model selection**: Which Nemotron variant is the right default? The tradeoff is capability vs. hardware requirements. A recommended minimum spec should be documented.

6. **NVIDIA partnership scope**: Beyond Nemotron as a default LLM, are there deeper integration opportunities, e.g., running agent inference on NVIDIA Jetson devices co-located with DDS edge nodes, or using NVIDIA NIM microservices as the inference backend?

---

## Suggestion 4: Peer-to-Peer Agent Discovery and Delegation

### Concept

Suggestion 3 gives a single participant a conversational interface over its own entities. This suggestion extends that to the **whole DDS network**: agent-enabled participants advertise their capabilities on a shared discovery topic, and any other agent-enabled participant can discover and invoke them as remote tools, automatically, with no manual configuration.

The result is a self-organizing network of agents where skills and tools are globally accessible to any participant that asks for them. An agent handling a request it cannot answer locally can discover a peer that can, delegate the sub-task, and incorporate the result, all transparently, all over DDS.

### How It Works

#### Advertisement

When `agent.enable()` is called, the participant begins publishing its capabilities to a well-known durable DDS topic: `rti/connext/agent/Advertisement`. Each advertisement record contains:

- Participant name and GUID
- A list of exposed tools/skills (name, description, parameter schema)
- The agent's `ask` RPC endpoint name (for natural-language delegation)
- LLM backend in use (informational)

This is a **passive, always-on broadcast**: no handshake required. Any participant that joins the domain later will receive the full set of current advertisements via DDS durability.

#### Discovery

Every agent-enabled participant subscribes to `rti/connext/agent/Advertisement` and maintains a live registry of peer agents and their capabilities. The registry updates automatically as participants join or leave the domain.

```python
a = agent.enable(participant, llm="nemotron")

# See what peers are available right now
peers = a.peers()
# [AgentPeer(name="RobotArmService", tools=["move_to", "get_joint_state", ...]),
#  AgentPeer(name="SensorHub",       tools=["read_temperature", "read_imu", ...]),
#  AgentPeer(name="MissionPlanner",  tools=["plan_route", "abort_mission",  ...])]
```

#### Delegation

When an agent receives a request it cannot satisfy with its local tools alone, it queries the peer registry and delegates to the best-matching remote agent via the DDS `ask` RPC endpoint established in Suggestion 3.

```
User ──ask()──► RobotController agent
                  │  "move to waypoint Alpha and report temperature"
                  │
                  ├──delegate──► MissionPlanner agent
                  │              (resolves waypoint coordinates)
                  │
                  └──delegate──► SensorHub agent
                                 (reads current temperature)
                  │
                  ◄── combined result returned to user
```

From the user's perspective this is a single `ask()` call. The delegation chain happens entirely over DDS, using the same request/reply infrastructure already present in the system.

#### Zero Configuration

No routing tables, no service registry, no central coordinator. The network topology emerges from DDS discovery alone. Adding a new agent-enabled participant to the domain immediately makes its tools available to all existing agents, and it immediately learns about all of theirs.

```python
# Node A (already running)
a = agent.enable(participant_A, llm="nemotron")

# Node B (joins later, immediately visible to A and vice versa)
b = agent.enable(participant_B, llm="openai")

# A can now delegate to B's tools without any reconfiguration
response = a.ask("Do something that requires B's capabilities")
```

### Topology Visualization

Because all advertisements and delegation events flow over DDS, the live agent network can be rendered as a graph in real time, directly in Connext Studio or the standalone graph viewer from Suggestion 2. Nodes are agent-enabled participants; edges appear when one agent delegates to another.

This is the same visualization that GENESIS's `GraphMonitor` and `genesis-graph-viewer` provided, now available to any DDS application without adopting the GENESIS framework.

### Relationship to GENESIS

This suggestion is a direct generalization of two GENESIS subsystems:

- **`AdvertisementBus`**: GENESIS's per-participant singleton that publishes function and agent advertisements to a shared DDS topic. The mechanism here is identical, extended to cover all entity types (readers, writers, RPC) rather than just GENESIS-registered functions.
- **`AgentCommunicationMixin`**: GENESIS's optional mixin that gave agents the ability to discover peer agents and send them requests. Here this capability is built into `agent.enable()` rather than being opt-in.

The key difference is scope: GENESIS's peer discovery was limited to GENESIS agents. This proposal extends it to **any DDS participant** that opts in, regardless of how it was built.

### Open Questions

1. **Delegation depth and cycles**: Should agents delegate transitively (A→B→C) or only one hop? Transitive delegation is more powerful but introduces the risk of cycles and runaway chains. A maximum delegation depth (configurable, default 2–3) is one mitigation.

2. **Trust and authorization**: In a multi-organization or security-partitioned DDS deployment, should an agent be allowed to delegate to any peer it discovers, or should delegation be scoped by DDS partition, security domain, or an explicit allowlist?

3. **Peer selection strategy**: When multiple peers advertise overlapping capabilities, which one should the agent delegate to? Options include: first-match, LLM-assisted semantic ranking (as GENESIS's `AgentClassifier` did), latency-based selection, or explicit priority hints in the advertisement.

4. **Advertisement schema**: What is the minimum viable advertisement record? Richer descriptions (natural-language capability summaries) make peer selection more accurate but require more author effort. Minimal records (topic name + type) are automatic but give the LLM less to work with.

5. **Failure handling**: If a delegated peer goes offline mid-chain, should the delegating agent retry with another peer, fail the request, or return a partial result? This intersects with DDS liveliness and deadline QoS.

6. **Cross-domain federation**: DDS domains are isolated by design. Should agent discovery and delegation work across domain bridges, or be strictly scoped to a single domain?
