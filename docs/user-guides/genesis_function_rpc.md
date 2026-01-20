# Genesis Function RPC System Explained

## 1. Introduction

This document provides a detailed explanation of the Genesis Function RPC (Remote Procedure Call) system, primarily used for communication between Agents and Function providers (Services). The core design principle is **dynamic discovery**: callers (Agents) do not need prior knowledge of available functions, their names, or their specific parameters. All necessary information is discovered at runtime through DDS (Data Distribution Service) mechanisms.

### Example Flow: Calculator Request with Classification

```mermaid
sequenceDiagram
    participant User
    participant Agent as GenesisAgent
    participant FReg as FunctionRegistry
    participant LLM1 as Fast-LLM
    participant LLM2 as Full-LLM
    participant Calc as CalculatorService

    User->>Agent: "What is 34 * (12 / 4)?"
    Agent->>FReg: list()
    FReg-->>Agent: 24 funcs
    Agent->>LLM1: classify(request, funcs)
    LLM1-->>Agent: [calc.multiply, calc.divide]
    Agent->>LLM2: request + subset
    LLM2-->>Agent: call(calc.divide, 12,4)
    Agent->>Calc: RPC divide(12,4)
    Calc-->>Agent: 3
    Agent->>LLM2: result=3
    LLM2-->>Agent: call(calc.multiply, 34,3)
    Agent->>Calc: RPC multiply(34,3)
    Calc-->>Agent: 102
    Agent->>LLM2: result=102
    LLM2-->>Agent: "The answer is 102."
    Agent-->>User: 102
```

This example demonstrates:
1. **Dynamic Discovery**: Agent queries FunctionRegistry for available functions
2. **Classification**: Fast-LLM narrows down relevant functions from the full registry
3. **Tool Execution**: Full-LLM uses classified functions to solve the problem
4. **RPC Communication**: Agent makes RPC calls to CalculatorService
5. **Multi-step Reasoning**: LLM chains multiple function calls to reach the answer

This system leverages RTI Connext DDS and its RPC capabilities (`rti.rpc`) but builds significant abstractions on top for function registration, discovery, monitoring, and standardized request/reply handling, particularly within the `GenesisRPCService` and `EnhancedServiceBase` classes.

Understanding this system is crucial for maintaining existing function services and for designing the new Interface-to-Agent RPC system, aiming to reuse its successful patterns while adhering to the desired communication hierarchy (Interface <-> Agent <-> Function).

## 2. Core Components

### 2.1. Data Model (`genesis_lib/datamodel.py`)

These Python classes, decorated with `@idl.struct`, define the data structures exchanged over DDS for function RPC. They map directly to DDS types defined potentially in XML (`datamodel.xml`) but are used programmatically as Python classes.

*   **`Function`**: Represents the definition of a single function available for remote calls.
    *   `name: str`: The name of the function (e.g., "add", "get_weather").
    *   `description: str`: A human-readable description of what the function does.
    *   `parameters: str`: **Crucially**, this is a *JSON string* representing the JSON Schema definition of the function's expected parameters (following OpenAI's function/tool schema format). This schema is used by the Agent to understand how to format arguments and potentially by the service for validation.
    *   `strict: bool`: If `True`, the service attempts to validate incoming arguments against the `parameters` schema.

*   **`Tool`**: An OpenAI-style container, currently always of type "function".
    *   `type: str`: Always "function".
    *   `function: Function`: Embeds the `Function` definition. Services register `Tool` objects.

*   **`FunctionCall`**: Represents the details of a *specific* function invocation *within* a request.
    *   `name: str`: The name of the function *to be called*.
    *   `arguments: str`: A *JSON string* containing the actual arguments for the function call, formatted according to the schema defined in the corresponding `Function`'s `parameters`.

*   **`FunctionRequest`**: The main structure sent by a caller (Agent) to invoke a function.
    *   `id: str`: A unique identifier for this specific request, often used for correlation (though RTI RPC handles correlation implicitly).
    *   `type: str`: Always "function".
    *   `function: FunctionCall`: Embeds the `FunctionCall` details specifying *which* function to call and *with what* arguments.

*   **`FunctionReply`**: The main structure sent back by the service (Function provider) to the caller (Agent).
    *   `result_json: str`: A *JSON string* containing the result of the function execution. Can be complex JSON.
    *   `success: bool`: Indicates whether the function executed successfully.
    *   `error_message: str`: If `success` is `False`, this contains a description of the error.

**Implementation Note:** Consistent use of these specific classes and their fields is vital. Arguments and results are *always* JSON strings within these structures. Parsing and serialization happen within the RPC service logic.

### 2.2. Base RPC Service (`genesis_lib/rpc_service.py`)

*   **`GenesisRPCService`**: The fundamental base class for creating RPC services that expose functions.
    *   **`__init__(self, service_name: str)`**:
        *   Initializes the DDS `DomainParticipant`.
        *   Creates an `rti.rpc.Replier` instance. This is the core DDS entity that listens for incoming requests and sends replies.
            *   `request_type`: Set by `self.get_request_type()`, defaults to `FunctionRequest`.
            *   `reply_type`: Set by `self.get_reply_type()`, defaults to `FunctionReply`.
            *   `participant`: The DDS participant.
            *   `service_name`: This name is used by `rti.rpc.Replier` primarily to **derive the default DDS Topic names** for the request and reply types (e.g., `CalculatorServiceRequest`, `CalculatorServiceReply`). While important for DDS discovery of the *RPC endpoint itself*, it's **not** used by callers to discover *what functions* the service provides. That happens via the separate Function Discovery mechanism (see Section 3.1). It serves mainly for debugging and identifying the RPC service endpoint within DDS tools.
        *   Initializes `self.functions: Dict[str, Dict[str, Any]] = {}`: This dictionary is crucial. It maps registered function names (strings) to dictionaries containing their implementation (`"implementation": Callable`), their schema/description (`"tool": Tool`), and potentially other metadata.

    *   **`get_request_type(self)` / `get_reply_type(self)`**: Return the Python classes (`FunctionRequest`, `FunctionReply`) used for this RPC service. Allows potential overriding but is standard for function services.

    *   **`register_function(self, func, description, parameters, ...)`**:
        *   Takes the Python function (`func`), its description, and its parameter schema (as a Python `dict`).
        *   Validates the parameter schema (`validate_schema`).
        *   Creates the `Function` and `Tool` objects from `datamodel.py`.
        *   Stores the function implementation and its `Tool` definition in the `self.functions` dictionary, keyed by the function's name (`func.__name__`).

    *   **`async run(self)`**:
        *   The main asynchronous loop that handles incoming requests.
        *   Enters an infinite loop waiting for requests using `self.replier.receive_requests(...)`. This blocks until requests arrive or the timeout occurs.
        *   Iterates through received `request_sample`s.
        *   Extracts the `request = request_sample.data` (which is an instance of `FunctionRequest`) and `request_info = request_sample.info` (containing DDS metadata like the caller's identity).
        *   Retrieves `function_name` and `arguments_json` from `request.function`.
        *   **Looks up** the `function_name` in its `self.functions` dictionary.
        *   If found:
            *   Retrieves the actual Python function implementation (`func = self.functions[function_name]["implementation"]`).
            *   Parses the `arguments_json` string into a Python dictionary (`args_data`).
            *   **(Optional)** If `strict=True` in the function's `Tool` definition, validates `args_data` against the schema stored in the `Tool`.
            *   **Injects** the `request_info` into the arguments dictionary (`args_data["request_info"] = request_info`). This allows the function implementation to know about the caller if needed (e.g., for monitoring).
            *   **Calls** the actual function implementation: `result = func(**args_data)`. Handles both regular functions and `async` functions.
            *   Serializes the `result` back into a JSON string (`result_json`).
            *   Creates a `FunctionReply` instance with `success=True` and the `result_json`.
        *   If the function name is not found, or if argument parsing/validation/execution fails:
            *   Logs the error appropriately.
            *   Creates a `FunctionReply` instance with `success=False` and a descriptive `error_message`.
        *   Sends the `FunctionReply` back to the specific caller using `self.replier.send_reply(reply, request_sample.info)`. The `request_sample.info` ensures the reply is correlated to the original request by the underlying RTI RPC mechanism.
        *   Includes `try...except` blocks for robust error handling during the request processing lifecycle.

    *   **`close(self)`**: Cleans up DDS resources (`Replier`, `Participant`).

**Implementation Note:** The `run` method's logic for looking up functions in `self.functions`, parsing/validating arguments, calling the implementation, and handling results/errors is the core request-processing pipeline.

### 2.3. Enhanced RPC Service (`genesis_lib/enhanced_service_base.py`)

*   **`EnhancedServiceBase`**: Inherits from `GenesisRPCService` and adds significant capabilities, primarily function discovery/advertisement and enhanced monitoring. Services like `CalculatorService` typically inherit from this class.
    *   **`__init__(self, service_name, capabilities, participant=None, domain_id=0, registry: FunctionRegistry = None)`**:
        *   Calls `super().__init__(service_name)`.
        *   Sets up DDS entities for **monitoring** (writers for `MonitoringEvent`, `ComponentLifecycleEvent`, `ChainEvent`, `LivelinessUpdate`). Uses `DynamicData` and types loaded from XML via `dds.QosProvider`.
        *   Initializes `FunctionRegistry` (from `genesis_lib/function_discovery.py`) if not provided. The registry is responsible for interacting with the DDS layer for advertising and discovering `FunctionCapability` data.
        *   Creates and sets an `EnhancedFunctionCapabilityListener` on the registry's reader to react to discovery events (e.g., logging matches, potentially triggering actions when other services/functions appear).
        *   Stores `self.app_guid` (derived from the registry's DDS writer instance handle) for unique service identification in monitoring.
        *   Calls `self._auto_register_decorated_functions()` to automatically register methods decorated with `@genesis_function`.

    *   **`_auto_register_decorated_functions(self)`**: Scans the class instance for methods decorated with `@genesis_function` (see `genesis_lib/decorators.py`) and calls `register_enhanced_function` for each.

    *   **`register_enhanced_function(self, func, description, parameters, ...)`**:
        *   A wrapper around the base class's `register_function`.
        *   Logs the enhanced registration process.
        *   Calls `self.function_wrapper(func_name)(func)` to wrap the user's function implementation with monitoring logic *before* registering it.
        *   Calls the base `self.register_function` with the *wrapped* function.

    *   **`function_wrapper(self, func_name)`**: (Implemented as a decorator factory)
        *   This is a key part of the enhanced monitoring. It returns a decorator that wraps the actual function implementation.
        *   The `wrapper` function inside the decorator:
            *   Extracts `request_info` from the called function's `kwargs`.
            *   Extracts call arguments (`call_data`).
            *   Publishes `ComponentLifecycleEvent` (state -> BUSY) and `ChainEvent` (type -> CALL_START) *before* calling the original function. Includes correlation IDs (`chain_id`, `call_id`).
            *   Calls the original function implementation (`result = func(*args, **kwargs)`).
            *   Publishes `ChainEvent` (type -> CALL_COMPLETE) and `ComponentLifecycleEvent` (state -> READY) *after* the function returns successfully.
            *   If the function raises an exception:
                *   Publishes `ChainEvent` (type -> CALL_ERROR) and `ComponentLifecycleEvent` (state -> DEGRADED).
                *   Re-raises the exception so the base `run` method can catch it and send an error `FunctionReply`.

    *   **`_publish_monitoring_event(...)` / `publish_component_lifecycle_event(...)`**: Helper methods to construct and publish various DDS monitoring messages using the dedicated monitoring writers. They handle creating `DynamicData`, populating fields (timestamps, IDs, states, metadata), and writing to the appropriate DDS Topic.

    *   **`_advertise_functions(self)`**:
        *   This method orchestrates the advertisement of the service's registered functions so that Agents can discover them. **Crucially, this uses a separate mechanism (`FunctionCapability` DDS Topic) from the RPC endpoint discovery.**
        *   Publishes initial monitoring events indicating the service is joining/initializing/discovering (`ComponentLifecycleEvent` with categories `NODE_DISCOVERY`, `AGENT_INIT`).
        *   Iterates through `self.functions`. For each function:
            *   Retrieves its schema, description, capabilities, etc.
            *   Publishes `ComponentLifecycleEvent` (category `NODE_DISCOVERY`) for the *function itself* (using a unique ID for the function node).
            *   Publishes `ComponentLifecycleEvent` (category `EDGE_DISCOVERY`) to represent the link between the *service application* (`self.app_guid`) and the *function node* it hosts.
            *   Calls `self.registry.register_function(...)`. This translates the function's details into a `FunctionCapability` structure (defined in `genesis_lib/function_discovery.py`, similar to `datamodel.xml` definition) and **publishes it on the `FunctionCapability` DDS topic.** This is the core advertisement step for discovery by Agents.
        *   After advertising all functions, publishes final monitoring events indicating the service is READY (`ComponentLifecycleEvent` category `AGENT_READY`).
        *   Sets `self._functions_advertised = True`.

    *   **`async run(self)`**: Overrides the base `run`. It ensures `_advertise_functions()` is called once before calling `super().run()` to start the request handling loop. Includes `finally` block for cleanup.

    *   **`handle_function_discovery(...)` / `handle_function_removal(...)`**: Methods intended to be called by the `FunctionCapabilityListener` when *other* functions are discovered or removed from the network. Allows the service to react to changes in available functions elsewhere.

    *   **`close(self)`**: Extends the base `close` to also close the `FunctionRegistry`.

**Implementation Note:** Services providing functions should inherit from `EnhancedServiceBase`, use the `@genesis_function` decorator (or call `register_enhanced_function` directly), and the base class handles advertisement and monitored execution.

### 2.4. Function Discovery (`genesis_lib/function_discovery.py`)

While not directly part of the RPC *call* mechanism, this is essential for the dynamic nature of the system.
*   **`FunctionRegistry`**: Manages the advertisement and discovery of functions via DDS.
    *   Creates DDS DataWriters for publishing `FunctionCapability` data.
    *   Creates DDS DataReaders for discovering `FunctionCapability` data published by *other* services.
    *   Provides `register_function` which takes function details and publishes them as `FunctionCapability`.
    *   Provides ways to query discovered functions.
*   **`FunctionCapability`**: The data structure (defined via `datamodel.xml` and used with `DynamicData`) that describes a function's capabilities, including its name, description, provider ID (the service's `app_guid`), parameter schema (as a JSON string), and the crucial **`service_name`**. This `service_name` within `FunctionCapability` tells the Agent **which RPC service endpoint** (the `service_name` used when initializing the `Replier`/`Requester`) to target when it wants to call *this specific function*.
*   **`FunctionCapabilityListener`**: A DDS listener attached to the `FunctionCapability` DataReader. Its `on_data_available` method is triggered when new functions are discovered or existing ones update/disappear. `EnhancedServiceBase` uses a custom version (`EnhancedFunctionCapabilityListener`) to trigger `handle_function_discovery`/`handle_function_removal` and publish monitoring events.

**Implementation Note:** Agents use a `FunctionRegistry` (or similar discovery mechanism) to find functions. They read `FunctionCapability` samples from DDS. The `parameter_schema` tells the Agent how to structure the `arguments` JSON in the `FunctionRequest`, and the `service_name` field tells the Agent which RPC service endpoint to send the `FunctionRequest` to.

### 2.5. Underlying RTI RPC (`rti.rpc`)

*   **`rti.rpc.Replier`**: Used by the *service* (`GenesisRPCService`/`EnhancedServiceBase`). Listens on DDS topics derived from the `service_name` and `request_type`. Receives requests, allows the application (`run` loop) to process them, and sends replies back using `send_reply`, ensuring correlation.
*   **`rti.rpc.Requester`**: Used by the *caller* (Agent). Sends requests (`FunctionRequest`) using `send_request` targeted at a specific `service_name`. Receives replies (`FunctionReply`) using `receive_replies` or `read_replies`/`take_replies`. Handles request-reply correlation automatically using DDS mechanisms.

## 3. Workflow Deep Dive

### 3.1. Function Registration & Advertisement (Service Startup)

1.  A service (e.g., `CalculatorService`) inherits from `EnhancedServiceBase`.
2.  `EnhancedServiceBase.__init__` is called, setting up DDS, monitoring, and the `FunctionRegistry`.
3.  Functions are registered:
    *   Using `@genesis_function` decorator on methods (preferred).
    *   Or by explicitly calling `service.register_enhanced_function(method, description, params_schema)`.
4.  The decorator/`register_enhanced_function` calls `EnhancedServiceBase.function_wrapper` to wrap the method with monitoring logic.
5.  The wrapped function is registered with the base `GenesisRPCService.register_function`, storing it in `self.functions`.
6.  The service's `async run()` method is called.
7.  `EnhancedServiceBase.run()` calls `_advertise_functions()`.
8.  `_advertise_functions()`:
    *   Publishes initial "joining" monitoring events.
    *   Iterates through functions in `self.functions`.
    *   For each function, calls `self.registry.register_function()`.
    *   `registry.register_function()` creates a `FunctionCapability` DDS sample containing the function's name, description, parameter schema (JSON string), provider ID (`self.app_guid`), and the `service_name` of the hosting RPC service.
    *   The `FunctionCapability` sample is **published** on the globally known `FunctionCapability` DDS topic.
    *   Monitoring events (`NODE_DISCOVERY` for the function, `EDGE_DISCOVERY` linking function to service) are published.
    *   Publishes final "ready" monitoring events.
9.  `EnhancedServiceBase.run()` calls `super().run()`, starting the `GenesisRPCService.run()` request loop. The service now listens for `FunctionRequest` messages via its `Replier`.

### 3.2. Function Discovery (Agent Startup/Runtime)

1.  An Agent initializes its own DDS Participant and a `FunctionRegistry` instance (or equivalent discovery logic).
2.  The Agent's `FunctionRegistry` creates a DDS DataReader for the `FunctionCapability` topic with a Listener (`FunctionCapabilityListener`).
3.  As services advertise their functions (Step 3.1.8), the Agent's Listener receives `FunctionCapability` DDS samples.
4.  The Listener's `on_data_available` callback processes these samples.
5.  The Agent now knows:
    *   A function named `X` exists.
    *   It's described by `description`.
    *   It expects parameters defined by the JSON schema in `parameter_schema`.
    *   It is provided by the service instance identified by `provider_id`.
    *   To call it, send a `FunctionRequest` to the RPC endpoint identified by `service_name` (extracted from the `FunctionCapability` sample).
6.  The Agent typically stores this discovered function information locally (e.g., in a dictionary mapping function names to their capabilities and target service name).

### 3.3. Function Call (Agent -> Service)

1.  The Agent decides to call a discovered function (e.g., "add").
2.  It retrieves the function's details (parameter schema, target `service_name`) from its discovered function cache.
3.  It constructs the arguments dictionary (e.g., `{'a': 1, 'b': 2}`) according to the discovered `parameter_schema`.
4.  It **serializes** the arguments dictionary into a JSON string: `'{"a": 1, "b": 2}'`.
5.  It creates a `FunctionCall` instance: `FunctionCall(name="add", arguments='{"a": 1, "b": 2}')`.
6.  It creates a `FunctionRequest` instance, embedding the `FunctionCall`: `FunctionRequest(id=unique_id, type="function", function=call_details)`.
7.  The Agent uses an `rti.rpc.Requester` instance, configured to communicate with the **target `service_name`** (discovered in Step 3.2.5).
8.  The Agent sends the request: `request_id = requester.send_request(function_request_object)`.
9.  The request travels via DDS to the target service's `Replier`.
10. The Service's `GenesisRPCService.run()` loop receives the request via `replier.receive_requests()`.
11. The `run` loop looks up "add" in `self.functions`.
12. It retrieves the *wrapped* implementation function.
13. It parses the `arguments` JSON string back into a dictionary.
14. It calls the wrapper function (created by `EnhancedServiceBase.function_wrapper`).
15. The wrapper publishes "CALL_START" monitoring events.
16. The wrapper calls the original `add(a=1, b=2, request_info=...)` implementation.
17. The `add` function executes and returns the result (e.g., `3`).
18. The wrapper receives the result.
19. The wrapper publishes "CALL_COMPLETE" monitoring events.
20. The wrapper returns the result (`3`) to the `run` loop.
21. The `run` loop **serializes** the result into a JSON string: `'3'` (or `'{"result": 3}'` depending on formatting).
22. It creates a `FunctionReply`: `FunctionReply(result_json='3', success=True, error_message="")`.
23. It sends the reply back using `replier.send_reply(reply, request_sample.info)`.
24. The Agent, waiting for a reply on its `Requester` (e.g., using `replies = requester.receive_replies(related_request_id=request_id)`), receives the `FunctionReply` sample.
25. The Agent extracts the `FunctionReply` object.
26. It checks `reply.success`.
27. If successful, it **parses** `reply.result_json` to get the final result (e.g., `json.loads('3') -> 3`).

## 4. Key Principles & Implementation Guidance

*   **Dynamic Discovery is Paramount**: Agents MUST rely solely on discovered `FunctionCapability` data. They should *not* have hardcoded knowledge of function names, parameter structures, or target service names. The discovery mechanism provides all necessary runtime information.
*   **Separation of Concerns**:
    *   `datamodel.py`: Defines the *data* being exchanged. Stable and fundamental.
    *   `rpc_service.py`: Provides the *basic RPC mechanics* (listening, routing calls based on name, argument parsing, result serialization, basic error handling).
    *   `enhanced_service_base.py`: Adds *advanced features* on top (monitoring, advertisement via `FunctionRegistry`, function wrapping).
    *   `function_discovery.py`: Handles the DDS interactions for *advertising and discovering* the `FunctionCapability` data.
    *   `rti.rpc`: The underlying DDS *transport* for request/reply.
*   **Role of `service_name`**: Used by `rti.rpc.Replier` and `rti.rpc.Requester` to establish the underlying DDS communication channel (Topics). It identifies the RPC *endpoint*. Agents discover *which* `service_name` endpoint hosts a *specific* function by reading the `service_name` field within the discovered `FunctionCapability` data for that function.
*   **JSON Everywhere**: Arguments (`FunctionCall.arguments`) and results (`FunctionReply.result_json`) are transported as JSON strings within the RPC data structures. Services need to parse incoming arguments from JSON; callers need to parse results from JSON. Schemas (`Function.parameters`) are also JSON strings (representing JSON Schema).
*   **Class Structures are Key**:
    *   Always use the classes defined in `genesis_lib/datamodel.py` (`FunctionRequest`, `FunctionReply`, etc.) when constructing requests/replies.
    *   Function implementations receive arguments as standard Python types after the `run` loop parses the JSON. They should return standard Python objects; the `run` loop handles serializing the return value to JSON for the `FunctionReply`.
    *   `request_info` is injected into the function call `kwargs` by `GenesisRPCService.run` if the function implementation needs DDS-level info about the caller.
*   **Monitoring**: `EnhancedServiceBase` provides robust monitoring via its function wrapper and lifecycle event publishing. This is crucial for observing system behavior. Chain and call IDs help correlate events across different components.
*   **Error Handling**: The `run` loop in `GenesisRPCService` includes broad exception handling. Errors during argument parsing, validation, or function execution result in a `FunctionReply` with `success=False` and an `error_message`. The `function_wrapper` in `EnhancedServiceBase` adds error-specific monitoring events.

## 5. Conclusion

The Genesis Function RPC system provides a robust, dynamic, and monitored way for Agents to interact with Function services without requiring compile-time knowledge. It achieves this through:
1.  Clear data models (`datamodel.py`).
2.  A layered service implementation (`rpc_service.py`, `enhanced_service_base.py`).
3.  A dedicated DDS-based discovery mechanism (`FunctionCapability`, `FunctionRegistry`).
4.  Leveraging the underlying RTI Connext RPC primitives (`rti.rpc.Replier`, `rti.rpc.Requester`).

When designing the new Interface-to-Agent RPC system, consider adopting similar patterns:
*   Define clear `AgentRequest`/`AgentReply` data structures (likely in `datamodel.py` or a new file).
*   Use a base RPC class structure (perhaps adapting `GenesisRPCService` or creating a parallel hierarchy) for handling the DDS `Replier`/`Requester` interactions.
*   Implement a discovery mechanism (if needed beyond simple service name matching) for Agents to advertise their capabilities or specific endpoints.
*   Integrate monitoring using patterns from `EnhancedServiceBase` (wrappers, lifecycle events).
*   Strictly enforce the communication hierarchy (Interfaces only talk to Agents). This might involve checks within the RPC layers or discovery mechanisms.
*   Pay close attention to data serialization (likely JSON) within the request/reply structures. 
---
*Copyright (c) 2025, RTI & Jason Upchurch*
