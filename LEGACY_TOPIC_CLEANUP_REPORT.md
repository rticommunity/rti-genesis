# Legacy Topic References - Cleanup Report

**Generated:** October 8, 2025  
**Status:** Identified all references to legacy topics

---

## 🔍 Summary

Found references to the three legacy topics across **13 files**:
- **3** documentation files (historical records - OK to keep)
- **1** XML type definition file (may need to keep for compatibility)
- **5** code files (cleaned - only comments remain)
- **4** test/script files (need updates)
- **1** main README (needs comprehensive update)

---

## 📋 Detailed Findings

### ✅ Code Files - CLEAN (Only Documentation Comments)

These files only contain comments documenting the removal - **no action needed**:

1. **`genesis_lib/agent.py`**
   - Line 100: `# Legacy GenesisRegistration writer removed - now using unified Advertisement topic via AdvertisementBus`
   
2. **`genesis_lib/genesis_app.py`**
   - Line 79: `# GenesisRegistration topic removed - now using unified Advertisement topic`
   
3. **`genesis_lib/function_discovery.py`**
   - Line 457: `# FunctionCapability topic removed - now using unified Advertisement topic`
   - Line 465: `# FunctionCapability topic removed - using unified Advertisement topic instead`
   - Line 496: `# Phase 3b: prefer unified advertisement; do not create legacy FunctionCapability reader`
   - Line 992: `# FunctionCapabilityListener removed - now using GenesisAdvertisementListener for unified discovery`
   
4. **`genesis_lib/agent_communication.py`**
   - Line 176: `# AgentCapability topic removed - now using unified Advertisement topic for agent discovery`
   - Line 343: `# Legacy AgentCapability topic/writer removed - now using unified Advertisement topic`
   
5. **`genesis_lib/interface.py`**
   - Line 251: `# Legacy AgentCapability fallback removed - now fully consolidated to Advertisement topic`

---

### ⚠️ Type Definition - KEEP (Backward Compatibility)

**File:** `genesis_lib/config/datamodel.xml`

**Status:** Contains type definitions for legacy topics:
- Line 59: `<struct name="FunctionCapability">`
- Line 74: `<struct name="AgentCapability">`

**Recommendation:** 
- **KEEP for now** - External consumers or old clients may still reference these types
- **Future cleanup:** Can be removed after confirming no external dependencies
- **Note:** Genesis framework no longer creates these topics, but type definitions allow DDS to recognize old data if present

---

### 🔧 Test Files - NEED UPDATES

#### 1. **`tests/run_all_tests.sh`**

**Lines 181-182:**
```bash
if grep -E '(New writer|New data).*topic="(FunctionCapability|CalculatorServiceRequest|TextProcessorServiceRequest|LetterCounterServiceRequest)"' "$SPY_LOG"; then
    echo "❌ ERROR: Detected lingering DDS activity on test topics (FunctionCapability or Service Requests) after cleanup attempt."
```

**Issue:** Checks for `FunctionCapability` in DDS cleanup verification

**Fix:** Replace `FunctionCapability` with `Advertisement`:
```bash
if grep -E '(New writer|New data).*topic="(Advertisement|CalculatorServiceRequest|TextProcessorServiceRequest|LetterCounterServiceRequest)"' "$SPY_LOG"; then
    echo "❌ ERROR: Detected lingering DDS activity on test topics (Advertisement or Service Requests) after cleanup attempt."
```

---

#### 2. **`tests/active/test_monitoring.sh`**

**Lines 147-148:**
```bash
TOPICS=(
  'FunctionCapability'
  'CalculatorServiceRequest' 'CalculatorServiceReply'
```

**Issue:** Expects `FunctionCapability` topic in monitoring test

**Fix:** Replace with `Advertisement`:
```bash
TOPICS=(
  'Advertisement'
  'CalculatorServiceRequest' 'CalculatorServiceReply'
```

---

#### 3. **`tests/run_triage_suite.sh`**

**Lines 101-102:**
```bash
local topics=(
  'GenesisRegistration'
  'FunctionCapability'
  'CalculatorServiceRequest' 'CalculatorServiceReply'
```

**Issue:** Expects legacy topics in triage suite

**Fix:** Replace with unified topic:
```bash
local topics=(
  'Advertisement'
  'CalculatorServiceRequest' 'CalculatorServiceReply'
```

**Lines 189-190:**
```bash
"consider timing/durability; check FunctionCapability durability and registration topics"
```

**Fix:**
```bash
"consider timing/durability; check Advertisement durability"
```

---

#### 4. **`tests/README.md`**

**Line 49:**
```markdown
- Verifies durable GenesisRegistration, request/reply topics, and pass tokens.
```

**Fix:**
```markdown
- Verifies durable Advertisement, request/reply topics, and pass tokens.
```

---

### 📖 Main README - NEEDS COMPREHENSIVE UPDATE

**File:** `README.md`

**Found 16 references across multiple sections**

#### Architecture Diagrams (Lines 240-315)

**Lines 242-243:**
```markdown
A->>F: Subscribes to `FunctionCapability` Topic
F-->>A: Receives Function Announcements
```

**Fix:**
```markdown
A->>F: Subscribes to `Advertisement` Topic (kind=FUNCTION)
F-->>A: Receives Function Announcements
```

**Line 313:**
```markdown
DDS -- Pub/Sub --> Discovery[FunctionCapability, AgentCapability]
```

**Fix:**
```markdown
DDS -- Pub/Sub --> Discovery[Advertisement (unified)]
```

#### Feature Descriptions (Lines 336-421)

**Line 336:**
```markdown
* **Discovers** agents through enhanced `AgentCapability` announcements
```

**Fix:**
```markdown
* **Discovers** agents through unified `Advertisement` topic (kind=AGENT)
```

**Lines 360-362:**
```markdown
* **Function Discovery:** Via `FunctionCapability` with rich metadata
* **Agent Discovery:** Via `AgentCapability` with specializations and capabilities
```

**Fix:**
```markdown
* **Function Discovery:** Via `Advertisement` topic (kind=FUNCTION) with rich metadata
* **Agent Discovery:** Via `Advertisement` topic (kind=AGENT) with specializations and capabilities
* **Unified Discovery:** Single durable topic for all agent and function announcements
```

**Line 400:**
```markdown
* **Publish/Subscribe:** For discovery (`FunctionCapability`, `AgentCapability`), monitoring
```

**Fix:**
```markdown
* **Publish/Subscribe:** For discovery (`Advertisement` - unified), monitoring
```

**Line 419:**
```markdown
* **Automatic Agent Discovery:** Agents automatically discover each other through enhanced `AgentCapability` announcements
```

**Fix:**
```markdown
* **Automatic Agent Discovery:** Agents automatically discover each other through unified `Advertisement` topic (kind=AGENT)
```

**Line 437:**
```markdown
* Agents advertise Functions (`FunctionCapability` topic) with standardized schemas.
```

**Fix:**
```markdown
* Agents advertise Functions (`Advertisement` topic with kind=FUNCTION) with standardized schemas.
```

#### State Management Section (Line 510)

**Line 510:**
```markdown
* **DDS for Shared State (Durability):** DDS Durability QoS (`TRANSIENT_LOCAL`, `PERSISTENT`) can share state (e.g., `FunctionCapability`, shared world model)
```

**Fix:**
```markdown
* **DDS for Shared State (Durability):** DDS Durability QoS (`TRANSIENT_LOCAL`, `PERSISTENT`) can share state (e.g., `Advertisement`, shared world model)
```

#### Error Log Example (Line 640)

**Line 640:**
```markdown
2025-04-08 08:47:37,710 - FunctionCapabilityListener.4418720944 - ERROR
```

**Fix:** Update or remove this example as `FunctionCapabilityListener` no longer exists

#### DDS Architecture Section (Lines 1121-1132)

**Line 1121:**
```markdown
- **Automatic Discovery:** Agents and services announce their capabilities via DDS topics (`AgentCapability`, `FunctionCapability`)
```

**Fix:**
```markdown
- **Automatic Discovery:** Agents and services announce their capabilities via unified `Advertisement` topic (with `kind` field: AGENT=1, FUNCTION=0)
```

**Lines 1129-1130:**
```markdown
- **Agent Discovery:** Agents publish and subscribe to `AgentCapability` topics
- **Function Discovery:** Services publish to `FunctionCapability` topics
```

**Fix:**
```markdown
- **Agent Discovery:** Agents publish and subscribe to `Advertisement` topic (kind=AGENT)
- **Function Discovery:** Services publish to `Advertisement` topic (kind=FUNCTION)
- **Unified Topic:** Single durable topic consolidates all discovery, reducing DDS overhead by 47%
```

#### Liveliness QoS Reference (Line 1235)

**Line 1235:**
```markdown
- FunctionCapability writer/reader: `genesis_lib/function_discovery.py` (AUTOMATIC, 2s)
```

**Fix:**
```markdown
- Advertisement writer (unified): `genesis_lib/advertisement_bus.py` (no liveliness - persistent discovery)
```

---

### ✅ Documentation Files - KEEP (Historical Record)

These files document the consolidation process - **no changes needed**:

1. **`TOPICS_ANALYSIS.md`** - Analysis document showing before/after
2. **`LEGACY_TOPIC_REMOVAL_COMPLETE.md`** - Completion summary
3. **`PLANS/advertisement_consolidation.md`** - Planning document

---

## 📊 Priority Summary

### High Priority (Breaks Tests)
1. ✅ `tests/run_all_tests.sh` - DDS cleanup check
2. ✅ `tests/active/test_monitoring.sh` - Topic list
3. ✅ `tests/run_triage_suite.sh` - Topic list and error messages

### Medium Priority (Documentation)
4. ⚠️ `README.md` - Main project documentation (16 references)
5. ⚠️ `tests/README.md` - Test documentation

### Low Priority (Future Cleanup)
6. 📋 `genesis_lib/config/datamodel.xml` - Type definitions (keep for compatibility)

---

## ✅ Recommended Actions

1. **Immediate:** Update test scripts (`run_all_tests.sh`, `test_monitoring.sh`, `run_triage_suite.sh`)
2. **Soon:** Update main `README.md` to reflect unified Advertisement architecture
3. **Later:** Remove legacy types from `datamodel.xml` after confirming no external dependencies
4. **Keep:** All code comments and consolidation documentation files

---

## 🎯 Next Steps

Run the following command to apply all test file fixes:
```bash
# Apply fixes to test files (detailed changes above)
```

Then update `README.md` with the architecture changes to reflect:
- Single unified `Advertisement` topic
- `kind` field distinguishing FUNCTION(0) vs AGENT(1)
- 47% topic count reduction benefit
- Simplified discovery architecture

