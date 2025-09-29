Active Modules Used By Triage/Run-All

These modules are invoked directly by the orchestrators in `run_scripts/` and must remain importable at their current top-level paths:

- Services (core)
  - `test_functions/calculator_service.py`
  - `test_functions/text_processor_service.py`
  - `test_functions/letter_counter_service.py`

- Agent Services (agent-to-agent tests)
  - `test_functions/weather_agent_service.py`
  - `test_functions/personal_assistant_service.py`

Notes
- Run scripts reference these via direct file paths and via `python -m test_functions.<module>`.
- If you move any of the above into subfolders, keep a top-level shim file that re-exports the implementation and preserves `if __name__ == "__main__"` entrypoints.
- After any reorg, always run: `python mcp/file_runner.py --enqueue triage --timeout 240 --wait` to verify.

