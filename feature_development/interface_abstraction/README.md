# Interface Abstraction Initiative

Goal: decouple UIs from DDS by centralizing graph construction in the Genesis library behind a `GraphService`, using NetworkX for the in-process model and Cytoscape.js for web visualization.

- Plan: see `plan.md`
- Prototypes: see `prototypes/`
- Tests: see `tests/`

Run tests:
```bash
./run_tests.sh
```


(venv) jason@RTI-RTI-11516 Genesis_LIB % ./feature_development/interface_abstraction/start_topology.sh --agents 10 --services 20 --interfaces 1 -t 180 --force --extra-agent-cmd "python examples/MultiAgent/agents/personal_assistant.py" --extra-agent-cmd "python -m test_functions.weather_agent_service" --interface-question "What is the weather in London, England?" --interface-question "What is 123 plus 456?"

  HOST=0.0.0.0 PORT=5000 python3 feature_development/interface_abstraction/viewer/server.py | cat