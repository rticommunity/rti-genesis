# RPC Consolidation - Quick Reference

## Key Lessons from Monitoring Consolidation

### 🏆 Top 5 Most Valuable Practices

| Practice | Impact | Apply to RPC |
|----------|--------|--------------|
| **1. rtiddsspy on every test** | 🔴 CRITICAL | Add spy logging to all RPC tests, analyze topic creation |
| **2. Dual-publishing phase** | 🟡 HIGH | Keep old RPC + add new RPC, validate in parallel |
| **3. run_all_tests.sh after EVERY change** | 🟡 HIGH | Require 13/13 passing before merging any phase |
| **4. Content filtering at DDS level** | 🟢 MEDIUM | Use `target_service_guid` field for routing |
| **5. Automated parity validation** | 🟢 MEDIUM | Create script to compare old vs new RPC behavior |

---

## The Pattern That Worked

### Monitoring Consolidation Pattern (Proven)
```
Old: 5 monitoring topics → New: 2 monitoring topics (with `kind` field)
- GenesisGraphNode       → GraphTopology (kind=NODE)
- GenesisGraphEdge       → GraphTopology (kind=EDGE)
- ChainEvent             → Event (kind=CHAIN)
- ComponentLifecycleEvent → Event (kind=LIFECYCLE)
- MonitoringEvent        → Event (kind=GENERAL)

Result: 60% reduction, 100% parity, 13/13 tests passing
```

### RPC Consolidation Pattern (Proposed)
```
Old: 2N RPC topics (N instances) → New: 2 RPC topics (per service type)
- CalculatorService_instance1_Request  → CalculatorRequest (target_service_guid='')
- CalculatorService_instance1_Reply    → CalculatorReply
- CalculatorService_instance2_Request  → CalculatorRequest (target_service_guid='GUID2')
- CalculatorService_instance2_Reply    → CalculatorReply
...

Result: 50-95% reduction (depending on instance count)
```

---

## Implementation: The Workflow That Worked

### Change → Test → Debug Cycle (From Monitoring)

```bash
# 1. Make code change
vim genesis_lib/rpc_service.py

# 2. Run individual test with spy
tests/active/run_math.sh

# 3. Check spy log immediately
grep "New writer" logs/spy_run_math.log | grep "Request\|Reply"

# 4. If passing, run full suite
tests/run_all_tests.sh

# 5. Analyze ALL spy logs
for log in logs/spy_*.log; do
  echo "=== $log ==="
  grep -c "legacy_topic_pattern" $log || echo "0"
done

# 6. Commit if all green
git commit -m "Phase X: Description - 13/13 tests passing"
```

**Time per cycle**: 5-10 minutes (fast feedback!)

---

## Example Code Structure (from RPC_Example/)

### Service Side: Content Filtered Request Reader
```python
# From: primes_replier.py (lines 146-174)

# 1. Create the unified request topic
request_topic = dds.Topic(
    participant, 
    "PrimeCalculatorRequest",  # Unified for ALL instances
    Primes.PrimeNumberRequest
)

# 2. Create content filter (broadcast OR specific GUID)
filter_expression = "replier_w_guid = %0 OR replier_w_guid = %1"
filter_parameters = ["''", "''"]  # Will update after creation
cft_filter = dds.Filter(filter_expression, filter_parameters)

content_filtered_topic = dds.ContentFilteredTopic(
    request_topic,
    "FilteredPrimeCalculatorRequest",
    cft_filter
)

# 3. Create Replier with filtered topic
replier = Replier(
    request_type=Primes.PrimeNumberRequest,
    reply_type=Primes.PrimeNumberReply,
    participant=participant,
    service_name="PrimeCalculator",
    request_topic=content_filtered_topic  # ← Content filtering here!
)

# 4. Update filter parameters with this instance's GUID
my_guid = str(replier.reply_datawriter.instance_handle)
content_filtered_topic.filter_parameters = [
    "''",           # Parameter 0: matches broadcast requests
    f"'{my_guid}'"  # Parameter 1: matches targeted requests to THIS instance
]
```

### Client Side: Targeted or Broadcast Request
```python
# From: primes_requester.py (lines 50-58, 97-99)

# Broadcast request (any service instance can respond)
request = PrimeNumberRequest(
    n=100,
    primes_per_reply=5,
    replier_w_guid=""  # Empty = broadcast to all instances
)
requester.send_request(request)

# Later: targeted request to specific instance (sticky session)
request = PrimeNumberRequest(
    n=100,
    primes_per_reply=5,
    replier_w_guid=str(first_reply_guid)  # Send to same instance
)
requester.send_request(request)
```

---

## Visual: Topic Consolidation

### Before (Current Genesis)
```
[Requester]
    ↓ writes
[CalculatorService_ABC123_Request]  ← Unique topic per instance
    ↓ reads
[Service Instance 1: ABC123]

[Requester]
    ↓ writes
[CalculatorService_DEF456_Request]  ← Another unique topic
    ↓ reads
[Service Instance 2: DEF456]

Problem: 100 instances = 200 topics!
```

### After (Proposed)
```
[Requester 1] ──┐
[Requester 2] ──┼─ write ──→ [CalculatorRequest] ← Unified topic
[Requester 3] ──┘                    |
                                     | ContentFilteredTopic
                    ┌────────────────┼────────────────┐
                    ↓                ↓                ↓
      [Service Inst 1]   [Service Inst 2]   [Service Inst 3]
      (filter: guid=''   (filter: guid=''   (filter: guid=''
       OR guid=ABC)       OR guid=DEF)       OR guid=GHI)

Result: 100 instances = 2 topics (Request + Reply)!
```

---

## Spy Log Analysis (The Ground Truth)

### What We Learned from Monitoring
```bash
# Run test
tests/active/run_interface_agent_service_test.sh

# Analyze spy log
$ grep "New writer" logs/spy_test.log | grep "rti/connext/genesis"

# Before consolidation (BAD):
rti/connext/genesis/GenesisGraphNode          ← Legacy
rti/connext/genesis/GenesisGraphEdge          ← Legacy
rti/connext/genesis/ChainEvent                ← Legacy
rti/connext/genesis/ComponentLifecycleEvent   ← Legacy
rti/connext/genesis/MonitoringEvent           ← Legacy

# After consolidation (GOOD):
rti/connext/genesis/monitoring/GraphTopology  ← Unified (kind=NODE|EDGE)
rti/connext/genesis/monitoring/Event          ← Unified (kind=LIFECYCLE|CHAIN|GENERAL)

Result: ✅ 60% reduction, zero legacy topics
```

### What We'll Check for RPC
```bash
# After Phase 5 (legacy removal)
$ grep "New writer" logs/spy_run_math.log | grep "Request\|Reply"

# Before consolidation (BAD):
rti/connext/genesis/CalculatorServiceRequest            ← Per-instance
rti/connext/genesis/CalculatorService_UUID1_Request     ← Per-instance
rti/connext/genesis/CalculatorService_UUID2_Request     ← Per-instance
...

# After consolidation (GOOD):
rti/connext/genesis/rpc/CalculatorRequest   ← Unified (target_service_guid='')
rti/connext/genesis/rpc/CalculatorReply     ← Unified

Result: ✅ 50-95% reduction, zero per-instance topics
```

---

## Parity Validation (The Safety Net)

### Monitoring Consolidation Validation (What We Did)
```bash
#!/bin/bash
# tests/active/validate_monitoring_parity.sh

# 1. Run test with both old and new topics active (dual-publishing)
tests/active/run_interface_agent_service_test.sh

# 2. Parse spy log for old topics
OLD_NODES=$(grep "GenesisGraphNode" spy.log | grep "New data" | wc -l)
OLD_EDGES=$(grep "GenesisGraphEdge" spy.log | grep "New data" | wc -l)

# 3. Parse spy log for new topics
NEW_NODES=$(grep "GraphTopology.*kind.*NODE" spy.log | wc -l)
NEW_EDGES=$(grep "GraphTopology.*kind.*EDGE" spy.log | wc -l)

# 4. Compare
if [ "$OLD_NODES" -eq "$NEW_NODES" ] && [ "$OLD_EDGES" -eq "$NEW_EDGES" ]; then
    echo "✅ PARITY VALIDATED"
else
    echo "❌ PARITY FAILED: Old=$OLD_NODES/$OLD_EDGES, New=$NEW_NODES/$NEW_EDGES"
    exit 1
fi
```

### RPC Consolidation Validation (What We'll Do)
```bash
#!/bin/bash
# tests/active/validate_rpc_parity.sh

# 1. Start 3 calculator services
for i in {1..3}; do
    python test_functions/services/calculator_service.py &
done

# 2. Send 10 requests via old RPC path
USE_UNIFIED_RPC=false python tests/test_rpc_calls.py > old_results.txt

# 3. Send same 10 requests via new RPC path
USE_UNIFIED_RPC=true python tests/test_rpc_calls.py > new_results.txt

# 4. Compare results
if diff old_results.txt new_results.txt; then
    echo "✅ RPC PARITY VALIDATED"
else
    echo "❌ RPC PARITY FAILED"
    diff old_results.txt new_results.txt
    exit 1
fi

# 5. Check spy log for unified topics
UNIFIED_TOPICS=$(grep "rpc/CalculatorRequest" spy.log | wc -l)
LEGACY_TOPICS=$(grep "CalculatorService.*UUID.*Request" spy.log | wc -l)

if [ "$LEGACY_TOPICS" -eq 0 ] && [ "$UNIFIED_TOPICS" -gt 0 ]; then
    echo "✅ TOPIC CONSOLIDATION VERIFIED"
else
    echo "❌ TOPIC CONSOLIDATION FAILED"
    exit 1
fi
```

---

## Rollback Strategy (Insurance Policy)

### What We Learned
During monitoring consolidation, dual-publishing saved us twice:
1. **Phase 3**: Found timing issue with ChainEvents → fixed without breaking tests
2. **Phase 6**: Discovered viewer wasn't using V2 flag → quick rollback for demo

### Apply to RPC
```python
# rpc_service.py (Phase 2-4: Dual-publishing active)

class GenesisRPCService:
    def __init__(self, service_name, use_unified_rpc=None):
        if use_unified_rpc is None:
            use_unified_rpc = os.getenv('USE_UNIFIED_RPC', 'false') == 'true'
        
        # Always create old RPC path (backward compatible)
        self.old_replier = self._create_per_instance_replier(service_name)
        
        # Optionally create new RPC path (opt-in)
        if use_unified_rpc:
            self.new_replier = self._create_unified_replier(service_name)
        else:
            self.new_replier = None
    
    def handle_request(self, request):
        result = self._execute_function(request)
        
        # Dual-publish during transition
        self.old_replier.send_reply(result)
        if self.new_replier:
            self.new_replier.send_reply(result)  # Same result, both paths
```

**Rollback**: Just set `USE_UNIFIED_RPC=false` → instant fallback to old path!

---

## Timeline Comparison

### Monitoring Consolidation (Actual)
- **Phase 1-2 (Dual-publishing)**: 5 days
- **Phase 3 (Parity validation)**: 3 days
- **Phase 4-6 (Migration)**: 4 days
- **Phase 7-8 (Cleanup)**: 2 days
- **Total**: ~14 days

### RPC Consolidation (Estimated)
- **Phase 1 (Example validation)**: 3 days
- **Phase 2 (Dual-publishing)**: 4 days
- **Phase 3 (Parity validation)**: 5 days
- **Phase 4 (Test migration)**: 3 days
- **Phase 5 (Legacy removal)**: 2 days
- **Phase 6 (Documentation)**: 2 days
- **Total**: ~19 days (±5 day buffer)

**Similar scope**, slightly longer due to RPC complexity (request routing, multi-instance).

---

## Critical Success Factors

### Must-Haves (From Monitoring Experience)
1. ✅ **rtiddsspy on EVERY test** - Non-negotiable external validation
2. ✅ **13/13 tests passing after EVERY phase** - Zero tolerance for regressions
3. ✅ **Dual-publishing for at least 2 phases** - Safety net for rollback
4. ✅ **Automated parity validation** - Catch subtle bugs early
5. ✅ **Comprehensive spy log analysis** - Ground truth for topic consolidation

### Nice-to-Haves
- Performance benchmarking (latency comparison)
- Load testing (100+ service instances)
- Stress testing (network partitions, failures)

---

## Final Checklist (Phase 6 Validation)

From monitoring consolidation, our final validation was:
- ✅ 13/13 tests passing
- ✅ 11/11 spy logs analyzed
- ✅ 5,495 DDS samples validated
- ✅ ZERO legacy topics detected
- ✅ 47% topic reduction confirmed

For RPC consolidation, we'll need:
- ⬜ 13/13 tests passing
- ⬜ 11/11 spy logs analyzed (RPC-focused tests)
- ⬜ X,XXX RPC request/reply samples validated
- ⬜ ZERO per-instance topics detected
- ⬜ 50-95% topic reduction confirmed (depending on instance count)
- ⬜ Request routing validated (broadcast + targeted)
- ⬜ Multi-instance load balancing working

---

**Document Version**: 1.0  
**Created**: October 10, 2025  
**Based On**: Monitoring consolidation lessons learned  
**See Also**: `rpc_consolidation.md` (full plan)
