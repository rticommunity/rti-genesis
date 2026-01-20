# Genesis Framework - DDS Topics Reference

**Generated**: October 10, 2025  
**Framework Version**: RC1 (Post-Consolidation)

---

## Core Framework Topics (Always Present)

These topics are fundamental to the Genesis framework and exist in every deployment:

### 1. Discovery & Registration
| Topic Name | QoS | Purpose | Type |
|------------|-----|---------|------|
| `rti/connext/genesis/Advertisement` | Durable, Reliable | Unified discovery for services, functions, and agents. Replaces legacy GenesisRegistration, FunctionCapability, and AgentCapability. | Advertisement |

**Fields**:
- `kind`: `FUNCTION` (0), `AGENT` (1), or `REGISTRATION` (2)
- `entity_id`: Unique identifier
- `entity_name`: Human-readable name
- `capabilities`: JSON string with metadata
- `timestamp`: Publication time

---

### 2. Monitoring Topics
| Topic Name | QoS | Purpose | Type |
|------------|-----|---------|------|
| `rti/connext/genesis/monitoring/GraphTopology` | Durable, Reliable | Graph structure (nodes and edges). Replaces GenesisGraphNode and GenesisGraphEdge. | GraphTopology |
| `rti/connext/genesis/monitoring/Event` | Volatile, Reliable | All events (lifecycle, chain, general). Replaces ChainEvent, ComponentLifecycleEvent, and MonitoringEvent. | Event |

#### GraphTopology Fields:
- `kind`: `NODE` (0) or `EDGE` (1)
- `element_id`: Identifier (node ID or composite edge ID)
- `element_type`: Type (e.g., "Agent", "Service", "AGENT_TO_SERVICE")
- `metadata`: JSON properties
- `timestamp`: Update time

#### Event Fields:
- `kind`: `LIFECYCLE` (0), `CHAIN` (1), or `GENERAL` (2)
- `component_id`: Source component
- `component_type`: Type of component
- `event_type`: Specific event (e.g., "STARTED", "STOPPED")
- `message`: Human-readable description
- `metadata`: JSON additional data
- `timestamp`: Event time

**Content Filtering Support**: Both topics support DDS ContentFilteredTopic for efficient subscription (e.g., filter by `kind`).

---

## Dynamic RPC Topics (Created Per Service/Agent)

These topics are created dynamically when services or agents are instantiated. The naming pattern is:

- **Service RPC**: `rti/connext/genesis/{ServiceName}Request` and `rti/connext/genesis/{ServiceName}Reply`
- **Agent RPC**: `rti/connext/genesis/{AgentName}_AgentRPCRequest` and `rti/connext/genesis/{AgentName}_AgentRPCReply`

### Examples from Test Suite:

#### Service Topics:
- `rti/connext/genesis/CalculatorServiceRequest` / `CalculatorServiceReply`
- `rti/connext/genesis/LetterCounterServiceRequest` / `LetterCounterServiceReply`
- `rti/connext/genesis/TextProcessorServiceRequest` / `TextProcessorServiceReply`
- `rti/connext/genesis/MathTestServiceRequest` / `MathTestServiceReply`

#### Agent Topics:
- `rti/connext/genesis/OpenAIChat_AgentRPCRequest` / `OpenAIChat_AgentRPCReply`
- (Pattern: `{AgentName}_AgentRPCRequest` / `{AgentName}_AgentRPCReply`)

#### Function Execution:
- `rti/connext/genesis/FunctionExecutionRequest` / `FunctionExecutionReply` (used for generic function calls)

**Note**: The exact number and names of these topics depend on your deployment configuration.

---

## Topic Count Summary

| Category | Count | Notes |
|----------|-------|-------|
| **Core Framework** | **3** | Advertisement + 2 monitoring |
| **RPC Topics** | **Variable** | 2 per service/agent (request + reply) |
| **Total (Typical Deployment)** | **9-15** | Depends on # of services/agents |

### Before Consolidation (Legacy):
- **17+ topics** (8 core: 3 discovery + 5 monitoring, plus RPC topics)

### After Consolidation (Current):
- **9+ topics** (3 core: 1 discovery + 2 monitoring, plus RPC topics)
- **47% reduction** in core framework topics

---

## Topic Naming Convention

All Genesis topics follow this pattern:
```
rti/connext/genesis/{category}/{name}
```

Where:
- **Base**: `rti/connext/genesis/`
- **Category**: Optional (e.g., `monitoring/`)
- **Name**: Descriptive topic name (e.g., `Advertisement`, `Event`)

---

## QoS Profiles

### Durable Topics (TRANSIENT_LOCAL)
- `Advertisement` - Discovery data survives component restarts
- `monitoring/GraphTopology` - Graph structure persists

### Volatile Topics (VOLATILE)
- `monitoring/Event` - Transient events
- All RPC Request/Reply topics - Ephemeral communications

All topics use:
- **Reliability**: `RELIABLE`
- **History**: `KEEP_LAST` with depth appropriate to use case
- **Liveliness**: Automatic participant liveliness

---

## Migration Notes

### Removed Topics (No Longer Used):
❌ `GenesisRegistration` → ✅ `Advertisement` (kind=REGISTRATION)  
❌ `FunctionCapability` → ✅ `Advertisement` (kind=FUNCTION)  
❌ `AgentCapability` → ✅ `Advertisement` (kind=AGENT)  
❌ `GenesisGraphNode` → ✅ `monitoring/GraphTopology` (kind=NODE)  
❌ `GenesisGraphEdge` → ✅ `monitoring/GraphTopology` (kind=EDGE)  
❌ `ChainEvent` → ✅ `monitoring/Event` (kind=CHAIN)  
❌ `ComponentLifecycleEvent` → ✅ `monitoring/Event` (kind=LIFECYCLE)  
❌ `MonitoringEvent` → ✅ `monitoring/Event` (kind=GENERAL)

---

## Usage Examples

### Subscribing to All Lifecycle Events (Python):
```python
from rti import dds

# Create content filter for lifecycle events only
filter_expr = "kind = 0"  # LIFECYCLE = 0
cft = dds.DynamicData.ContentFilteredTopic(
    event_topic,
    "LifecycleEvents",
    dds.Filter(filter_expr)
)
reader = dds.DynamicData.DataReader(subscriber, cft)
```

### Subscribing to Agent Advertisements Only:
```python
filter_expr = "kind = 1"  # AGENT = 1
cft = dds.DynamicData.ContentFilteredTopic(
    advertisement_topic,
    "AgentAds",
    dds.Filter(filter_expr)
)
reader = dds.DynamicData.DataReader(subscriber, cft)
```

---

**For detailed type definitions, see**: `genesis_lib/config/datamodel.xml`  
**For external validation**: `MONITORING_CONSOLIDATION_VALIDATION.md`


---
*Copyright (c) 2025, RTI & Jason Upchurch*
