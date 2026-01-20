## Function Discovery - Quick Guide

### Architecture Overview
- **For Service Registration** (`genesis_lib.function_discovery.InternalFunctionRegistry`):
  - Registers local/internal functions within a service process
  - Advertises them to DDS via `GenesisAdvertisement` topic
  - Used ONLY for functions provided by THIS service
- **For Discovery** (`genesis_lib.dds_function_discovery.DDSFunctionDiscovery`):
  - Discovers functions from OTHER applications/services
  - Reads directly from DDS DataReader (no caching)
  - Used by agents and clients to find available functions
- Listener (`GenesisAdvertisementListener`): Reads unified ads via a content-filtered topic (FUNCTION kind)
- For intelligent function selection, use `FunctionClassifier` from `genesis_lib.function_classifier`

### Data Flow
1. **Service Registration** (Internal Functions):
   - Service creates `InternalFunctionRegistry` (automatically via `GenesisService`)
   - Service registers functions → Registry publishes `GenesisAdvertisement(kind=FUNCTION)`
2. **Agent Discovery** (Remote Functions):
   - Agent uses `DDSFunctionDiscovery` to read from DDS DataReader
   - Queries `list_functions()` to get current functions (no caching)
   - For intelligent selection, use `FunctionClassifier.classify_functions()` with LLM-based semantic analysis

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

**For Services (InternalFunctionRegistry)**:
- `register_function(func, description, parameter_descriptions, capabilities, ...) -> str`
  - Returns `function_id` (UUID string) and advertises to DDS
  - Used by services to register their internal functions

**For Agents/Clients (DDSFunctionDiscovery)**:
- `list_functions() -> List[Dict[str, Any]]`
  - Returns list of all currently available functions
  - Reads directly from DDS (no caching)
  - Example item:
    ```json
    {
      "function_id": "uuid-string",
      "name": "add",
      "description": "Add two numbers",
      "provider_id": "<writer handle>",
      "schema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
      "capabilities": ["math", "calculator"],
      "service_name": "CalculatorService"
    }
    ```
- `get_function_by_id(function_id: str) -> Optional[Dict[str, Any]]`
  - Get specific function by ID
- `get_function_by_name(name: str) -> Optional[Dict[str, Any]]`
  - Get specific function by name

### Intelligent Function Selection
For matching user requests to available functions, use the `FunctionClassifier`:

```python
from genesis_lib.function_classifier import FunctionClassifier
from genesis_lib.llm_factory import LLMFactory

# Initialize classifier with LLM
classifier = FunctionClassifier()
classifier.llm = LLMFactory.create_llm(purpose="classifier", provider="openai")

# Get available functions
available_functions = registry.get_all_discovered_functions()

# Classify functions based on user request
relevant_functions = classifier.classify_functions(
    query="add two numbers",
    functions=list(available_functions.values())
)
```

The `FunctionClassifier` uses LLM-based semantic analysis to intelligently match user
requests to relevant functions, following Genesis's agentic design principles.

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

# Use FunctionClassifier for intelligent selection
from genesis_lib.function_classifier import FunctionClassifier
classifier = FunctionClassifier(llm=your_llm_client)
relevant = classifier.classify_functions("add two numbers", list(functions.values()))
```

### Notes
- DDS durability is `TRANSIENT_LOCAL`; late joiners can read historical ads.
- The registry prints a discovery signal line starting with "📚 PRINT:" to support tests.
- Logging:
  - INFO: business events (ads discovered/processed)
  - DEBUG: detailed traces
  - ERROR: unexpected exceptions
- For function selection, always use `FunctionClassifier` with LLM-based semantic analysis
  rather than keyword/regex matching to ensure agentic behavior



---
*Copyright (c) 2025, RTI & Jason Upchurch*
