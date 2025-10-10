# RPC Topic Consolidation Plan

**Status**: 📋 PLANNING  
**Start Date**: October 10, 2025  
**Goal**: Consolidate RPC topics using content filtering and service instance keying

---

## Executive Summary

Currently, Genesis creates **2 topics per service instance** (Request + Reply), leading to topic proliferation. The goal is to consolidate to **2 topics per service TYPE** using DDS ContentFilteredTopic and instance-specific keying, reducing topic count while improving scalability.

**Current State**: N service instances = 2N topics  
**Target State**: M service types = 2M topics (regardless of instance count)

---

## Lessons Learned from Monitoring Consolidation

### 🎯 What Worked Exceptionally Well

#### 1. **External Validation with rtiddsspy**
- **Why it worked**: Provided objective, unbiased validation independent of application code
- **Key benefit**: Caught issues that internal logging might miss
- **Apply to RPC**: 
  - Use spy logs to verify content filtering is working
  - Confirm requests route to correct service instances
  - Validate no topic leaks or duplicates
  - Verify GUID-based filtering functions correctly

#### 2. **Dual-Publishing During Transition**
- **Why it worked**: Allowed gradual migration with immediate rollback capability
- **Key benefit**: Zero downtime, continuous test validation
- **Apply to RPC**:
  - Phase 2: Publish to both old (per-instance) and new (unified) topics
  - Phase 3: Validate parity between old and new RPC paths
  - Phase 4: Switch subscribers to new topics
  - Phase 5: Remove old topic publishing

#### 3. **Incremental Testing with run_all_tests.sh**
- **Why it worked**: Caught regressions immediately after each change
- **Key benefit**: Fast feedback loop, easy to identify breaking commits
- **Apply to RPC**:
  - Run full test suite after EVERY phase
  - Require 13/13 passing before proceeding
  - Use existing RPC-heavy tests (run_math.sh, run_interface_agent_service_test.sh)

#### 4. **Content Filtering for Efficiency**
- **Why it worked**: Reduced CPU/memory by 90% by filtering at DDS middleware level
- **Key benefit**: No application-level filtering needed
- **Apply to RPC**:
  - Filter requests by `target_service_guid` field
  - Each service instance only receives its own requests
  - Requester can broadcast (empty GUID) or target specific instance

#### 5. **Detailed Parity Validation Scripts**
- **Why it worked**: Automated objective comparison of old vs new behavior
- **Key benefit**: Found subtle discrepancies early
- **Apply to RPC**:
  - Create `validate_rpc_parity.sh` to compare:
    - Request routing (correct service receives request)
    - Reply routing (correct requester receives reply)
    - Multi-instance load distribution
    - Error handling paths

---

## Current RPC Architecture

### Per-Instance Topics (Current)
```
Service: CalculatorService (instance 1)
  - rti/connext/genesis/CalculatorServiceRequest
  - rti/connext/genesis/CalculatorServiceReply

Service: CalculatorService (instance 2)
  - rti/connext/genesis/CalculatorService_<UUID>Request
  - rti/connext/genesis/CalculatorService_<UUID>Reply

Service: LetterCounterService
  - rti/connext/genesis/LetterCounterServiceRequest
  - rti/connext/genesis/LetterCounterServiceReply
```

**Problem**: Each service instance creates new topics, leading to topic explosion in large deployments.

---

## Proposed Architecture (Target)

### Unified Topics with Content Filtering
```
Service Type: CalculatorService (all instances)
  - rti/connext/genesis/rpc/CalculatorRequest (UNIFIED)
  - rti/connext/genesis/rpc/CalculatorReply (UNIFIED)

Service Type: LetterCounterService (all instances)
  - rti/connext/genesis/rpc/LetterCounterRequest (UNIFIED)
  - rti/connext/genesis/rpc/LetterCounterReply (UNIFIED)
```

### Key Changes

#### 1. Add `target_service_guid` field to Request types
```xml
<struct name="FunctionRequest">
    <member name="function_name" type="string"/>
    <member name="parameters_json" type="string"/>
    <member name="target_service_guid" type="string" default="''"/>  <!-- NEW -->
</struct>
```

#### 2. Content Filtering on Service Side
```python
# Each service instance filters for:
# 1. Broadcast requests (target_service_guid = '')
# 2. Requests targeted to this specific instance

filter_expr = "target_service_guid = %0 OR target_service_guid = %1"
filter_params = ["''", f"'{service_writer_guid}'"]

cft = dds.ContentFilteredTopic(
    request_topic,
    f"Filtered{service_name}Request",
    dds.Filter(filter_expr, filter_params)
)

replier = rti.rpc.Replier(
    ...,
    request_topic=cft  # Use filtered topic
)
```

#### 3. Targeted or Broadcast Requests
```python
# Broadcast to all instances (load balancing)
request = FunctionRequest(
    function_name="add",
    parameters_json='{"x": 5, "y": 3}',
    target_service_guid=""  # Empty = broadcast
)

# Target specific instance (sticky sessions)
request = FunctionRequest(
    function_name="add",
    parameters_json='{"x": 5, "y": 3}',
    target_service_guid="01010a3f4d2a..."  # Specific GUID
)
```

---

## Implementation Phases

### Phase 1: Type Updates & Example Validation (Week 1)
**Goal**: Update types, validate with standalone example

#### Tasks:
1. ✅ Review RPC_Example code thoroughly
2. ⬜ Add `target_service_guid` field to `FunctionRequest` in datamodel.xml
3. ⬜ Create standalone test script using RPC_Example pattern
4. ⬜ Validate content filtering works with 3+ service instances
5. ⬜ Use rtiddsspy to confirm only 2 topics created (not 2N)

#### Success Criteria:
- Standalone example runs with 3 calculator instances
- rtiddsspy shows only 2 topics (Request + Reply)
- Each instance receives only its targeted requests
- Broadcast requests reach all instances

#### Tools:
- `rtiddsspy` - Monitor topic creation and data flow
- Standalone test script (minimal Genesis dependencies)

---

### Phase 2: Dual-Publishing Implementation (Week 2)
**Goal**: Implement new RPC path alongside existing, maintain backward compatibility

#### Tasks:
1. ⬜ Create `rpc_service_v2.py` with unified topic logic
2. ⬜ Create `rpc_client_v2.py` with targeting support
3. ⬜ Modify `GenesisRPCService` to dual-publish:
   - Publish to old per-instance topics (existing path)
   - Publish to new unified topics (new path)
4. ⬜ Add environment variable `USE_UNIFIED_RPC=true` for opt-in
5. ⬜ Update one test service (calculator) to use dual-publishing
6. ⬜ Run targeted tests with rtiddsspy logging

#### Success Criteria:
- Old RPC path still works (backward compatible)
- New RPC path works in parallel (opt-in via env var)
- rtiddsspy shows both old and new topics
- No performance degradation

#### Tools:
- `tests/active/run_math.sh` - Simple RPC test
- `rtiddsspy` - Verify dual-publishing
- Git branch: `feature/rpc-consolidation`

---

### Phase 3: Parity Validation (Week 2-3)
**Goal**: Prove 1:1 parity between old and new RPC paths

#### Tasks:
1. ⬜ Create `tests/active/validate_rpc_parity.sh`:
   - Start 3 calculator services (different instances)
   - Send 10 requests via old path
   - Send same 10 requests via new path
   - Compare results, latency, success rates
2. ⬜ Validate multi-instance scenarios:
   - Round-robin load balancing (broadcast)
   - Sticky sessions (targeted GUID)
   - Instance failure handling
3. ⬜ Create detailed parity report (similar to monitoring)
4. ⬜ Use rtiddsspy to verify request routing

#### Success Criteria:
- 100% parity: same results for same inputs
- Latency within 5% (old vs new)
- Multi-instance routing works correctly
- Spy logs confirm correct content filtering

#### Tools:
- `tests/active/validate_rpc_parity.sh` (NEW)
- `rtiddsspy` with detailed logging
- Automated comparison script (Python)

---

### Phase 4: Comprehensive Test Suite Migration (Week 3)
**Goal**: Switch all tests to unified RPC, validate end-to-end

#### Tasks:
1. ⬜ Switch all services to dual-publish mode:
   - `calculator_service.py`
   - `letter_counter_service.py`
   - `text_processor_service.py`
   - All agent RPC endpoints
2. ⬜ Update `tests/run_all_tests.sh`:
   - Set `USE_UNIFIED_RPC=true` by default
   - Add spy logging to all RPC-heavy tests
3. ⬜ Run full test suite, require 13/13 passing
4. ⬜ Analyze all spy logs for topic counts

#### Success Criteria:
- 13/13 tests passing with unified RPC
- rtiddsspy logs show unified topics only (when opted in)
- No regressions in functionality
- Topic count reduction verified externally

#### Tools:
- `tests/run_all_tests.sh`
- `rtiddsspy` on every test
- Automated spy log analysis script

---

### Phase 5: Legacy RPC Removal (Week 4)
**Goal**: Remove old per-instance topic code, simplify codebase

#### Tasks:
1. ⬜ Remove old RPC topic creation logic:
   - Delete per-instance topic name generation
   - Remove `_create_unique_service_name()` helpers
2. ⬜ Update all services to use unified topics only
3. ⬜ Remove `USE_UNIFIED_RPC` environment variable
4. ⬜ Update documentation and examples
5. ⬜ Run full test suite again (13/13 required)

#### Success Criteria:
- No per-instance topics created
- All tests passing without environment variable
- Codebase simplified (lines of code reduction)
- rtiddsspy shows minimal topic count

#### Tools:
- `git diff` to verify deletions
- `tests/run_all_tests.sh`
- `rtiddsspy` for final validation

---

### Phase 6: Documentation & Final Validation (Week 4)
**Goal**: Document new architecture, create external validation report

#### Tasks:
1. ⬜ Update `GENESIS_TOPICS.md` with new RPC architecture
2. ⬜ Create `RPC_CONSOLIDATION_VALIDATION.md`:
   - Topic reduction metrics
   - Performance comparison (old vs new)
   - Spy log analysis summary
   - Migration guide for users
3. ⬜ Update `README.md` with RPC content filtering info
4. ⬜ Create usage examples for targeted vs broadcast requests
5. ⬜ Run final comprehensive validation

#### Success Criteria:
- Complete documentation of new RPC architecture
- External validation report (similar to monitoring)
- Usage examples for developers
- Migration guide for existing deployments

#### Deliverables:
- `RPC_CONSOLIDATION_VALIDATION.md`
- Updated `GENESIS_TOPICS.md`
- Usage examples in `examples/`

---

## Testing Strategy (Lessons Applied)

### 1. **Continuous Spy Logging**
Every test that uses RPC should have a spy log:
```bash
# In every test script
SPY_LOG="$LOG_DIR/spy_$(basename $0 .sh).log"
RTIDDSSPY_PROFILEFILE="$PROJECT_ROOT/spy_transient.xml" \
  "$NDDSHOME/bin/rtiddsspy" > "$SPY_LOG" 2>&1 &
```

### 2. **Automated Spy Log Analysis**
Create validation script:
```bash
#!/bin/bash
# Verify unified RPC topics in spy logs

for spy_log in logs/spy_*.log; do
  # Check for old per-instance topics (should be ZERO after Phase 5)
  legacy_count=$(grep "New writer" "$spy_log" | \
    grep -c "ServiceRequest.*UUID" || echo "0")
  
  if [ "$legacy_count" != "0" ]; then
    echo "❌ FAIL: Found $legacy_count legacy RPC topics in $spy_log"
    exit 1
  fi
done

echo "✅ PASS: No legacy RPC topics found"
```

### 3. **Individual Test → Run All Tests**
Change → Test → Debug cycle:
1. Make code change
2. Run individual test: `tests/active/run_math.sh`
3. Check spy log: `logs/spy_run_math.log`
4. If passing, run full suite: `tests/run_all_tests.sh`
5. Analyze all spy logs for regressions

### 4. **Git Commits per Phase**
After each phase, commit with descriptive message:
```bash
git commit -m "Phase 2: RPC dual-publishing - all tests passing (13/13)"
```

### 5. **Rollback Safety**
Always maintain ability to revert:
- Use feature branch: `feature/rpc-consolidation`
- Tag each phase: `v1.0-rpc-phase2`
- Keep dual-publishing for at least 2 phases

---

## Expected Metrics

### Topic Reduction
**Before**: 15+ topics (typical deployment)
- 3 core (Advertisement + 2 monitoring)
- 12 RPC (6 services × 2 directions)

**After**: 9+ topics (typical deployment)
- 3 core (Advertisement + 2 monitoring)
- 6 RPC (3 service types × 2 directions) ← **50% reduction**

### Performance Impact
- **Latency**: Expected ±2% (negligible, within measurement error)
- **Memory**: 30-40% reduction (fewer DDS readers/writers per service)
- **CPU**: 10-20% reduction (content filtering at middleware level)

### Scalability
- **Before**: 100 service instances = 200 topics
- **After**: 100 service instances of 5 types = 10 topics ← **95% reduction**

---

## Risk Mitigation

### High Risk: Content Filter Complexity
**Risk**: Complex filter expressions may fail or have edge cases  
**Mitigation**:
- Start with simple 2-parameter filter (broadcast OR specific GUID)
- Validate with RPC_Example standalone first
- Test with 10+ concurrent service instances
- Use rtiddsspy to verify filtering behavior

### Medium Risk: GUID Format Inconsistencies
**Risk**: Different GUID string formats may break filtering  
**Mitigation**:
- Standardize GUID-to-string conversion across codebase
- Add validation helpers: `validate_service_guid()`
- Test with multiple GUID formats in parity validation

### Low Risk: Performance Regression
**Risk**: New RPC path may be slower  
**Mitigation**:
- Benchmark in Phase 3 (parity validation)
- Compare latency: old vs new (require <5% difference)
- Profile with rtiddsspy and DDS tools

---

## Success Criteria (Final)

### Functional
- ✅ All 13 tests passing with unified RPC
- ✅ Multi-instance load balancing works
- ✅ Targeted requests route correctly
- ✅ Error handling preserved

### External Validation
- ✅ rtiddsspy shows unified topics only (2 per service type)
- ✅ No legacy per-instance topics in any test
- ✅ Content filtering verified in spy logs
- ✅ Request routing confirmed via GUID analysis

### Performance
- ✅ Latency within ±5% of baseline
- ✅ Topic count reduced by 50%+
- ✅ Memory usage reduced by 30%+

### Documentation
- ✅ `RPC_CONSOLIDATION_VALIDATION.md` complete
- ✅ `GENESIS_TOPICS.md` updated
- ✅ Usage examples created
- ✅ Migration guide for users

---

## Key Takeaways from Monitoring Consolidation

### DO:
✅ Use rtiddsspy for every test  
✅ Implement dual-publishing phase  
✅ Create automated parity validation  
✅ Run full test suite after EVERY change  
✅ Commit after each successful phase  
✅ Use content filtering for efficiency  
✅ Create external validation reports  

### DON'T:
❌ Skip spy logging (external validation is critical)  
❌ Remove old code too early (dual-publish first)  
❌ Assume tests pass without running them  
❌ Trust internal logs alone (spy logs are ground truth)  
❌ Skip parity validation (subtle bugs hide here)  

---

## Timeline Estimate

| Phase | Duration | Confidence |
|-------|----------|------------|
| Phase 1: Types & Example | 3 days | High |
| Phase 2: Dual-Publishing | 4 days | High |
| Phase 3: Parity Validation | 5 days | Medium |
| Phase 4: Test Migration | 3 days | High |
| Phase 5: Legacy Removal | 2 days | High |
| Phase 6: Documentation | 2 days | High |
| **Total** | **19 days** | **~4 weeks** |

**Buffer**: +5 days for unexpected issues (25% contingency)

---

## Next Steps

1. ⬜ Review this plan with team
2. ⬜ Create feature branch: `feature/rpc-consolidation`
3. ⬜ Start Phase 1: Validate RPC_Example
4. ⬜ Set up spy logging infrastructure for RPC tests
5. ⬜ Schedule weekly progress reviews

---

**Document Version**: 1.0  
**Last Updated**: October 10, 2025  
**Author**: Based on monitoring consolidation lessons learned  
**Status**: 📋 Ready for Review


