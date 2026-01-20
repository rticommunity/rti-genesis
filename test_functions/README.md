# Test Functions: Structure and Usage

This directory contains Python services, agents, clients, and focused tests that are invoked by the orchestrators in `run_scripts/`.

The goal is to make it clear which files are critical to the main test flows versus auxiliary or development-focused utilities. For now, files remain at the top level to preserve `python -m test_functions.<module>` entry points used by runner scripts.

## Categories

- Services (core, do not remove):
  - `calculator_service.py`: Arithmetic RPC service used across smoke, pipeline, and durability tests
  - `text_processor_service.py`: Text RPC service used by simple agent/client flows
  - `letter_counter_service.py`: Simple RPC service used by function tests

- Agents and agent-services (test/demo specific):
  - `weather_agent_service.py`: Specialized agent service for multi-agent tests
  - `personal_assistant_service.py`: Agent service used in agent-to-agent scenarios
  - `weather_agent.py`: Agent used by comprehensive scenarios

- Clients and tools:
  - `calculator_client.py`, `text_processor_client.py`: Direct RPC clients for smoke testing

- Focused tests (invoked by orchestrators or for targeted debugging):
  - `test_same_process_agents.py`, `test_monitoring_*`, `test_graph_connectivity_*`, `test_agent_*`, etc.

- Debug/demo/legacy (safe to run locally, not part of CI triage or all-tests by default):
  - `debug_*`, `drone_function_service.py`, selected shell demos

## Critical Modules Referenced by Runners

Referenced from `run_scripts/` via direct path or `python -m`:
- `calculator_service.py`
- `text_processor_service.py`
- `letter_counter_service.py`
- `weather_agent.py` (comprehensive scenario)

Please avoid renaming or relocating these without updating all runner scripts. If a reorg is desired, we can add thin compatibility wrappers at the top-level (e.g., `calculator_service.py` that imports from `test_functions.services.calculator_service`) to keep `python -m test_functions.calculator_service` working.

## Notes

- Python 3.10 is required for running these scripts.
- DDS: Ensure `NDDSHOME` points to a valid RTI Connext DDS installation when running tests that communicate via DDS.
- Set `OPENAI_API_KEY` for agent scenarios that require LLMs.


---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
