# Monitoring Topic Consolidation Plan

**Date:** October 8, 2025  
**Status:** Planning Phase  
**Goal:** Consolidate 5 monitoring topics into unified architecture

---

## 📊 Current State

### Monitoring Topics (5):

#### Durable Topics (2):
1. **`rti/connext/genesis/monitoring/GenesisGraphNode`**
   - Purpose: Persistent node state in the execution graph
   - QoS: TRANSIENT_LOCAL, RELIABLE, KEEP_ALL
   - Usage: Graph viewer subscribes to maintain topology
   - Key: Node ID

2. **`rti/connext/genesis/monitoring/GenesisGraphEdge`**
   - Purpose: Persistent edge/connection state in execution graph
   - QoS: TRANSIENT_LOCAL, RELIABLE, KEEP_ALL
   - Usage: Graph viewer subscribes to maintain relationships
   - Key: Edge ID (source-target pair)

#### Volatile Topics (3):
3. **`rti/connext/genesis/monitoring/ChainEvent`**
   - Purpose: Track execution chains and multi-hop workflows
   - QoS: VOLATILE, RELIABLE, KEEP_LAST
   - Usage: Real-time chain execution monitoring
   - Data: chain_id, hop_number, timestamps, performance metrics

4. **`rti/connext/genesis/monitoring/ComponentLifecycleEvent`**
   - Purpose: Component lifecycle state changes (ONLINE/OFFLINE/ERROR)
   - QoS: VOLATILE, RELIABLE, KEEP_LAST
   - Usage: Real-time component status tracking
   - Data: component_id, state, timestamp, reason

5. **`rti/connext/genesis/monitoring/MonitoringEvent`**
   - Purpose: General monitoring events, logs, and notifications
   - QoS: VOLATILE, RELIABLE, KEEP_LAST
   - Usage: Catch-all for monitoring data
   - Data: event_type, severity, message, metadata

---

## 🎯 Consolidation Options

### Option 1: Full Consolidation (Single Topic)
**One unified `MonitoringData` topic with event_type discriminator**

**Pros:**
- Maximum simplicity (1 topic instead of 5)
- Single subscriber for all monitoring
- Consistent QoS management

**Cons:**
- Mixed durability needs (graph state is durable, events are volatile)
- Performance: Volatile events would inherit TRANSIENT_LOCAL durability
- Semantic confusion: Mixing persistent state with ephemeral events

**Verdict:** ❌ **Not recommended** - durability requirements are fundamentally different

---

### Option 2: Split by Durability (2 Topics)
**Two topics: `MonitoringState` (durable) and `MonitoringEvent` (volatile)**

#### Topic 1: `rti/connext/genesis/monitoring/State` (DURABLE)
- **Purpose:** Persistent state (graph topology)
- **QoS:** TRANSIENT_LOCAL, RELIABLE, KEEP_ALL
- **Consolidates:**
  - GenesisGraphNode → `state_type = NODE`
  - GenesisGraphEdge → `state_type = EDGE`
- **Key:** state_id (node_id or edge_id)
- **Usage:** Late-joining viewers get full graph state

#### Topic 2: `rti/connext/genesis/monitoring/Event` (VOLATILE)
- **Purpose:** Real-time events and telemetry
- **QoS:** VOLATILE, RELIABLE, KEEP_LAST
- **Consolidates:**
  - ChainEvent → `event_type = CHAIN`
  - ComponentLifecycleEvent → `event_type = LIFECYCLE`
  - MonitoringEvent → `event_type = GENERAL`
- **No Key:** Events are fire-and-forget
- **Usage:** Real-time monitoring, logging, alerting

**Pros:**
- Reduces 5 topics to 2 (60% reduction)
- Clear separation of concerns (state vs events)
- Appropriate QoS for each category
- Maintains semantic clarity

**Cons:**
- Still requires 2 topics (not down to 1)
- Two subscribers needed for complete monitoring

**Verdict:** ✅ **SELECTED** - best balance of simplicity and correctness

**Decision:** Split by durability - durable graph topology vs volatile events

---

### Option 3: Keep Graph Topics, Consolidate Events (3 Topics)
**Keep graph state separate, merge event topics**

#### Topics:
1. `rti/connext/genesis/monitoring/GraphNode` (DURABLE)
2. `rti/connext/genesis/monitoring/GraphEdge` (DURABLE)
3. `rti/connext/genesis/monitoring/Event` (VOLATILE)
   - Consolidates: ChainEvent, ComponentLifecycleEvent, MonitoringEvent

**Pros:**
- Less disruptive change
- Graph topics remain dedicated
- Still reduces 5 → 3 (40% reduction)

**Cons:**
- Only partial consolidation
- Misses opportunity for cleaner architecture

**Verdict:** ⚠️ **Acceptable fallback** if Option 2 proves too complex

---

## 🏗️ Approved Architecture (Option 2)

### Implementation Strategy: Dual-Publish with Validation

**Approach:**
1. Create NEW topics alongside existing 5 monitoring topics
2. Dual-publish to both old and new topics
3. Use rtiddsspy to verify new topics match old topics 1:1
4. Create validation tests to ensure parity
5. Once proven, deprecate old topics
6. Remove old topics only after all tests pass with new topics

**Rationale:**
- Monitoring is complex with many moving parts
- Tests rely heavily on topic names
- Need to verify new topics work correctly before removing old ones
- Allows for gradual, safe migration

### Proposed Topic Names:

#### Option A: Descriptive Names
1. **`rti/connext/genesis/monitoring/GraphTopology`** (DURABLE)
   - Consolidates: GenesisGraphNode + GenesisGraphEdge
2. **`rti/connext/genesis/monitoring/Event`** (VOLATILE)
   - Consolidates: ChainEvent + ComponentLifecycleEvent + MonitoringEvent

#### Option B: State/Event Pattern
1. **`rti/connext/genesis/monitoring/State`** (DURABLE)
   - Consolidates: GenesisGraphNode + GenesisGraphEdge
2. **`rti/connext/genesis/monitoring/Event`** (VOLATILE)
   - Consolidates: ChainEvent + ComponentLifecycleEvent + MonitoringEvent

**Recommendation:** Option A - "GraphTopology" is more explicit about purpose

### New Unified Types:

```xml
<!-- Graph Topology (Durable) -->
<enum name="GraphElementKind">
  <enumerator name="NODE" value="0"/>
  <enumerator name="EDGE" value="1"/>
</enum>

<struct name="GraphTopology">
  <member name="element_id" type="string" key="true" stringMaxLength="256"/>
  <member name="kind" type="nonBasic" nonBasicTypeName="GraphElementKind"/>
  <member name="timestamp" type="int64"/>
  <member name="component_name" type="string" stringMaxLength="256"/>
  <member name="component_type" type="string" stringMaxLength="128"/>
  <member name="state" type="string" stringMaxLength="64"/>
  <!-- JSON payload for extensibility -->
  <member name="metadata" type="string" stringMaxLength="8192"/>
  <!-- Node-specific: when kind=NODE, metadata contains node info -->
  <!-- Edge-specific: when kind=EDGE, metadata contains source/target info -->
</struct>

<!-- Monitoring Event (Volatile) -->
<enum name="EventKind">
  <enumerator name="CHAIN" value="0"/>
  <enumerator name="LIFECYCLE" value="1"/>
  <enumerator name="GENERAL" value="2"/>
</enum>

<struct name="MonitoringEventUnified">
  <member name="event_id" type="string" stringMaxLength="128"/>
  <member name="kind" type="nonBasic" nonBasicTypeName="EventKind"/>
  <member name="timestamp" type="int64"/>
  <member name="component_id" type="string" stringMaxLength="256"/>
  <member name="severity" type="string" stringMaxLength="32"/>
  <member name="message" type="string" stringMaxLength="2048"/>
  <!-- JSON payload for event-specific data -->
  <member name="payload" type="string" stringMaxLength="8192"/>
  <!-- Chain: chain_id, hop_number, latency in payload -->
  <!-- Lifecycle: state, reason in payload -->
  <!-- General: arbitrary event data in payload -->
</struct>
```

**🔑 CRITICAL FEATURE: Content Filtering**

Both unified types have a `kind` discriminator field that enables efficient **DDS ContentFilteredTopic** filtering:

- **GraphTopology**: Filter by `kind` to get only NODEs (0) or only EDGEs (1)
- **MonitoringEventUnified**: Filter by `kind` to get only CHAIN (0), LIFECYCLE (1), or GENERAL (2) events

This allows subscribers to filter at the DDS middleware level, dramatically reducing:
- Network traffic (filtered before transmission)
- CPU usage (no deserialization of unwanted events)
- Memory usage (no storage of irrelevant data)

**Example:** Graph viewer only needs topology (no events), activity overlay only needs CHAIN events (no lifecycle/general).

See `MONITORING_CONTENT_FILTERING.md` for complete examples and implementation patterns.

---

## 📦 Testing Infrastructure (Pulled from Main)

**Status:** ✅ Pulled `examples/` and `feature_development/` from `main` branch

### Why These Are Critical
The monitoring consolidation will break anything that subscribes to the old 5 topics. The examples use the full visualization stack (GraphService → Socket.IO → Web UI), making them perfect integration tests.

### Key Test Assets

#### 1. `examples/GraphInterface/` 
**What it is:** Chat interface with embedded graph viewer  
**Why it matters:** Tests the complete stack with real agent communication  
**Uses:**
- `GraphService` (subscribes to monitoring topics)
- `register_graph_viewer()` (mounts Socket.IO bridge + viewer)
- `MonitoredInterface` (publishes monitoring events)
- Web UI with orbital viewer

**Files:**
- `server.py` - Flask app with graph viewer
- `run_graph_interface.sh` - Launch script
- `templates/index.html` - UI with graph pane

#### 2. `feature_development/interface_abstraction/viewer/`
**What it is:** Large network stress test with graph visualization  
**Why it matters:** Tests scalability (10+ agents, 20+ services)  
**Uses:**
- `GraphService` (same as above)
- `register_graph_viewer()` (same as above)
- `start_topology.sh` - Spawns large network

**Files:**
- `viewer/server.py` - Flask app
- `start_topology.sh` - Network spawner
- `viewer/templates/index.html` - 3D orbital viewer

### Testing Strategy
1. **Phase 1-3:** Dual-publish implementation
2. **Phase 4:** Test examples with `GENESIS_USE_NEW_MONITORING_TOPICS=false` (should work as-is)
3. **Phase 5:** Update `GraphSubscriber` to support new topics
4. **Phase 4 (again):** Test examples with `GENESIS_USE_NEW_MONITORING_TOPICS=true`
5. **Phase 7:** Remove old topics, verify examples still work
6. **Phase 9:** Push fixed examples back to `main`

---

## 🗺️ System Architecture Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DDS LAYER (PUB/SUB)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PUBLISHERS (3 files)                    SUBSCRIBERS (2 files)     │
│  ┌──────────────────┐                    ┌─────────────────────┐  │
│  │ graph_monitoring │ ───┐               │   graph_state.py    │  │
│  │      .py         │    │               │  (GraphSubscriber)  │  │
│  │  - publish_node  │    ├──► Topics ───►│  - ComponentLife... │  │
│  │  - publish_edge  │    │               │  - GenesisGraphNode │  │
│  └──────────────────┘    │               │  - GenesisGraphEdge │  │
│                          │               │  - ChainEvent       │  │
│  ┌──────────────────┐    │               └──────────┬──────────┘  │
│  │monitored_interface    │                          │              │
│  │      .py         │ ───┤                          │              │
│  │  - ChainEvent    │    │               ┌──────────▼─────────┐   │
│  └──────────────────┘    │               │ genesis_monitoring │   │
│                          │               │       .py          │   │
│  ┌──────────────────┐    │               │  (MonitoringSub)   │   │
│  │ monitored_agent  │    │               │  - MonitoringEvent │   │
│  │      .py         │ ───┘               └────────────────────┘   │
│  │  - MonitoringEvt │                                              │
│  │  - ChainEvent    │                                              │
│  └──────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┬─┘
                                                                    │
                                                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VISUALIZATION LAYER (HTTP/WS)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐     ┌──────────────────┐                    │
│  │   GraphService   │────►│ socketio_graph   │                    │
│  │  (graph_state)   │     │     _bridge      │                    │
│  │  - subscribe()   │     │  - node_update   │                    │
│  │  - to_cytoscape()│     │  - edge_update   │                    │
│  └──────────────────┘     │  - activity      │                    │
│                           └────────┬─────────┘                     │
│                                    │                               │
│                                    ▼                               │
│  ┌──────────────────┐     ┌──────────────────┐                    │
│  │  graph_viewer.py │     │   Socket.IO      │                    │
│  │  (Flask/REST)    │     │   (WebSocket)    │                    │
│  │  /api/graph      │     └────────┬─────────┘                    │
│  └──────────────────┘              │                              │
│                                    ▼                               │
│                           ┌────────────────────┐                   │
│                           │  JS Viewers (2)    │                   │
│                           │  - orbital_viewer  │                   │
│                           │  - reference       │                   │
│                           └────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The visualization layer is fully decoupled from DDS topics through the `GraphService` abstraction. This means we only need to update `GraphSubscriber` to translate new topics → same internal events.

---

## 🗺️ Component Inventory

### Publishers (Writers)
1. **`graph_monitoring.py`** (`GraphMonitor`)
   - ✍️ ComponentLifecycleEvent (volatile)
   - ✍️ GenesisGraphNode (durable)
   - ✍️ GenesisGraphEdge (durable)
   - ✍️ MonitoringEvent (legacy, if `GENESIS_MON_LEGACY=1`)

2. **`monitored_interface.py`** (`MonitoredInterface`)
   - ✍️ ChainEvent (volatile)

3. **`monitored_agent.py`** (`MonitoredAgent`)
   - ✍️ MonitoringEvent (volatile)
   - ✍️ ChainEvent (volatile)

### Subscribers (Readers)
1. **`graph_state.py`** (`GraphSubscriber`)
   - 📖 ComponentLifecycleEvent (volatile) → graph updates
   - 📖 GenesisGraphNode (durable) → node state
   - 📖 GenesisGraphEdge (durable) → edge state
   - 📖 ChainEvent (volatile) → activity overlay

2. **`genesis_monitoring.py`** (`MonitoringSubscriber`)
   - 📖 MonitoringEvent (volatile)

### Visualization Stack
1. **`graph_state.py`** (`GraphService`)
   - In-memory graph (GenesisNetworkGraph)
   - Exports to Cytoscape JSON

2. **`socketio_graph_bridge.py`**
   - Forwards GraphService events → Socket.IO
   - Events: `node_update`, `edge_update`, `node_remove`, `edge_remove`, `activity`

3. **`graph_viewer.py`** (Flask Blueprint)
   - REST API: `/api/graph` → Cytoscape JSON
   - Static assets for viewers

4. **JavaScript Viewers**
   - `orbital_viewer.js` - 3D orbital visualization
   - `reference.js` - 2D reference viewer
   - Both consume Socket.IO events

### Impact Summary
- **3 Writers** need dual-publish logic
- **2 Readers** need migration to new topics
- **Visualization stack is agnostic** (works on GraphService events, not raw DDS)
- **Tests** rely on topic names and will need updates

---

## 📝 Implementation Plan

### Phase 1: Create New Types & Topics
- [ ] Add `GraphTopology` type to datamodel.xml
- [ ] Add `MonitoringEventUnified` type to datamodel.xml
- [ ] Define enums: `GraphElementKind` (NODE/EDGE), `EventKind` (CHAIN/LIFECYCLE/GENERAL)
- [ ] Create new topics in code (alongside existing topics)
- [ ] Verify types load correctly via DDS

### Phase 2: Implement Dual-Publishing

#### 2.1: Update Publishers
- [ ] **`graph_monitoring.py`** (`GraphMonitor._DDSWriters.__init__`)
  - [ ] Create NEW writers for GraphTopology and MonitoringEventUnified
  - [ ] Keep existing writers for old topics
  - [ ] All QoS settings must match (TRANSIENT_LOCAL for topology, VOLATILE for events)

- [ ] **`graph_monitoring.py`** (`GraphMonitor.publish_node`)
  - [ ] Publish to GenesisGraphNode (existing)
  - [ ] Publish to ComponentLifecycleEvent (existing)
  - [ ] **NEW:** Publish to GraphTopology (kind=NODE)
  - [ ] Ensure all three writes succeed

- [ ] **`graph_monitoring.py`** (`GraphMonitor.publish_edge`)
  - [ ] Publish to GenesisGraphEdge (existing)
  - [ ] Publish to ComponentLifecycleEvent (existing)
  - [ ] **NEW:** Publish to GraphTopology (kind=EDGE)
  - [ ] Ensure all three writes succeed

- [ ] **`monitored_interface.py`** (`MonitoredInterface._setup_monitoring`)
  - [ ] Keep existing ChainEvent writer
  - [ ] **NEW:** Create MonitoringEventUnified writer
  - [ ] Dual-publish ChainEvent → both topics (kind=CHAIN)

- [ ] **`monitored_agent.py`** (`MonitoredAgent._setup_monitoring`)
  - [ ] Keep existing MonitoringEvent writer
  - [ ] Keep existing ChainEvent writer
  - [ ] **NEW:** Create MonitoringEventUnified writer
  - [ ] Dual-publish to both old and new topics
  - [ ] MonitoringEvent → MonitoringEventUnified (kind=GENERAL)
  - [ ] ChainEvent → MonitoringEventUnified (kind=CHAIN)
  - [ ] ComponentLifecycleEvent → MonitoringEventUnified (kind=LIFECYCLE) if applicable

#### 2.2: Verification
- [ ] Run existing tests - all should pass (old topics still work)
- [ ] Use rtiddsspy to verify new topics receive data
- [ ] Check that dual-publishing doesn't impact performance

### Phase 3: Validation via rtiddsspy
- [ ] Create validation script using rtiddsspy
- [ ] Compare old vs new topic data for parity
- [ ] Verify:
  - [ ] Node count matches between GenesisGraphNode and GraphTopology(kind=NODE)
  - [ ] Edge count matches between GenesisGraphEdge and GraphTopology(kind=EDGE)
  - [ ] Event counts match for each event type
  - [ ] Timestamps align
  - [ ] All fields populated correctly
- [ ] Document any discrepancies and fix

### Phase 4: Create Validation Tests

#### 4.1: Automated Parity Tests
- [ ] **Test: `test_monitoring_topology_parity.py`**
  - [ ] Subscribe to old graph topics
  - [ ] Subscribe to new GraphTopology topic
  - [ ] Verify 1:1 correspondence
  - [ ] Verify late joiner gets full topology from TRANSIENT_LOCAL
  
- [ ] **Test: `test_monitoring_event_parity.py`**
  - [ ] Subscribe to old event topics
  - [ ] Subscribe to new MonitoringEventUnified topic
  - [ ] Verify all events appear in new topic
  - [ ] Verify kind discriminator is correct
  
- [ ] Add to test suite (`tests/active/`)

#### 4.2: Integration Tests with Examples
**These examples use the full visualization stack and will validate end-to-end:**

- [ ] **`examples/GraphInterface/`** (Chat interface with graph viewer)
  - [ ] Test with old topics (`GENESIS_USE_NEW_MONITORING_TOPICS=false`)
  - [ ] Test with new topics (`GENESIS_USE_NEW_MONITORING_TOPICS=true`)
  - [ ] Verify graph visualization works identically
  - [ ] Verify agent discovery and chat still work
  - [ ] File: `examples/GraphInterface/server.py` (uses GraphService + register_graph_viewer)
  
- [ ] **`feature_development/interface_abstraction/viewer/`** (Large network stress test)
  - [ ] Test with old topics
  - [ ] Test with new topics
  - [ ] Verify can handle 10+ agents, 20+ services (per README example)
  - [ ] Verify orbital viewer renders correctly
  - [ ] File: `feature_development/interface_abstraction/viewer/server.py`
  - [ ] Script: `feature_development/interface_abstraction/start_topology.sh`

#### 4.3: Document Example Fixes
- [ ] Create `EXAMPLES_MIGRATION.md` documenting any changes needed
- [ ] Update example READMEs if env vars change
- [ ] Ensure examples work on both `rc1` and eventually `main`

### Phase 5: Update Subscribers

#### 5.1: Update `graph_state.py` (`GraphSubscriber`)
**Critical:** This is the core subscriber that feeds the visualization stack

- [ ] Add command-line or env var flag: `GENESIS_USE_NEW_MONITORING_TOPICS` (default: `false`)
- [ ] **When flag=false (old topics):**
  - [ ] Subscribe to ComponentLifecycleEvent (volatile) ✅ current
  - [ ] Subscribe to GenesisGraphNode (durable) ✅ current
  - [ ] Subscribe to GenesisGraphEdge (durable) ✅ current
  - [ ] Subscribe to ChainEvent (volatile) ✅ current

- [ ] **When flag=true (new topics):**
  - [ ] Subscribe to GraphTopology (durable) **NEW**
  - [ ] Subscribe to MonitoringEventUnified (volatile) **NEW**
  - [ ] Filter by `kind` field to route events correctly
  - [ ] Map GraphTopology → node_update/edge_update events
  - [ ] Map MonitoringEventUnified(kind=LIFECYCLE) → node state changes
  - [ ] Map MonitoringEventUnified(kind=CHAIN) → activity events

- [ ] Verify internal `GenesisNetworkGraph` receives identical updates from both paths
- [ ] Verify late-joiner scenario works with new durable GraphTopology topic

#### 5.2: Update `genesis_monitoring.py` (`MonitoringSubscriber`)
**Lower priority:** This is for standalone monitoring, not critical for visualization

- [ ] Add flag to switch between MonitoringEvent and MonitoringEventUnified
- [ ] Update listener to handle unified event structure
- [ ] Filter by `kind` field if needed

#### 5.3: Visualization Stack Changes
**Good news:** No changes needed! 🎉

- [ ] **`graph_state.py` (`GraphService`)** - No changes, already event-driven
- [ ] **`socketio_graph_bridge.py`** - No changes, consumes GraphService events
- [ ] **`graph_viewer.py`** - No changes, serves GraphService data
- [ ] **`orbital_viewer.js`** - No changes, consumes Socket.IO events
- [ ] **`reference.js`** - No changes, consumes Socket.IO events
- [ ] **`viewer_topology.schema.json`** - No changes, schema is stable

**Rationale:** The visualization stack is decoupled from DDS. It only sees high-level events from `GraphService` (`node_update`, `edge_update`, `activity`), so as long as `GraphSubscriber` correctly translates the new topics into these events, the entire visualization stack works unchanged.

### Phase 6: Switch Tests to New Topics
- [ ] Update test scripts to expect new topic names
- [ ] Update monitoring test expectations
- [ ] Verify all tests pass with new topics
- [ ] Keep old topic code but mark as deprecated

### Phase 7: Remove Legacy Topics
- [ ] Stop publishing to old topics
- [ ] Remove old topic creation code
- [ ] Remove old type definitions from datamodel.xml
- [ ] Remove backward compatibility code
- [ ] Update all documentation

### Phase 8: Final Validation & Documentation
- [ ] Run full test suite (`run_all_tests.sh`)
- [ ] Verify monitoring dashboard works
- [ ] Test both examples work with new topics:
  - [ ] `examples/GraphInterface/run_graph_interface.sh`
  - [ ] `feature_development/interface_abstraction/viewer/server.py`
- [ ] Update architecture diagrams
- [ ] Update README.md
- [ ] Create migration notes (`MONITORING_MIGRATION.md`)
- [ ] Document QoS settings
- [ ] Create `EXAMPLES_MIGRATION.md` if examples needed changes

### Phase 9: Merge and Sync Examples to Main
**Note:** Examples will eventually move to a separate repository, but for now they live here.

- [ ] Merge `topic-consolidation` → `rc1` (library changes)
- [ ] Cherry-pick or merge example fixes back to `main` branch
- [ ] Verify examples work on `main` with the library changes
- [ ] Tag release candidate (e.g., `v1.0.0-rc1`)
- [ ] Document breaking changes for any external users

---

## 🚨 Considerations

### 1. Breaking Change Impact
- **Graph viewer** will need updates
- **Monitoring dashboard** will need updates
- **Any external monitoring tools** will break

### 2. Migration Strategy
- Can we do dual-publish for a transition period?
- Do we need version detection?
- Timeline for deprecation?

### 3. Performance Impact
- Consolidation should improve performance (fewer topics)
- Need to verify no QoS conflicts
- Test with high event rates

### 4. Backward Compatibility
- **For first release:** NO backward compatibility needed
- Can make breaking changes freely
- Clean slate approach

### 5. DDS Configuration for Large Topologies (macOS)
- **CRITICAL:** Testing with 20+ participants requires `USER_QOS_PROFILES.xml`
- **Issue:** Default DDS exhausts participant indexes on macOS (fails after 2-5 services)
- **Error:** `ERROR: No index available for participant`
- **Solution:** Use provided `USER_QOS_PROFILES.xml` (UDP4 discovery, expanded index range)
- **Usage:** Run from `Genesis_LIB/` directory (DDS auto-loads config)
- **Details:** See `DDS_CONFIGURATION.md` for full documentation
- **Impact:** Enables testing of consolidation with realistic large-scale topologies

---

## 📊 Expected Benefits

### Topic Reduction:
- **Before:** 5 monitoring topics
- **After:** 2 monitoring topics
- **Reduction:** 60% (3 topics eliminated)

### Architecture Benefits:
- Clearer separation: state vs events
- Simpler subscription model
- Reduced DDS overhead
- Easier to add new monitoring data (just add to enum)

### Development Benefits:
- Single place to add new state types
- Single place to add new event types
- Consistent patterns for monitoring
- Easier testing

---

## ✅ Decisions Made

1. **Approach:** Option 2 - Split by durability (2 topics)
2. **Strategy:** Dual-publish with validation before deprecation
3. **Topic Names:** 
   - `rti/connext/genesis/monitoring/GraphTopology` (durable)
   - `rti/connext/genesis/monitoring/Event` (volatile)
4. **Validation:** Use rtiddsspy to verify 1:1 parity with old topics
5. **Testing:** Create new validation tests for parity checking
6. **Timeline:** After advertisement consolidation stabilizes in production
7. **Visualization Stack:** No changes needed - already decoupled via GraphService abstraction

## ❓ Remaining Questions

1. **Topic name final decision:**
   - `GraphTopology` vs `State` for durable topic? (Leaning toward GraphTopology)
   - `Event` vs `MonitoringEventUnified` for volatile topic? (Leaning toward just "Event")

2. **Field mappings:**
   - Do all fields from ChainEvent, ComponentLifecycleEvent, and MonitoringEvent fit into unified MonitoringEventUnified?
   - Need to verify no data loss during mapping

3. **Performance:**
   - Impact of dual-publishing on latency?
   - Should we add a rate limiter for high-frequency events?

4. **Migration flag:**
   - Env var name: `GENESIS_USE_NEW_MONITORING_TOPICS`?
   - Should it be per-component or global?

5. **Backward compatibility:**
   - How long to maintain dual-publishing?
   - Deprecation timeline for old topics?

---

## 🎯 Immediate Next Steps

### Pre-Implementation Decisions Needed
1. **Finalize topic names:**
   - Confirm: `rti/connext/genesis/monitoring/GraphTopology` (durable)
   - Confirm: `rti/connext/genesis/monitoring/Event` (volatile)

2. **Field mapping verification:**
   - Create mapping document: Old fields → New unified structure
   - Ensure no data loss in translation

3. **Migration strategy:**
   - Decide on env var name: `GENESIS_USE_NEW_MONITORING_TOPICS`?
   - Should dual-publishing be always-on or optional?

### Phase 1 Implementation
1. ✅ **Decision made:** Option 2 - dual-publish with validation
2. **Create new types in datamodel.xml** (non-breaking addition)
3. **Create validation script template** for rtiddsspy comparison
4. **Update `graph_monitoring.py`** to create new writers (don't publish yet)
5. **Verify types load** and DDS participants can create topics

### Phase 2 Implementation
6. **Implement dual-publishing** in all 3 publishers
7. **Run all existing tests** - verify backward compatibility
8. **Run rtiddsspy validation** - compare old vs new topic data
9. **Create automated parity tests**

### Critical Path
**Most Important:** `GraphSubscriber` (graph_state.py) is the linchpin. It's the only component that needs to understand both old and new topics. Everything downstream (viewers, Socket.IO bridge) works unchanged.

## 📋 Validation Test Ideas

### Test 1: `test_monitoring_topology_consolidation.py`
- Start agent/service with dual-publishing enabled
- Subscribe to all 5 old topics
- Subscribe to 2 new topics
- Compare data received:
  - Node count: old GenesisGraphNode == new GraphTopology(kind=NODE)
  - Edge count: old GenesisGraphEdge == new GraphTopology(kind=EDGE)
  - Event counts for each type
- Verify late joiner gets full topology from new durable topic
- Assert 100% parity

### Test 2: `test_monitoring_event_types.sh`
- Use rtiddsspy to capture both old and new topics
- Parse output and compare:
  - Event counts by type
  - Timestamp alignment
  - Field completeness
- Generate diff report

### Test 3: Integration with existing tests
- Run existing monitoring tests with dual-publishing
- Verify old topics still work (backward compatibility)
- Verify new topics contain equivalent data
- No test should break during transition

---

## 📚 Related Documents

- `advertisement_consolidation.md` - Completed discovery topic consolidation
- `CONSOLIDATION_SUMMARY.md` - Summary of advertisement consolidation work
- `TOPICS_ANALYSIS.md` - Full topic inventory and analysis

---

**Status:** Ready for discussion and decision on approach

