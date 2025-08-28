# Plan for Event-Driven Function Discovery

## Core Principles

### Centralized Discovery Cache
- FunctionRegistry (owned by GenesisApp) will be the single source of truth for discovered functions available on the network
- Its FunctionCapabilityListener will continuously update this cache in real-time as DDS FunctionCapability messages arrive or are disposed

### Event-Driven Updates
- Agents will no longer actively "discover" functions on demand
- Instead, they will access the always-up-to-date cache from GenesisApp/FunctionRegistry

### Simplified Agent Logic
- Agents (especially OpenAIGenesisAgent) will be consumers of this information, simplifying their internal logic

### Robustness & Durability
- This approach naturally supports durability
- If an agent starts before a service, the FunctionRegistry will automatically pick up the service's functions when they are eventually advertised

## Detailed Changes

### FunctionRegistry (genesis_lib/function_discovery.py) Enhancements

#### Responsibility
- Solidify its role as the primary manager of discovered function data received via DDS

#### FunctionCapabilityListener.on_data_available
- Ensure it robustly updates self.registry.discovered_functions not only for new/updated functions but also correctly handles function removal when a FunctionCapability instance is disposed (e.g., info.state.instance_state != dds.InstanceState.ALIVE)
- The listener should directly populate a structured cache (e.g., self.registry.discovered_functions) with all relevant details from the FunctionCapability message

#### Access to Discovered Functions
- Provide a clear, thread-safe public method, e.g., get_all_discovered_functions() -> Dict[str, Dict], which returns a copy or a well-structured view of the current discovered_functions cache
- This dictionary would map function_id to its details
- Consider methods like get_discovered_function_by_name(name: str) for convenience

#### Event Notification (Advanced - Optional for a first pass)
- Could implement an asyncio.Event or a callback system within FunctionRegistry that GenesisApp can expose
- This would allow agents to be notified proactively when the set of available functions changes, rather than polling
- For now, on-demand access by the agent should be sufficient

### GenesisApp (genesis_lib/genesis_app.py) Modifications

#### Responsibility
- Act as the gateway for agents to access discovered function information from its FunctionRegistry instance

#### Expose Function Access
- Add a method like get_available_functions() -> Dict[str, Dict] that simply calls self.function_registry.get_all_discovered_functions()
- This keeps a clean API for the agent and decouples it from the direct FunctionRegistry internals if they were to change

#### No Active Discovery
- GenesisApp itself doesn't initiate discovery; it relies on its FunctionRegistry's passive, event-driven nature

### GenesisAgent (genesis_lib/agent.py) Refactoring

#### Remove Active Discovery
- The existing async def discover_functions(self, function_client, ...) method should be removed or its purpose fundamentally changed
- Agents will no longer call it to find functions

#### Accessing Functions
- When an agent needs to know about available functions (e.g., to prepare a list for an LLM or to decide if it can handle a request), it will call self.app.get_available_functions()

#### Internal State
- Agents that maintain their own specific list or cache of functions (like OpenAIGenesisAgent.function_cache) will populate it by calling self.app.get_available_functions()

### OpenAIGenesisAgent (genesis_lib/openai_genesis_agent.py) Simplification

#### Remove Custom Discovery
- Delete the async def _ensure_functions_discovered(self) method entirely

#### Update Function Usage
- In methods like process_request or process_message, and especially in _get_function_schemas_for_openai, it will now call self.app.get_available_functions() to get the current list of all discovered functions on the network
- It will then filter/transform this list as needed for its self.function_cache and for providing schemas to the OpenAI API
- The logic for deciding self.system_prompt (function-based vs. general) will also rely on the output of self.app.get_available_functions()

### Role of GenericFunctionClient (genesis_lib/generic_function_client.py)
- Its discover_functions method, which actively reads/takes from the FunctionCapability topic, will no longer be the primary mechanism used by agents for continuous discovery
- It might still have utility for specific components that need a one-off, non-continuous query of available functions, but agents will rely on the GenesisApp's cached view

## Benefits of this Plan

### Truly Event-Driven
- Aligns with DDS principles
- Functions appear and disappear in the agent's awareness dynamically

### Reduced Complexity in Agents
- OpenAIGenesisAgent becomes much simpler regarding discovery

### Centralized Logic
- Discovery logic is concentrated in FunctionRegistry and its listener

### Improved Robustness
- Less prone to timing issues (e.g., service starting after agent)

### Testability
- Easier to test components in isolation

### Closer to Base Classes
- The core discovery mechanism (listening and caching) is handled by FunctionRegistry, which is a fundamental part of GenesisApp
- Agents simply consume this information

This approach directly uses the DDS queue's event-driven nature (via the DataReader and its listener in FunctionRegistry) to maintain an up-to-date, in-memory cache of functions, which is then exposed to agents. This seems more efficient and cleaner than agents trying to interact with DDS queues directly for this purpose.

## Function Calling Mechanism

Once functions are discovered and cached by an agent (e.g., `OpenAIGenesisAgent`) via the `GenesisApp` and its `FunctionRegistry`, the process of classifying and calling them involves several key identifiers:

1.  **Identifiers:**
    *   **`function_id` (UUID):** A unique identifier generated by the providing service (via its `FunctionRegistry`) for each specific function it offers (e.g., one UUID for `CalculatorService.add`, another for `CalculatorService.subtract`). This ID is advertised in the `FunctionCapability` DDS message.
    *   **`provider_id` (GUID):** The DDS GUID of the specific `DataWriter` instance (belonging to the providing service's `FunctionRegistry`) that advertised the `FunctionCapability`. This identifies the unique running instance of the service that advertised the function.
    *   **`service_name` (String):** The logical name of the service providing the function (e.g., "CalculatorService"). This is also part of the `FunctionCapability`.

2.  **Agent-Side Caching:**
    *   The `OpenAIGenesisAgent` fetches available functions from `self.app.get_available_functions()` (which gets them from `FunctionRegistry.discovered_functions`).
    *   It populates its own `self.function_cache`, typically a dictionary keyed by the function's string `name`. Each entry stores the `function_id` (UUID), `description`, `schema`, `service_name`, and `provider_id` (GUID).
    *   Example entry in `OpenAIGenesisAgent.function_cache["add"]`:
        ```json
        {
            "function_id": "abc-123-def-456", // UUID for CalculatorService.add
            "description": "Add two numbers together.",
            "schema": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "First number to add"},
                    "y": {"type": "number", "description": "Second number to add"}
                },
                "required": ["x", "y"]
            },
            "classification": { /* ... */ },
            "provider_id": "xyz-789-ghi-012", // GUID of the CalculatorService instance
            "service_name": "CalculatorService"
        }
        ```

3.  **Function Classification:**
    *   The `OpenAIGenesisAgent` passes a list of function details (including `name`, `description`, `schema`) to the `FunctionClassifier`.
    *   The `FunctionClassifier` returns a list of *names* of functions deemed relevant to the user's query. The `function_id` and `provider_id` are not directly used or returned by the classifier; the agent uses the returned names to retrieve full details from its `function_cache`.

4.  **Function Execution via RPC:**
    *   When the agent's main LLM decides to execute a function (e.g., "add" with arguments `{"x": 10, "y": 5}`), the `OpenAIGenesisAgent` looks up "add" in its `function_cache`.
    *   It retrieves the `function_id` (UUID) and `service_name`.
    *   It calls `self.generic_client.call_function()` with:
        *   `function_id`: The UUID of the function (e.g., `"abc-123-def-456"`).
        *   `target_service_name`: The string name of the service (e.g., `"CalculatorService"`).
        *   `**kwargs`: The arguments for the function (e.g., `x=10, y=5`).
    *   The `GenericFunctionClient` constructs a `FunctionExecutionRequest` DDS message. This payload includes the `function_id` (UUID) and the JSON string of parameters.
    *   The `GenericFunctionClient` uses an `rti.rpc.Requester` configured for the `target_service_name`. The DDS RPC mechanism routes this request to an available `Replier` for that service name.
    *   The `provider_id` (GUID of the specific service instance) is known to the agent but is not the primary targeting mechanism in `GenericFunctionClient`'s RPC call. The `target_service_name` is used, and DDS selects an instance. The `provider_id` is useful for logging and advanced scenarios.
    *   The remote service (e.g., `CalculatorService`) receives the `FunctionExecutionRequest`. Its `Replier` uses the `function_id` from the payload to identify and execute the correct internal Python method (e.g., its `add` method).

This flow ensures that functions are dynamically discovered and that calls are routed to the appropriate service and specific function implementation using a combination of logical service names and unique function identifiers. 

example function schema as printed out:

2025-05-08 15:24:01,327 - function_discovery - INFO - Sample data:    function_id: "e77bef10-13e0-40d6-940a-83b2bae9b1a7"
   name: "divide"
   description: "Divide the first number by the second.
        
        Args:
            x: The number to divide (example: 6.0)
            y: The number to divide by (example: 2.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the division
            
        Examples:
            >>> await divide(6, 2)
            {'result': 3}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
            DivisionByZeroError: If attempting to divide by zero
        "
   provider_id: "010196595846c3e54d893a8480008402"
   parameter_schema: "{"type": "object", "properties": {"x": {"type": "number", "description": "The number to divide (example: 6.0)"}, "y": {"type": "number", "description": "The number to divide by (example: 2.0)"}}, "required": ["x", "y"], "additionalProperties": false}"
   capabilities: "["calculator", "math"]"
   performance_metrics: "{"latency": "low"}"
   security_requirements: "{"level": "public"}"
   classification: "{}"
   last_seen: 1746739425774
   service_name: "CalculatorService"
> Status: Implemented (see genesis_lib/function_discovery.py; capability listener, callbacks, discovery cache). Last reviewed: 2025-08-28.
