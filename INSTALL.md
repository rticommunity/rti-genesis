Genesis-LIB Local Installation Guide (RC1)

Prerequisites
- macOS or Linux
- Python 3.10.x
- RTI Connext DDS installed
  - Set NDDSHOME to your install, e.g. /Applications/rti_connext_dds-7.3.0
  - Ensure $NDDSHOME/bin/rtiddsspy exists
- API keys (optional tests): OPENAI_API_KEY, ANTHROPIC_API_KEY

Quick Start (local pip install)
1) Create and activate a clean venv
   python3.10 -m venv .venv
   source .venv/bin/activate

2) Install package locally
   pip install --upgrade pip
   pip install .

3) Verify installation
   python -c "import genesis_lib; print('OK:', genesis_lib.__file__)"

4) Configure DDS spy QoS (already included in repo)
   The test runner uses spy_transient.xml at the project root:
   Genesis_LIB/spy_transient.xml

5) Set DDS environment (required for DDS-based tests)
   export NDDSHOME=/Applications/rti_connext_dds-7.3.0   # adjust for your install
   test -x "$NDDSHOME/bin/rtiddsspy" && echo OK || echo Missing

6) Optional: run tests (venv must be active and NDDSHOME set)
   cd Genesis_LIB/tests
   ./run_triage_suite.sh        # fast fail/diagnostics
   ./run_all_tests.sh           # full suite

Console Entrypoints
- Monitoring console (DDS log/monitor feed):
  python -c "from genesis_lib.genesis_monitoring import main; main()"

Environment Notes
- You must activate the root project venv (.venv) before running tests. The test runner no longer auto-activates any venv.
- NDDSHOME must be set; rtiddsspy is used by tests and diagnostics.
- OPENAI_API_KEY and ANTHROPIC_API_KEY are optional; tests that require them are skipped when absent.

Troubleshooting
- QoS mismatch in spy logs:
  Ensure spy_transient.xml is present and being used with -qosFile/-qosProfile.
- Python version errors:
  Use Python 3.10.x; the provided tests/venv is pinned to 3.10.


