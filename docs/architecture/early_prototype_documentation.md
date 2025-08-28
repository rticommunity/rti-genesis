# GENESIS Framework - Early Prototype Status Report

## 1. Introduction

The GENESIS project aims to create a flexible framework facilitating communication and dynamic interaction between distributed components, such as AI agents, user interfaces, and specialized functions. Leveraging RTI Connext DDS as its backbone, the framework's primary goal is **not** to implement specific agent logic, but rather to provide the infrastructure that allows these components to:

1.  Register themselves within the distributed system.
2.  Dynamically discover other components and their capabilities (especially functions) at runtime.
3.  Communicate effectively using standardized data types and conventions.

This report analyzes the status of the GENESIS framework based on its early prototype implementation (`service.py`, `interface.py` usage example, `Architecture-Detailed.md`, `genesis_semantic_message.xml`), focusing on the core framework mechanisms rather than the specific example applications built upon it.

## 2. Core Framework Components & Mechanisms

The prototype establishes the foundational architectural elements:

*   **DDS Communication Backbone:**
    *   **Data Models (`genesis_semantic_message.xml`):** Defines standardized DDS structures for registration announcements/assignments, function details, and basic inter-component messaging (questions/answers). This enforces a common language.
    *   **Core Service Topics:** Uses predefined DDS topics for essential framework services like registration (`AgentRegistrationTopic`, `InterfaceRegistrationTopic`, `FunctionRegistrationTopic`, etc.).
    *   **Dynamic Communication Topics:** Implements a crucial convention where direct communication topics between registered components are dynamically named using runtime-assigned numeric IDs (e.g., `QuestionTopic-{target_id}`, `AnswerTopic-{source_id}`).

*   **Service Registry (`service.py`): The Framework's Directory Service**
    *   **Centralized Registration:** Acts as the authoritative entry point for all components joining the Genesis network. It listens for standardized registration announcement messages on dedicated DDS topics.
    *   **Unique ID Assignment:** Assigns unique numeric identifiers to each registering agent, interface, and function. These IDs are the cornerstone of the dynamic topic naming convention and runtime component identification.
    *   **Function Cataloguing & Discovery:** Maintains an internal, dynamic registry of available functions, including their assigned ID, metadata (name, description), and schemas. Critically, it exposes this catalogue via DDS:
        *   Listens on `QueryFunctionListTopic` for requests (`query_genesis_function_list`).
        *   Responds on `FunctionListResponseTopic` with a list (`genesis_function_list_response`) of currently registered functions (ID, name, description). This provides the core **dynamic function discovery** capability.
    *   **Relationship Brokering (Initial):** Facilitates the connection between an interface and an agent by resolving the agent's preferred name into its assigned numeric ID during interface registration.

## 3. Key Framework Capabilities Demonstrated in Prototype

The early prototype successfully demonstrates the viability of the core framework concepts:

*   **Dynamic Component Registration:** Agents, interfaces, and functions can announce their presence via DDS and receive unique numeric IDs from the `ServiceRegistry`, allowing them to join the network dynamically.
*   **ID-Based Topic Routing:** The convention of using assigned numeric IDs to construct DDS topic names for communication is implemented, enabling targeted messaging without compile-time dependencies. (Example: `interface.py` sending to `QuestionTopic-{prefered_bot}`).
*   **Dynamic Function Discovery:** The mechanism for components to query the `ServiceRegistry` via DDS and receive a list of available functions and their IDs is functional. This is a key enabler for agents needing to find specific capabilities at runtime.
*   **Basic Interface-Agent Connection:** The framework provides the mechanism (via the `ServiceRegistry`) for an interface to find the numeric ID of a target agent it wishes to communicate with.

## 4. Framework Focus vs. Example Applications

It is important to distinguish the framework itself from the example applications (`Agent0.py`, `interface.py`) built using it. These examples *demonstrate* how to use the framework's registration and communication patterns, but their internal logic (agent processing, UI handling) is not part of the core Genesis framework. The framework's role is to provide the *plumbing* and *directory services*, not the specific applications.

## 5. Alignment with High-Level Goals

This prototype validates the fundamental architectural approach outlined in `Architecture-Detailed.md`. It proves that DDS can be effectively used for:
*   Implementing a central registry for dynamic discovery.
*   Assigning unique IDs for runtime identification.
*   Enabling dynamic construction of communication channels (topics).
*   Providing a mechanism for components (like agents) to discover available functions at runtime.

This aligns well with the likely goals of an "RTI Distributed Agentic Framework" by establishing the necessary foundation for a loosely coupled, discoverable system.

## 6. Current Framework Limitations & Next Steps

While foundational, the framework prototype requires further development:

*   **Function Invocation Mechanism:** While functions can be discovered, the standardized DDS topics and patterns for *invoking* a discovered function (e.g., Agent -> Function Provider communication via `FunctionTopic-{function_id}`) need full definition and implementation within the framework's conventions.
*   **Classifier Integration Pattern:** The architecture mentions a Classifier agent. The framework needs to define the standard DDS topics and interaction patterns for components to interact with such a classification service, building upon the existing function discovery.
*   **Framework Abstractions:** Higher-level abstractions (like the `GenesisAgent` decorator pattern mentioned in the architecture doc) could be developed to simplify framework usage for developers, hiding some direct DDS interactions.
*   **Robustness & Error Handling:** Framework-level error handling, timeouts for DDS interactions, and connection monitoring patterns need to be standardized and potentially built into helper libraries.
*   **Scalability & Security:** Considerations outlined in the architecture (registry distribution, load balancing, security features) are future steps for the framework itself.

## 7. Conclusion

The current GENESIS prototype successfully implements the essential building blocks of the proposed distributed agent framework. It provides functional mechanisms for dynamic registration, ID-based communication routing, and, most importantly, dynamic function discovery via DDS. This proves the viability of the core concepts and provides a solid foundation for building out the function invocation capabilities and higher-level framework abstractions necessary for a complete solution. The focus remains correctly on providing the communication and discovery infrastructure, enabling interoperability between diverse, loosely coupled components.

## 8. Architecture

This section describes the concrete components, DDS entities, topics, message types, and data flows that constitute the early prototype. A competing project can follow these steps to re-implement the system.

### 8.1 Core Components & Initialization

1.  **DomainParticipant & QoS Provider**
    - Create a single DDS participant:
      ```python
      participant = dds.DomainParticipant(0)
      ```
    - Load message definitions from `genesis_semantic_message.xml`:
      ```python
      type_provider = dds.QosProvider("genesis_semantic_message.xml")
      ```
    - For each message struct, obtain the DynamicData type:
      ```python
      agent_reg_type    = type_provider.type("genesis_lib", "genesis_agent_registration_announce")
      agent_reg_resp    = type_provider.type("genesis_lib", "genesis_agent_registration_assign")
      interface_reg     = type_provider.type("genesis_lib", "genesis_interface_registration_announce")
      interface_reg_resp= type_provider.type("genesis_lib", "genesis_interface_registration_assign")
      function_reg      = type_provider.type("genesis_lib", "genesis_function_registration_announce")
      function_reg_resp = type_provider.type("genesis_lib", "genesis_function_registration_assign")
      query_fn_list     = type_provider.type("genesis_lib", "query_genesis_function_list")
      fn_list_resp      = type_provider.type("genesis_lib", "genesis_function_list_response")
      ```

2.  **Topic & Entity Setup**
    - For each service, define a Topic, DataReader, and DataWriter:
      ```python
      # Example for agent registration
      agent_reg_topic = dds.DynamicData.Topic(participant, "AgentRegistrationTopic", agent_reg_type)
      agent_reg_reader= dds.DynamicData.DataReader(dds.Subscriber(participant), agent_reg_topic)
      agent_reg_resp_topic = dds.DynamicData.Topic(participant, "AgentRegistrationResponseTopic", agent_reg_resp)
      agent_reg_resp_writer= dds.DynamicData.DataWriter(dds.Publisher(participant), agent_reg_resp_topic)
      ```
    - Repeat for `InterfaceRegistrationTopic`, `FunctionRegistrationTopic`, and for `QueryFunctionListTopic` / `FunctionListResponseTopic`.

3.  **Registry Data Structures**
    - Maintain in-memory dictionaries and locks:
      ```python
      agent_registry     = {}  # agent_id -> metadata
      interface_registry = {}
      function_registry  = {}
      registry_lock      = threading.Lock()
      ```

### 8.2 Registration Flows

#### 8.2.1 Agent Registration

1.  An agent creates and writes a registration sample:
    ```python
    sample = dds.DynamicData(agent_reg_type)
    sample['message']        = "Agent description"
    sample['prefered_name']  = "agent_name"
    sample['default_capable'] = 1
    agent_reg_writer.write(sample)
    agent_reg_writer.flush()
    ```
2.  The ServiceRegistry's `Agent_RegistrationListener` picks up the sample:
    - In `on_data_available`, iterate `for data in reader.take_data(): threading.Thread(target=process_registration, args=(data,)).start()`.
    - In `process_registration(data)`:
      - Generate `agent_id = uuid.uuid4().int & 0xFFFFFFF`.
      - With `registry_lock`, store metadata in `agent_registry[agent_id]`.
      - Prepare a response sample:
        ```python
        resp = dds.DynamicData(agent_reg_resp)
        resp['bot_name']      = agent_id
        resp['classifier_id'] = determined_classifier_id
        agent_reg_resp_writer.write(resp)
        agent_reg_resp_writer.flush()
        ```
3.  The registering agent blocks on its DataReader for `AgentRegistrationResponseTopic`, then reads `data['bot_name']` and `data['classifier_id']` to complete registration.

#### 8.2.2 Interface Registration

1.  An interface writes to `InterfaceRegistrationTopic`:
    ```python
    sample = dds.DynamicData(interface_reg)
    sample['message']       = "Registering interface"
    sample['prefered_name'] = "Interface0"
    sample['interface_type']= 1
    sample['prefered_bot']  = "default"
    interface_reg_writer.write(sample)
    interface_reg_writer.flush()
    ```
2.  `Interface_RegistrationListener` in the registry:
    - Generates `interface_id`, resolves `prefered_bot_id` via `agent_registry`.
    - Writes a response sample on `InterfaceRegistrationResponseTopic`:
      ```python
      resp = dds.DynamicData(interface_reg_resp)
      resp['bot_name']         = interface_id
      resp['prefered_bot_id']  = prefered_bot_id
      interface_reg_resp_writer.write(resp)
      interface_reg_resp_writer.flush()
      ```
3.  The interface reads its assigned IDs and uses them for dynamic topic construction.

### 8.3 Dynamic Topic Naming & Messaging

1.  **Topic Construction**
    - After registration, each component knows its own numeric ID (`own_id`) and the target's ID (`target_id`).
    - Define per-component topics:
      ```python
      question_topic = dds.DynamicData.Topic(participant, f"QuestionTopic-{target_id}", question_type)
      answer_topic   = dds.DynamicData.Topic(participant, f"AnswerTopic-{own_id}",    answer_type)
      ```
2.  **DataWriters and DataReaders**
    - Create a DataWriter for `question_topic` and a DataReader for `answer_topic`.
    - Attach a listener to the answer DataReader to process incoming replies.

3.  **Message Exchange**
    ```python
    # Send question
    msg = dds.DynamicData(question_type)
    msg['message']   = user_text
    msg['sessionID'] = ctypes.c_int32(session).value
    msg['series']    = series_counter
    msg['target']    = target_id
    msg['source']    = own_id
    question_writer.write(msg)
    question_writer.flush()

    # Listener on answer_reader prints data['message'], resets flags on FINAL status.
    ```

### 8.4 Function Discovery

1.  **Query for functions**
    ```python
    q = dds.DynamicData(query_fn_list)
    q['calling_bot'] = own_id
    query_fn_list_writer.write(q)
    query_fn_list_writer.flush()
    ```
2.  **Registry's FunctionListQueryListener**
    - Reads `for data in reader.take_data()`.
    - Builds a list of `{name, description, id}` from `function_registry`.
    - Writes JSON payload:
      ```python
      resp = dds.DynamicData(fn_list_resp)
      resp['target_bot']           = calling_bot
      resp['function_list_short_JSON'] = json.dumps(list)
      fn_list_resp_writer.write(resp)
      fn_list_resp_writer.flush()
      ```
3.  **Client parsing**
    ```python
    for data in fn_list_reader.take_data():
        functions = json.loads(data['function_list_short_JSON'])
    ```

### 8.5 Function Registration & Invocation (Outline)

-  **Registration:** Function providers announce via `FunctionRegistrationTopic` using `genesis_function_registration_announce` and receive an assigned function ID.
-  **Invocation (Next Steps):** Components will write invocation requests to `FunctionTopic-{function_id}`, and providers will listen, execute, and respond on `FunctionAnswerTopic-{caller_id}`. This pattern follows the registration-response and dynamic topic conventions above.

---

With these detailed steps—covering participant setup, type loading, topic creation, listener patterns, data flows, and ID-based routing—a competing team could re-create the early prototype of the GENESIS framework from scratch. 