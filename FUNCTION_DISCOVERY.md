## Function Discovery - Quick Guide

### Architecture Overview
- Registry (`genesis_lib.function_discovery.FunctionRegistry`):
  - Registers local functions, advertises them to DDS (`GenesisAdvertisement`), discovers remote ones
  - Exposes APIs to query and match functions
- Matcher (`FunctionMatcher`): Optional LLM-assisted matching, with robust fallback
- Listener (`GenesisAdvertisementListener`): Reads unified ads via a content-filtered topic (FUNCTION kind)

### Data Flow
1. Service creates `FunctionRegistry` (typically via `GenesisService`)
2. Service registers functions → Registry publishes `GenesisAdvertisement(kind=FUNCTION)`
3. Peers receive ads and call `handle_advertisement()`
4. Consumers query `get_all_discovered_functions()` or use `find_matching_functions()`

### Advertisement Payload Schema (JSON)
```json
{
  "parameter_schema": {"type": "object", "properties": {"a": {"type": "number"}}},
  "capabilities": ["math", "calculator"],
  "performance_metrics": {"latency": "low"},
  "security_requirements": {"level": "public"},
  "classification": {"domain": "mathematics"}
}
```

### Public API (essentials)
- `register_function(func, description, parameter_descriptions, capabilities, ...) -> str`
  - Returns `function_id` (UUID string) and advertises to DDS
- `get_all_discovered_functions() -> Dict[str, Dict[str, Any]]`
  - Maps `function_id` → metadata
  - Example item:
    ```json
    {
      "name": "add",
      "description": "Add two numbers",
      "provider_id": "<writer handle>",
      "schema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
      "capabilities": ["math", "calculator"],
      "service_name": "CalculatorService",
      "capability": {"service_name": "CalculatorService"}
    }
    ```
- `find_matching_functions(user_request: str) -> List[FunctionInfo]`
  - Each `FunctionInfo.match_info` has:
    ```json
    {
      "relevance_score": 0.5,
      "explanation": "Basic text matching",
      "inferred_params": {},
      "considerations": ["..."],
      "domain": "unknown",
      "operation_type": "unknown"
    }
    ```

### Usage Example
```python
from genesis_lib.genesis_service import GenesisService

class CalculatorService(GenesisService):
    def __init__(self, participant=None, domain_id=0):
        super().__init__(
            service_name="CalculatorService",
            capabilities=["calculator", "math"],
            participant=participant,
            domain_id=domain_id,
        )

    @GenesisService.genesis_function(description="Add two numbers", parameters={
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}}
    })
    def add(self, a: float, b: float) -> float:
        return a + b

# Discovery (consumer side)
registry = CalculatorService(...).registry
functions = registry.get_all_discovered_functions()
matches = registry.find_matching_functions("add two numbers")
```

### Notes
- DDS durability is `TRANSIENT_LOCAL`; late joiners can read historical ads.
- The registry prints a discovery signal line starting with "📚 PRINT:" to support tests.
- Logging:
  - INFO: business events (ads discovered/processed)
  - DEBUG: detailed traces
  - ERROR: unexpected exceptions


