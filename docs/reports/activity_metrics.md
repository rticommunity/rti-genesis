# Repository Activity Metrics (2025-08-28)

## Overall

- Commits: 142
- Contributors: 5
- Top Contributors:
  - 102	Jason
  -     23	sploithunter
  -     14	Gianpiero Napoli
  -      2	rtidgreenberg
  -      1	Jason Upchurch
- Files changed (numstat rows): 1005
- Additions: 229626  |  Deletions: 139014
- Timeline: 2025-04-06 → 2025-08-27

## Monthly Commits (all paths)

- 2025-04: 28
- 2025-05: 69
- 2025-06: 20
- 2025-07: 6
- 2025-08: 19

## Current LOC Snapshot

- genesis_lib: ~14214 lines (rough count of code/text files)
- examples: ~7236 lines (rough count of code/text files)
- docs: ~1976 lines (rough count of code/text files)

## Area Breakdowns

### Service Registry
- Commits: 30
- Files changed (numstat rows): 57
- Additions: 6043  |  Deletions: 1907
- Contributors: 0
- Timeline: 2025-04-06 → 2025-08-20
- Current LOC in area: ~4136
- Top Files by Churn (adds+deletes):
  - genesis_lib/openai_genesis_agent.py: +2140/-554
  - genesis_lib/enhanced_service_base.py: +1383/-966
  - genesis_lib/function_discovery.py: +1345/-278
  - genesis_lib/rpc_service.py: +389/-26
  - genesis_lib/rpc_client.py: +355/-59
  - genesis_lib/config/datamodel.xml: +274/-24
  - genesis_lib/datamodel.py: +157/-0
- Recent Commits:
  - 2fd4163|2025-08-20|sploithunter|feat: enhance 3D graph visualization with improved activity tracking
  - b3e6da7|2025-08-20|sploithunter|feat: implement interface abstraction with graph monitoring and visualization
  - c32c874|2025-07-11|sploithunter|feat: Complete Genesis memory subsystem implementation
  - ccec36f|2025-06-12|sploithunter|Unified monitoring system implementation and comprehensive plan - Added SERVICE component type (value 4) to COMPONENT_TYPE enum in datamodel.xml - Fixed enhanced_service_base.py to use SERVICE component type - Added missing publish_monitoring_event method to MonitoredAgent - Fixed OpenAIGenesisAgent monitoring event publishing - Updated test_monitoring.py to handle new component types - All tests now pass (12/12) - Created unified GraphMonitor class - Added comprehensive monitoring documentation - Implemented publisher-first development plan with RTI DDS Spy validation
  - 55e09d1|2025-06-06|Jason|feat: Complete agent-to-agent communication fix and clean demo mode
  - 1438ac7|2025-06-06|Jason|🎉 Implement @genesis_tool Auto-Discovery System - Phase 1 Complete - Zero-Boilerplate Tool Development Achieved! Enhanced @genesis_tool decorator with automatic schema generation, new schema_generators.py with multi-LLM support, integrated auto-discovery into OpenAIGenesisAgent, universal tool injection system. WeatherAgent rewritten using decorators - 200+ lines simpler. All tests passing including agent-to-agent communication with 60s timeout.
  - 789c086|2025-06-06|Jason|feat: Major Genesis enhancements - agent-to-agent communication, internal tools, built-in tracing. Universal agent schema eliminates manual tool definitions. WeatherAgent demonstrates internal tools with memory. Enhanced tracing built into OpenAIGenesisAgent base class. Comprehensive testing with DDS monitoring. All regression tests pass (12/12).
  - 50309dd|2025-06-02|Jason|Phase 5: Complete Multi-Agent System Implementation with Agent-as-Tool Pattern - Enhanced OpenAIGenesisAgent with agent communication and tool conversion, PersonalAssistant agent with automatic service discovery, Interactive CLI with proper Genesis patterns, Fixed critical connection management in MonitoredInterface, Complete working examples/MultiAgentV2/ system with interactive demo, All regression tests pass and interactive demo confirmed working
  - 9d8c77f|2025-05-27|Jason|feat: Complete Phase 4 - Graph Connectivity Validation & Multi-Agent Infrastructure - Added graph connectivity validation with NetworkX topology analysis - Enhanced monitoring with asynchronous service discovery - Added real weather agent and agent classification system - Created comprehensive test suite for topology validation - Fixed edge discovery events and component ID consistency - Added multi-agent test infrastructure and documentation updates
  - 6098e05|2025-05-12|Jason|Prevent service-to-service discovery: Modified FunctionRegistry to prevent services from creating DataReaders for FunctionCapability topic, ensuring services remain non-agentic. Added limited_mesh_test.sh to verify service isolation.
  - 4858512|2025-05-09|Jason|feat: Enhance ExampleInterface, logging, comments, and tests. This commit introduces a new example in examples/ExampleInterface showcasing a full CLI -> Agent -> Service pipeline, with run_example.sh, logging, and README. Key changes include: Added examples/ExampleInterface/ contents; Improved commenting/logging in examples; Addressed AttributeError in example_service.py; Updated run_scripts/ including run_all_tests.sh and new utilities; General code/logging/comment refinements in genesis_lib and scripts; Deleted run_scripts/start_services_and_agent.py.
  - 59c8d2f|2025-05-08|Jason|Fix: Correct FunctionRegistry listener and dependencies
  - 2d35868|2025-05-08|Jason|docs: Enhance function discovery documentation and cleanup DDS imports - Added detailed Function Calling Mechanism section to event_driven_function_discovery_plan.md documenting roles of function_id (UUID), provider_id (GUID), and service_name, with examples of function caching and RPC call flow. Removed unused DDS import from openai_genesis_agent.py as DDS functionality is handled by base classes.
  - fad1c8d|2025-05-08|Jason|Baseline before event-driven function discovery implementation - Added plan doc, modified core files, updated tests
  - c3bfb2c|2025-05-06|Jason|Added comprehensive documentation to Genesis framework components and test suite

### Simulation Integration
- Commits: 28
- Files changed (numstat rows): 52
- Additions: 7009  |  Deletions: 2430
- Contributors: 0
- Timeline: 2025-04-06 → 2025-08-27
- Current LOC in area: ~4550
- Top Files by Churn (adds+deletes):
  - genesis_lib/monitored_agent.py: +2450/-1617
  - genesis_lib/monitored_interface.py: +1170/-808
  - genesis_lib/web/static/orbital_viewer.js: +1176/-0
  - genesis_lib/graph_state.py: +688/-3
  - genesis_lib/graph_monitoring.py: +279/-0
  - genesis_lib/web/socketio_graph_bridge.py: +225/-2
  - genesis_lib/web/static/reference.js: +215/-0
  - examples/GraphInterface/server.py: +203/-0
  - examples/DroneGraphDemo/drones_radar_agent.py: +150/-0
  - genesis_lib/web/graph_viewer.py: +114/-0
- Recent Commits:
  - 177c7a5|2025-08-27|sploithunter|tests: stabilize math interface test; remove stdbuf injection on macOS; relax spy grep for wrapped lines
  - a94512d|2025-08-27|sploithunter|feat: Add DroneGraphDemo example and enhance agent isolation testing
  - e1c4199|2025-08-25|rtidgreenberg|add genesis lib path (#7)
  - d7b10e4|2025-08-21|sploithunter|feat: comprehensive interface abstraction system with graph viewer and testing
  - 67fac7e|2025-08-21|sploithunter|feat: implement subtractive visualization with node/edge removal support
  - 2fd4163|2025-08-20|sploithunter|feat: enhance 3D graph visualization with improved activity tracking
  - b3e6da7|2025-08-20|sploithunter|feat: implement interface abstraction with graph monitoring and visualization
  - c32c874|2025-07-11|sploithunter|feat: Complete Genesis memory subsystem implementation
  - ccec36f|2025-06-12|sploithunter|Unified monitoring system implementation and comprehensive plan - Added SERVICE component type (value 4) to COMPONENT_TYPE enum in datamodel.xml - Fixed enhanced_service_base.py to use SERVICE component type - Added missing publish_monitoring_event method to MonitoredAgent - Fixed OpenAIGenesisAgent monitoring event publishing - Updated test_monitoring.py to handle new component types - All tests now pass (12/12) - Created unified GraphMonitor class - Added comprehensive monitoring documentation - Implemented publisher-first development plan with RTI DDS Spy validation
  - 50309dd|2025-06-02|Jason|Phase 5: Complete Multi-Agent System Implementation with Agent-as-Tool Pattern - Enhanced OpenAIGenesisAgent with agent communication and tool conversion, PersonalAssistant agent with automatic service discovery, Interactive CLI with proper Genesis patterns, Fixed critical connection management in MonitoredInterface, Complete working examples/MultiAgentV2/ system with interactive demo, All regression tests pass and interactive demo confirmed working
  - 9d8c77f|2025-05-27|Jason|feat: Complete Phase 4 - Graph Connectivity Validation & Multi-Agent Infrastructure - Added graph connectivity validation with NetworkX topology analysis - Enhanced monitoring with asynchronous service discovery - Added real weather agent and agent classification system - Created comprehensive test suite for topology validation - Fixed edge discovery events and component ID consistency - Added multi-agent test infrastructure and documentation updates
  - 4858512|2025-05-09|Jason|feat: Enhance ExampleInterface, logging, comments, and tests. This commit introduces a new example in examples/ExampleInterface showcasing a full CLI -> Agent -> Service pipeline, with run_example.sh, logging, and README. Key changes include: Added examples/ExampleInterface/ contents; Improved commenting/logging in examples; Addressed AttributeError in example_service.py; Updated run_scripts/ including run_all_tests.sh and new utilities; General code/logging/comment refinements in genesis_lib and scripts; Deleted run_scripts/start_services_and_agent.py.
  - 67d77ab|2025-05-06|Jason|Update library documentation and data model: - Add comprehensive library descriptions to interface and monitored interface classes - Update copyright statements - Minor modifications to data model for future work - All tests passing
  - 5b62d87|2025-05-05|Jason|Refactor: Centralize chain event publishing in MonitoredAgent and update OpenAIGenesisAgent to use helper methods
  - f7c3926|2025-05-05|Jason|feat: Implement event-driven agent discovery using callbacks - Added callback mechanism to RegistrationListener for agent discovery/departure. Modified GenesisInterface/MonitoredInterface to use callbacks, added connect_to_agent, removed wait_for_agent. Refactored test interface.
