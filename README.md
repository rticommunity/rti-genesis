# GENESIS \- A Distributed AI Agent Framework

## Overview

GENESIS (Generative Networked System for Intelligent Services) is a Python library designed for building complex, distributed AI agent networks. It facilitates seamless communication, dynamic function discovery, and collaboration between heterogeneous AI agents, leveraging the power of **RTI Connext DDS** for real-time, reliable, and scalable interactions.

## Project Status

### Current Phase: Phase 5C - Comprehensive Chaining Tests (In Progress)

**Overall Progress: 75% Complete**

#### ✅ Completed Phases:
- **Phase 1-4**: Core framework, monitoring, and infrastructure (100% complete)
- **Phase 5A**: Weather Agent with LLM integration (100% complete)
- **Phase 5B**: Basic multi-agent communication (100% complete)

#### 🚧 In Progress:
- **Phase 5C**: Comprehensive chaining tests with agent-as-tool pattern

#### ❌ Remaining Work:
1. **Agent-as-Tool Pattern**: Agents must be injected as LLM tools (not just discovered)
2. **Complex Chain Testing**: 
   - Interface → Agent A → Agent B → Service → Function
   - Interface → Agent → Multiple Agents (parallel) → Multiple Services
   - Interface → Agent → Agent (context) → Agent → Service
3. **Third Specialized Agent**: Fashion/Travel agent for chain testing
4. **Performance Validation**: Latency, concurrency, and context preservation metrics

**Critical Requirement**: ALL final tests MUST use real APIs (OpenAI, OpenWeatherMap, etc.) with NO mock data.

See `PHASE_5_COMPREHENSIVE_CHECKLIST.md` for detailed requirements.

## Quick Start

### Prerequisites

Before setting up Genesis LIB, ensure you have:

1. **Python 3.10**
   - We recommend using `pyenv` to manage Python versions
   - Installation instructions for pyenv:
     ```bash
     # macOS
     brew install pyenv
     
     # Linux
     curl https://pyenv.run | bash
     
     # Add to your shell configuration
     echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
     echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
     echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
     
     # Install Python 3.10
     pyenv install 3.10.0
     pyenv global 3.10.0
     ```

2. **RTI Connext DDS 7.3.0 or greater**
   - Download from [RTI's website](https://support.rti.com/downloads)
   - Install in one of the following locations:
     - macOS: `/path/to/rti_connext_dds-7.3.0`
     - Linux: `/path/to/rti_connext_dds-7.3.0` or `$HOME/rti_connext_dds-7.3.0`
     - Windows: `C:\path\to\rti_connext_dds-7.3.0`

3. **API Keys**
   - OpenAI API Key (for GPT models)
   - Anthropic API Key (for Claude models)
   - Store these in your environment or `.env` file:
     ```bash
     export OPENAI_API_KEY="your_openai_api_key"
     export ANTHROPIC_API_KEY="your_anthropic_api_key"
     ```

### Quick Setup

The easiest way to set up Genesis LIB is to use the provided setup script:

```bash
# Clone the repository
git clone https://github.com/your-org/Genesis_LIB.git
cd Genesis_LIB

# Run the setup script
./setup.sh
```

The setup script will:
1. Create a Python virtual environment
2. Install all required dependencies
3. Configure RTI Connext DDS environment
4. Set up API keys
5. Install the package in development mode

### Try the Hello World Example

After setup, run the Hello World example to verify your installation:

```bash
# Run the Hello World example
cd examples/HelloWorld
./run_hello_world.sh
```

This will start a simple calculator service and agent that can perform basic arithmetic operations.

### Next Steps

Once you've verified your installation with the Hello World example, you can:
1. Explore the examples directory for more complex use cases
2. Read the detailed documentation below
3. Start building your own agents and services

The core purpose of GENESIS is to enable the creation of sophisticated multi-agent systems where different agents, potentially built using various AI frameworks (like LangChain, OpenAI's API, or native Python), can work together to solve problems that are beyond the capability of any single agent.

## Why an Agent-to-Agent Framework like GENESIS?

Modern AI applications often require the coordination of multiple specialized components:

* **LLMs:** For natural language understanding, generation, and reasoning.  
* **Planning Agents:** To decompose complex tasks.  
* **Perception Models:** To interpret sensory data.  
* **Domain-Specific Tools:** Databases, simulators, external APIs.

Connecting these components ad-hoc using simple methods like direct sockets or basic REST APIs quickly becomes complex and brittle. Key challenges include:

1. **Discovery:** How do agents find each other and the capabilities they offer?  
2. **Reliability:** How to ensure messages are delivered, especially in dynamic or unreliable networks?  
3. **Scalability:** How to handle communication efficiently as the number of agents and interactions grows?  
4. **Data Typing:** How to ensure data consistency between different agents?  
5. **Real-time Needs:** How to support low-latency interactions required for certain applications?  
6. **Heterogeneity:** How to integrate agents built with different technologies or frameworks?

GENESIS addresses these challenges by providing a structured framework built on DDS.

## Philosophy: Automated Agent Connection

GENESIS is built on the philosophy that agent networks should be self-organizing and self-configuring. Rather than requiring users to manually define connections between agents, GENESIS automates the entire process of agent discovery, connection, and collaboration.

### Key Principles

1. **Zero-Configuration Discovery:** Agents automatically discover each other through DDS without manual configuration of IPs/ports, adapting dynamically.  
2. **Self-Organizing Networks:** Connections form based on capabilities, allowing network topology to emerge organically without central orchestration.  
3. **Intelligent Function Matching:** Functions are classified and matched to requests dynamically, enabling agents to use newly available capabilities.  
4. **Automatic Load Balancing:** Multiple instances of functions are discovered, allowing requests to be distributed, adapting to provider availability.

### Genesis Wrapper: Seamless Integration

A key component of this automation philosophy is the planned **Genesis Wrapper** system. This system will allow existing agents to be integrated into Genesis *without any code changes*.

```
graph TD
    A[Existing Agent] --> W[Genesis Wrapper]
    W --> D[DDS Network]
    W --> F[Function Registry Integration]
    W --> M[Monitoring Integration]

    subgraph "Wrapper Internals"
        W --> I[Input Capture]
        W --> O[Output Capture]
        W --> T[Type Conversion]
        W --> S[Schema Generation]
    end
```

**How it Works:**

1. **Input/Output Capture:** Monitors agent streams to capture calls/responses.  
2. **Automatic Integration:** Handles all DDS communication transparently.  
3. **Schema Generation:** Analyzes I/O patterns to create DDS types and function descriptions.  
4. **Monitoring Integration:** Adds health/performance tracking automatically.

**Example Usage (Conceptual):**

```py
# Example of wrapping an existing agent (Conceptual)
from genesis_lib import GenesisWrapper

# Create wrapper for existing agent
wrapper = GenesisWrapper(
    agent=existing_agent,
    input_method="process_input",  # Method to capture inputs
    output_method="get_response",  # Method to capture outputs
    name="wrapped_agent"           # Name in Genesis network
)

# Start the wrapped agent
wrapper.start()
# Agent is now discoverable and usable within the Genesis network.
```

**Benefits:**

* **Zero-Code Integration:** Integrates legacy or existing systems quickly.  
* **Automatic Discovery:** Wrapped agents join and advertise functions seamlessly.  
* **Seamless Operation:** Preserves original agent behavior.  
* **Enhanced Capabilities:** Gains monitoring, load balancing potential, etc.

This wrapper system exemplifies Genesis's commitment to automation and ease of use.

### Example: Automated Connection Flow

```
sequenceDiagram
    participant A as New Agent
    participant N as Network (DDS)
    participant F as Function Providers
    participant O as Other Agents

    A->>N: Joins Network (Starts DDS Participant)
    N-->>A: Discovers Existing Agents/Functions (via DDS Discovery)
    A->>F: Subscribes to `FunctionCapability` Topic
    F-->>A: Receives Function Announcements
    A-)O: Uses RPC Client to Call Functions as Needed
    O-)A: Responds via RPC Reply
```

### Benefits of Automation

1. **Reduced Complexity:** Eliminates manual connection management.  
2. **Increased Reliability:** Automatic discovery and potential for reconnection.  
3. **Enhanced Scalability:** Easily add/remove agents and functions.  
4. **Improved Flexibility:** Adapt to changing requirements and network topology.

## System Architecture

GENESIS employs a modular architecture built upon RTI Connext DDS.

```
graph TD
    subgraph "Genesis Application Layer"
        I[Interface Agent] -- interacts --> PA[Primary Agent]
        PA -- chains --> SA[Specialized Agent]
        PA -- uses --> FR[Function Registry]
        SA -- uses --> FR
        I -- uses --> FR
        PA -- uses --> RPC_C[RPC Client]
        SA -- uses --> RPC_C
        I -- uses --> RPC_C
        FS[Function Service] -- uses --> RPC_S[RPC Service]
        FS -- registers --> FR

        subgraph "Base Classes"
            B_APP[GenesisApp] --> B_AGT[GenesisAgent]
            B_APP --> B_IF[GenesisInterface]
            B_APP --> B_RPC_S[GenesisRPCService]
            B_APP --> B_RPC_C[GenesisRPCClient]
            B_AGT --> B_MON_AGT[MonitoredAgent]
            B_IF --> B_MON_IF[MonitoredInterface]
            B_MON_AGT --> PA & SA & I & FS
            B_MON_IF --> I
        end
    end

    subgraph "Core Services / Concepts"
        FR[Function Registry]
        FC[Function Classifier]
        FM[Function Matcher]
        RPC_S[RPC Service]
        RPC_C[RPC Client]
        MON[Monitoring System]
    end

    subgraph "DDS Communication Layer"
        DDS[RTI Connext DDS]
        DDS -- Pub/Sub --> Discovery[Discovery Topics (e.g., FunctionCapability)]
        DDS -- Req/Rep --> RPC_Topics[RPC Topics (e.g., FunctionExecution)]
        DDS -- Pub/Sub --> Monitoring_Topics[Monitoring Topics (e.g., LifecycleEvent)]
    end

    Genesis_App_Layer -- utilizes --> Core_Services
    Core_Services -- built on --> DDS_Layer

    style B_APP fill:#f9f,stroke:#333,stroke-width:2px
    style B_AGT fill:#f9f,stroke:#333,stroke-width:2px
    style B_IF fill:#f9f,stroke:#333,stroke-width:2px
    style B_RPC_S fill:#f9f,stroke:#333,stroke-width:2px
    style B_RPC_C fill:#f9f,stroke:#333,stroke-width:2px
    style B_MON_AGT fill:#f9f,stroke:#333,stroke-width:2px
    style B_MON_IF fill:#f9f,stroke:#333,stroke-width:2px
    style FR fill:#ccf,stroke:#333,stroke-width:2px
    style FC fill:#ccf,stroke:#333,stroke-width:2px
    style FM fill:#ccf,stroke:#333,stroke-width:2px
    style RPC_S fill:#ccf,stroke:#333,stroke-width:2px
    style RPC_C fill:#ccf,stroke:#333,stroke-width:2px
    style MON fill:#ccf,stroke:#333,stroke-width:2px
    style DDS fill:#cfc,stroke:#333,stroke-width:2px
```

**Key Components:**

* **GenesisApp:** Foundational base class for DDS setup (Participant, Topics).  
* **GenesisAgent / MonitoredAgent:** Base classes for autonomous agents. `MonitoredAgent` adds automatic lifecycle/status reporting. Hosts `FunctionRegistry`, `FunctionClassifier`, `RPCClient`.  
* **GenesisInterface / MonitoredInterface:** Specialized agents for entry/exit points (UIs, bridges).  
* **GenesisRPCService:** Base class for discoverable function providers (services). Handles registration and request processing.  
* **GenesisRPCClient:** Base class for clients interacting with RPC services.  
* **Function Registry (`FunctionRegistry`):** Discovers `FunctionCapability` announcements via DDS and maintains a local cache. Resides within agents.  
* **Function Classifier/Matcher (`FunctionClassifier`, `FunctionMatcher`):** Components (often within agents) to intelligently select functions, potentially using LLMs.  
* **Monitoring System (`genesis_monitoring.py`, `genesis_web_monitor.py`):** Standalone applications subscribing to DDS monitoring topics for observation.  
* **DDS Communication Layer:** RTI Connext DDS providing transport for discovery, RPC, and monitoring.

**Interaction Flow:**

1. Agents/Services start, initialize DDS, begin discovery.  
2. Services (`GenesisRPCService`) publish `FunctionCapability` via DDS.  
3. Agents (`GenesisAgent`) discover capabilities via their `FunctionRegistry`.  
4. An Interface (`GenesisInterface`) or Agent receives input/task.  
5. The agent uses its `FunctionRegistry`, `FunctionClassifier`, and `FunctionMatcher` to identify needed functions.  
6. The `RPCClient` sends requests over DDS RPC topics if remote functions are needed.  
7. The target `RPCService` receives the request, executes, and sends a reply via DDS.  
8. `MonitoredAgent`/`MonitoredInterface` publish lifecycle, status, and log events to DDS Monitoring Topics.  
9. The Monitoring System subscribes to provide visibility.

## Internal Communication Identifiers

GENESIS components are identified by globally unique identifiers (GUIDs) automatically assigned by DDS (e.g., `0101f2a4a246e5cf70e2629680000002`). These GUIDs enable precise targeting and tracking:

* **Discovery:** Genesis logs GUIDs upon discovery:

```
FunctionCapability subscription matched with remote GUID: 0101f2a4a246e5cf70e2629680000002
FunctionCapability subscription matched with self GUID:   010193af524e12b65bd4c08980000002
```

* **Function Association:** Provider-client relationships are logged:

```
DEBUG: CLIENT side processing function_id=569fb375-1c98-40c7-ac12-c6f8ae9b3854,
       provider=0101f2a4a246e5cf70e2629680000002,
       client=010193af524e12b65bd4c08980000002
```

* **Benefits:** Unambiguous identification, availability tracking, clear function provider association, potential for identity-based access control.

## Key Features & "Special Sauce"

* **DDS-Powered Communication:** Utilizes RTI Connext DDS for:  
    
  * **Publish/Subscribe:** For discovery (`FunctionCapability`, `genesis_agent_registration_announce`), monitoring (`MonitoringEvent`, etc.), and data streaming.  
  * **Request/Reply (RPC):** For reliable remote procedure calls (`FunctionExecutionRequest`/`Reply`).  
  * **Automatic Discovery:** Built-in mechanism for agents/services to find each other.  
  * **Quality of Service (QoS):** Fine-grained control (reliability, durability, latency, etc.) configurable via XML profiles for different topics (e.g., reliable/durable discovery, reliable/volatile RPC, best-effort monitoring).  
  * **Real-time Performance:** Optimized for low-latency, high-throughput.  
  * **Platform Independence:** Supports various platforms (Genesis focuses on Python).


* **DDS Network Transport and Protocol Details:** GENESIS leverages DDS's transport flexibility:  
    
  * **UDPv4/UDPv6:** Default for LAN/WAN, efficient multicast discovery (port 7400), configurable RTPS reliability (heartbeats, ACKs).  
  * **Shared Memory:** Automatic zero-copy transport for inter-process communication on the same host (μs latency, high throughput).  
  * **TCP:** Option for WANs or firewall traversal (port 7400, configurable), supports TLS.  
  * **Automatic Selection:** DDS chooses the best transport based on endpoint location (SHMEM \-\> UDP \-\> TCP).  
  * **Network Usage:** Efficient CDR serialization, configurable batching, predictable discovery traffic overhead.


* **Dynamic Function Discovery & Injection:**  
    
  * Agents advertise Functions (`FunctionCapability` topic) with standardized schemas.  
  * Agents discover functions dynamically at runtime (`function_discovery.py`).  
  * Optional **LLM-based two-stage classification** (`agent_function_injection.md`) to quickly identify relevant functions before deeper processing.  
  * Discovered functions can be automatically "injected" into LLM prompts/contexts.


* **LLM Integration and AI Framework Support:**  
    
  * **Native Integrations:** Direct API support for OpenAI (GPT series), Anthropic (Claude series), and integration capabilities for Llama, Mistral, HuggingFace models (via local inference or API).  
  * **Optimized LLM Usage:**  
    * *Two-Stage Function Processing:* Use lightweight LLMs for initial classification and powerful LLMs for execution/reasoning.  
    * *Context Window Management:* Automatic token counting, truncation strategies, dynamic compression.  
    * *Hybrid Inference:* Combine local and remote models, potentially routing based on task complexity or cost.  
  * **AI Framework Compatibility:** Adapters and integrations planned/available for LangChain, AutoGen, LlamaIndex, HuggingFace Transformers. Custom agents integrated via the `GenesisWrapper`. Example LangChain integration:

```py
from genesis_lib.adapters import LangChainGenesisAdapter
# ... LangChain agent setup ...
genesis_agent = LangChainGenesisAdapter(
    agent_executor=executor, name="math_agent", description="Solves math problems",
    register_tools_as_functions=True # Expose LangChain tools as Genesis functions
)
await genesis_agent.run() # Agent joins Genesis network
```

  * **Deployment Options:** Supports Cloud APIs, Local Inference (ggml, ONNX, llama.cpp), Self-hosted APIs (TGI, vLLM), Hybrid, and Containerized deployments.


* **Agent-Framework Agnostic:** Designed to integrate agents regardless of implementation (Python/DDS required). Base classes provided, `GenesisWrapper` planned for zero-code integration.  
    
* **Built-in Monitoring:** `MonitoredAgent` publishes lifecycle, communication, status, and log events (`ComponentLifecycleEvent`, `ChainEvent`, `MonitoringEvent`, `LivelinessUpdate`, `LogMessage`) over DDS. Monitoring tools (`genesis_monitor.py`, `genesis_web_monitor.py`) provide visibility.  
    
* **Structured RPC Framework:** Base classes (`GenesisRPCService`, `GenesisRPCClient`) for robust RPC with schema validation (jsonschema), error handling, and request/reply management.

## Advantages Over Alternatives

| Feature | GENESIS (with DDS) | Direct Sockets | REST APIs | Message Queues (e.g., RabbitMQ/Kafka) | Agent Frameworks (LangChain, etc.) |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Discovery** | Automatic, built-in (DDS Discovery) | Manual config or separate service registry needed | Separate service registry needed | Broker handles connections, topics needed | Framework-specific, often limited |
| **Communication** | Pub/Sub, Req/Rep, Peer-to-Peer | Point-to-Point stream | Client-Server, Request-Response | Broker-mediated Pub/Sub, Queues | Often HTTP-based or proprietary |
| **Reliability** | Configurable (Best-Effort, Reliable) via DDS QoS | Manual implementation (ACKs, retries) needed | Based on underlying TCP, retries needed | Configurable (ACKs, persistence) | Framework-dependent, often basic |
| **Scalability** | High (DDS designed for large, dynamic systems) | Limited by connection count/management | Limited by server capacity, load balancers needed | High (designed for throughput) | Varies by framework, often limited |
| **Data Typing** | Strong (DDS IDL or Dynamic Types), Schema Validation | Raw bytes, manual serialization/validation needed | Typically JSON/XML, schema validation optional | Broker agnostic (bytes), client handles | Typically JSON-based, limited validation |
| **Real-time** | Yes (Low latency, high throughput) | Possible, depends on implementation | Generally higher latency (HTTP overhead) | Latency varies by broker/config | Generally not optimized for real-time |
| **QoS Control** | Extensive (Reliability, Durability, Latency, etc.) | None built-in | Limited (via HTTP headers, if supported) | Some (Persistence, ACKs) | Limited or non-existent |
| **Function Discovery** | Built-in with metadata, dynamic discovery | Must be implemented manually | Typically requires API documentation/registration | Requires custom implementation | Framework-specific, often limited |
| **Monitoring** | Comprehensive built-in (lifecycle, events, performance) | Manual implementation required | Often requires separate monitoring systems | Varies by broker, often basic | Framework-dependent, often limited |
| **Peer-to-Peer** | Native support | Possible, but discovery/connection management | Possible via complex patterns, not typical | Broker-mediated (not direct P2P) | Rarely supported natively |
| **Filtering** | Data-centric (Content/Time filters in DDS) | Application-level implementation required | Limited (API endpoint parameters) | Topic-based, some header filtering | Application-level implementation required |
| **Security** | Comprehensive (AuthN, AuthZ, Encrypt) via DDS Security | Manual implementation required | TLS/SSL encryption, app-level AuthN/AuthZ | Varies (TLS, SASL, ACLs) | Varies, often basic or external |

## Core Concepts & Technical Details

### Configuration Management

* **DDS Configuration (XML):** Primary method via QoS Profiles XML files defining QoS, resource limits, transports, discovery peers, and optionally types (`datamodel.xml`). Loaded by `GenesisApp`.  
* **Application Configuration:** Environment Variables (`NDDSHOME`, API keys), Config Files (YAML, .env using `python-dotenv`, etc.), Command-line Arguments.  
* **Genesis Component Configuration:** Constructor arguments, programmatic settings within the code.

### State Management

GENESIS is flexible; state is managed at the agent/service level:

* **Agent Internal State:** Managed within Python class instances (e.g., conversation history).  
* **Stateless Functions:** RPC Services often designed stateless for scalability.  
* **DDS for Shared State (Durability):** DDS Durability QoS (`TRANSIENT_LOCAL`, `PERSISTENT`) can share state (e.g., `FunctionCapability`, shared world model) across agents or with late joiners.  
* **External Databases/Stores:** Agents can integrate with external DBs for complex persistence.

### Error Handling and Resilience

Combines DDS features and application logic:

* **DDS Reliability QoS:** `RELIABLE` QoS handles transient network issues via retransmissions.  
* **DDS Liveliness QoS:** Detects unresponsive components via heartbeats, notifying participants. `LivelinessUpdate` topic provides visibility.  
* **Timeouts:** Configurable in `GenesisRPCClient`, DDS WaitSets, and DDS request-reply operations.  
* **Deadlines:** DDS Deadline QoS ensures periodic data flow.  
* **Application-Level Handling:** RPC replies include `success`/`error_message`. Use `try...except` blocks. Consider Circuit Breakers.  
* **Redundancy:** Multiple instances of services provide failover; DDS discovery finds all instances.  
* **Monitoring:** Helps identify failures via lifecycle events and logs.

### DDS Security and Access Control (DDS Native, not yet applied to GENESIS)

Leverages RTI Connext DDS Security for enterprise-grade protection:

* **Plugins:** Implements Authentication (X.509 certificates), Access Control (permissions documents), Encryption (AES-GCM), and Logging.

```xml
<!-- Example Security Config Snippet -->
<property>
    <value>
      <element>
        <name>dds.sec.auth.identity_ca</name>
        <value>file:///path/to/identity_ca.pem</value>
      </element>
      <!-- Other security properties: cert, key, permissions, governance -->
    </value>
</property>
```

* **Isolation:** DDS Domains provide network isolation. Secure Partitions and Topic-level rules offer finer control.  
* **Fine-Grained Access Control:** Role-based, group-based policies defined in XML permissions files.

```xml
<!-- Example Permissions Snippet -->
<permissions>
  <grant name="AgentRole_A">
    <subject_name>CN=SpecificAgent,O=MyOrg</subject_name>
    <allow_rule>
      <publish><topics><topic>CriticalData</topic></topics></publish>
      <subscribe><topics><topic>GeneralStatus</topic></topics></subscribe>
    </allow_rule>
  </grant>
</permissions>
```

* **Semantic Security Guardrails:** (Conceptual/Future) Middleware to monitor conversations and function calls for exploits, policy violations, or harmful content, complementing DDS transport security. Specialized components like `SemanticGuardian` could perform content analysis, enforce boundaries, validate I/O, and maintain adaptive trust scores. RTI aims to provide APIs for third-party integration here.  
* **Benefits:** Zero Trust Architecture, Compliance readiness, Defense in Depth, Secure Multi-Tenancy, Centralized Management.

### Performance Characteristics

Performance depends on DDS and application logic.

* **Latency:** DDS enables sub-millisecond latency (esp. SHMEM/UDP). Influenced by network, serialization, LLM inference, agent logic.  
* **Throughput:** DDS supports high throughput (millions msg/sec). Depends on message size, participants, processing, QoS.  
* **Scalability:** DDS scales to hundreds/thousands of participants. Function discovery scales with two-stage classification. Limited by network/discovery traffic.  
* **Resource Usage:** DDS resource usage configurable via QoS. Python usage depends on agent complexity.

## Lifelong Learning Through Dynamic Chaining

Genesis's dynamic function discovery and potential for automated chaining lay groundwork for lifelong learning systems. Agents can adapt and improve over time.

### Lifelong Learning Components (Conceptual)

```
graph TD
    A[Agent Network] --> B[Experience Collection]
    B --> C[Chain Optimization / Evolution]
    C --> D[Memory Management]
    D --> E[Performance Feedback]
    E --> A

    subgraph "Learning Loop"
        B --> F[RL Training / Strategy Update]
        F --> G[Chain Improvement / Pruning]
        G --> H[Knowledge Transfer / Storage]
        H --> B
    end
```

**Core Ideas:**

1. **Experience Collection:** Record which function chains were used, their inputs, outputs, and performance metrics.

```py
# Conceptual Experience Collector
class ExperienceCollector:
    def record_chain_execution(self, chain_details, result, metrics):
        # Store experience data (e.g., in memory, DB, or DDS topic)
        pass
```

2. **Chain Evolution/Optimization:** Use collected experiences (potentially with RL or other optimization techniques) to refine how chains are constructed or selected for future tasks.

```py
# Conceptual Chain Evolution
class ChainEvolution:
    def evolve_chain(self, query, context, historical_data):
        # Generate candidate chains, evaluate based on history, optimize selection
        pass
```

**Features Enabled:**

* **Knowledge Accumulation:** Learn from successes/failures, adapt to context.  
* **Transfer Learning:** Share effective patterns between agents or tasks.  
* **Adaptive Optimization:** Refine function selection, prompts, or strategies.  
* **System Evolution:** Improve overall system performance over time.

**Benefits:** Continuous improvement, knowledge preservation, adaptive intelligence, scalable learning across the network. This transforms Genesis from a static framework to potentially dynamic, evolving systems.

## Deployment and Operations

* **Environments:** Containers (Docker \- manage network/license access), VMs/Bare Metal, Cloud (configure security groups for DDS ports).  
* **DDS Configuration:** Manage via XML QoS Profiles. Set `NDDSHOME` environment variable.  
* **Networking:** Ensure firewalls allow DDS discovery (UDP multicast/unicast) and data traffic (UDP/TCP ports). Choose appropriate transports.  
* **Monitoring:** Use Genesis tools (`genesis_monitor.py`, web monitor) and RTI Tools (Admin Console, Monitor) for DDS-level inspection. Aggregate logs via `LogMessage` topic or standard logging.  
* **Operations:** Graceful shutdown is important. Manage updates carefully (especially type changes \- consider DDS X-Types). Scaling involves adding/removing instances (DDS handles discovery). Load balancing may need custom logic.

## Debugging and Troubleshooting

* **Genesis Monitoring:** High-level visibility via monitoring topics.  
* **Python Debugging:** Standard tools (`pdb`, IDEs) for single-component logic.  
* **Logging:** Crucial. Use built-in `LogMessage` topic for aggregation. Check Python and DDS log levels. Example log line indicating an issue:

```
2025-04-08 08:47:37,710 - FunctionCapabilityListener.4418720944 - ERROR - Error processing function capability: 'NoneType' object is not subscriptable
```

* **RTI DDS Tools:** *Admin Console* (visualize network, participants, topics, QoS mismatches), *Monitor* (performance metrics), *Wireshark* (DDS dissector).  
* **Common Issues:**  
  * *Discovery:* Domain IDs, firewall blocks, type consistency (`datamodel.xml`). Check Admin Console.  
  * *Communication:* Topic names, QoS compatibility (check Admin Console), serialization errors.  
  * *Performance:* Use RTI Monitor, profiling. Check QoS settings.  
  * *Resource Limits:* DDS entity creation failures (check logs/Admin Console).  
  * *Type Errors:* Debug data processing logic (like the log example above).  
  * *Timeouts:* Check DDS/application timeout settings if requests fail. Example log:

```
ERROR - Unexpected error in service: Timed out waiting for requests
Traceback (most recent call last):
  File "/Genesis-LIB/genesis_lib/rpc_service.py", line 140, in run
    requests = self.replier.receive_requests(max_wait=dds.Duration(3600))
```

* **Strategy:** Correlate information from application logs, Genesis monitoring, and RTI DDS tools.



*(Detailed instructions and examples needed here)*

## Future Development & Next Steps (Addressing Limitations)

Key areas for enhancement:

* **Function Chaining & Composition:** Standardized mechanisms for multi-step workflows.  
* **Asynchronous Function Execution:** Better support for long-running tasks (callbacks, async RPC).  
* **Enhanced Web Interface:** More features for monitoring, interaction, configuration.  
* **Advanced Security Implementation:** Fully implement DDS Security features with examples.  
* **Performance Optimizations:** Benchmarking, caching, serialization improvements (FlatBuffers/Protobuf?), QoS tuning.  
* **Distributed Memory/State Management:** Tools/patterns for sophisticated shared state beyond basic DDS durability.  
* **Expanded Agent Integrations:** More adapters (LangChain, AutoGen), finalize `GenesisWrapper`.  
* **Load Balancing:** Standardized client-side or dedicated load balancing strategies.  
* **Comprehensive Documentation & Tutorials:** More examples, use cases (security, deployment).  
* **Error Recovery Frameworks:** Standard patterns for circuit breakers, graceful degradation.  
* **Standardized Metrics Collection:** Define comprehensive metrics for analysis.  
* **Multi-Framework Interoperability:** Standard layer for connecting with agents from other frameworks (AutoGPT, etc.).

# Genesis LIB

Genesis LIB is a framework for building intelligent agents and services using RTI Connext DDS and modern AI capabilities.

## Prerequisites

Before setting up Genesis LIB, ensure you have the following installed:

1. **Python 3.10**
   - We recommend using `pyenv` to manage Python versions
   - Installation instructions for pyenv:
     ```bash
     # macOS
     brew install pyenv
     
     # Linux
     curl https://pyenv.run | bash
     
     # Add to your shell configuration
     echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
     echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
     echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
     
     # Install Python 3.10
     pyenv install 3.10.0
     pyenv global 3.10.0
     ```

2. **RTI Connext DDS 7.3.0 or greater**
   - Download from [RTI's website](https://www.rti.com/downloads)
   - Install in one of the following locations:
     - macOS: `/path/to/rti_connext_dds-7.3.0`
     - Linux: `/path/to/rti_connext_dds-7.3.0` or `$HOME/rti_connext_dds-7.3.0`
     - Windows: `C:\path\to\rti_connext_dds-7.3.0`

3. **API Keys**
   - OpenAI API Key (for GPT models)
   - Anthropic API Key (for Claude models)
   - Store these in your environment or `.env` file:
     ```bash
     export OPENAI_API_KEY="your_openai_api_key"
     export ANTHROPIC_API_KEY="your_anthropic_api_key"
     ```

## Quick Setup

The easiest way to set up Genesis LIB is to use the provided setup script:

```bash
# Clone the repository
git clone https://github.com/your-org/Genesis_LIB.git
cd Genesis_LIB

# Run the setup script
./setup.sh
```

The setup script will:
1. Create a Python virtual environment
2. Install all required dependencies
3. Configure RTI Connext DDS environment
4. Set up API keys
5. Install the package in development mode

## Manual Setup

If you prefer to set up manually:

```bash
# Create and activate virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Set up RTI Connext DDS environment
# The setup script will help you with this, or you can manually:
export NDDSHOME="/path/to/rti_connext_dds-7.3.0"
source $NDDSHOME/resource/scripts/rtisetenv_<arch>.bash
```

## Environment Variables

The following environment variables are important for Genesis LIB:

- `NDDSHOME`: Path to RTI Connext DDS installation
- `PYTHONPATH`: Should include RTI Connext DDS Python libraries
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key

## Running Examples

After setup, you can run the examples:

```bash
# Run the Hello World example
cd examples/HelloWorld
./run_hello_world.sh
```

## Development

For development, we recommend:

1. Using `pyenv` to manage Python versions
2. Using a virtual environment
3. Installing in development mode (`pip install -e .`)
4. Running tests with pytest:
   ```bash
   pytest tests/
   ```

## Troubleshooting

Common issues and solutions:

1. **RTI Connext DDS not found**
   - Ensure RTI Connext DDS 7.3.0 or greater is installed
   - Verify the installation path is correct
   - Check that the environment script exists

2. **Python version issues**
   - Use `pyenv` to manage Python versions
   - Ensure Python 3.10 is installed and active

3. **API Key issues**
   - Verify API keys are set in environment or `.env` file
   - Check for any placeholder values

## Support

For support, please:
1. Check the troubleshooting section
2. Review the documentation
3. Open an issue on GitHub

## License

[Your License Here]
