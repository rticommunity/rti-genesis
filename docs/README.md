# Genesis Framework Documentation

## User Guides

Essential documentation for using the Genesis framework:

### Configuration & Setup
- **[DDS Configuration](user-guides/DDS_CONFIGURATION.md)** - Configure RTI Connext DDS for Genesis
- **[Genesis Topics Reference](user-guides/GENESIS_TOPICS.md)** - DDS topics and data types reference

### Core Concepts
- **[Genesis API Overview](user-guides/genesis_api_overview.md)** - High-level API and architectural overview
- **[Genesis LIB Explorer](user-guides/Genesis_LIB_Explorer.md)** - Fast reference for contributors and agents

### Function System
- **[Function Service Guide](user-guides/function_service_guide.md)** - Creating and using function services
- **[Genesis Function RPC](user-guides/genesis_function_rpc.md)** - Detailed RPC system explanation
- **[Function Call Flow](user-guides/function_call_flow.md)** - Agent-as-Tool pattern and call flows

### Monitoring & Capabilities
- **[Monitoring Guide](user-guides/V2_MONITORING_USAGE.md)** - Using the monitoring system
- **[User Capabilities Guide](user-guides/USER_CAPABILITIES_GUIDE.md)** - Configuring agent capabilities

## Architecture Documentation

Internal architecture documentation for contributors and advanced developers:

### Core Architecture
- **[Architecture Overview](architecture/architecture.md)** - High-level system architecture
- **[Architecture Detailed](architecture/architecture_detailed.md)** - Detailed architectural deep-dive
- **[Monitoring System](architecture/monitoring_system.md)** - Monitoring system design and implementation

### Agent System
- **[Agent Architecture Quick Reference](architecture/AGENT_ARCHITECTURE_QUICK_REFERENCE.md)** - Agent class hierarchy and design patterns
- **[Capability System Architecture](architecture/CAPABILITY_SYSTEM_ARCHITECTURE.md)** - Agent capability system design

### Function & Discovery
- **[Function Discovery](architecture/FUNCTION_DISCOVERY.md)** - Function discovery and registration architecture

### LLM Integration
- **[Multi-Provider Architecture](architecture/MULTI_PROVIDER_ARCHITECTURE.md)** - LLM provider abstraction design
- **[New Provider Guide](architecture/NEW_PROVIDER_GUIDE.md)** - Adding new LLM providers

### Advanced Topics
- **[Memory Architecture](architecture/memory_architecture.md)** - External memory systems for LLM agents

## Reference Documentation

Technical references for RTI DDS and Genesis internals:

- **[RTI 7.3 RPC API](reference/RTI_7.3_RPC.md)** - RTI Connext RPC API documentation
- **[DDS GUID Identification](reference/dds_guid_identification.md)** - Client and provider ID identification
- **[Sequence Diagram](reference/sequenceDiagram.mmd)** - Flow diagram (also embedded in guides)

## Getting Started

- **[README](../README.md)** - Overview and introduction
- **[Quick Start](../QUICKSTART.md)** - Get up and running quickly
- **[Installation](../INSTALL.md)** - Installation instructions

## Examples

See the `examples/` directory for practical examples:
- `HelloWorld/` - Minimal agent example
- `ExampleInterface/` - Basic interface usage
- `MultiAgent/` - Multi-agent system with routing
- `GraphInterface/` - Combined chat + visualization
- `StandaloneGraphViewer/` - Pure network visualization

## Testing

See the `tests/` directory for test suites and stress testing tools:
- `tests/active/` - Active test suite
- `tests/stress/` - Stress testing and topology tools
