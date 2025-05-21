# AGENTS.md: Contributor Guide for Genesis LIB

This guide provides tips and instructions for contributors and automated agents working on the Genesis LIB project.

## Dev Environment Tips
- **Python Version**: Ensure you are using Python 3.10. We recommend `pyenv` for managing Python versions.
  ```bash
  # Example: Install and set Python 3.10
  pyenv install 3.10.0
  pyenv global 3.10.0
  python --version 
  ```
- **RTI Connext DDS**: Version 7.3.0 or greater is required. Install it in a standard location (e.g., `/path/to/rti_connext_dds-7.3.0` on macOS/Linux or `$HOME/rti_connext_dds-7.3.0` on Linux, `C:\path\to\rti_connext_dds-7.3.0` on Windows).
- **Quick Setup**: The `setup.sh` script is the fastest way to get started. It handles virtual environment creation, dependency installation, and initial configuration.
  ```bash
  # From the project root
  ./setup.sh
  ```
- **Manual Virtual Environment & Dependencies**: If not using `setup.sh`:
  ```bash
  # From the project root
  # Create and activate virtual environment
  python -m venv venv
  source venv/bin/activate  # Unix/macOS
  # .\venv\Scripts\activate    # Windows

  # Install dependencies
  pip install -r requirements.txt
  pip install -e . # Install Genesis LIB in editable mode
  ```
- **API Keys**: Set your OpenAI and Anthropic API keys as environment variables:
  ```bash
  export OPENAI_API_KEY="your_openai_api_key"
  export ANTHROPIC_API_KEY="your_anthropic_api_key"
  ```
- **Project Root**: Always operate from the root of the `Genesis_LIB` repository.
- **Exploring Code**: Key directories include:
    - `genesis_lib/`: Core library.
    - `examples/`: Usage examples.
    - `test_functions/`: Contains some test logic, but tests are typically run via scripts in `run_scripts/`.
    - `run_scripts/`: Contains scripts for running tests and examples.
    - `docs/`: Project documentation.

## Testing Instructions
- **Comprehensive Test Suite**: The primary method for running all tests is the `run_all_tests.sh` script located in the `run_scripts/` directory. This script executes a sequence of individual test scripts and checks for overall success.
  ```bash
  # From the project root
  ./run_scripts/run_all_tests.sh
  ```
  - This script **must be run before and after any modifications to the code** to ensure the integrity of the codebase.
  - The script manages timeouts, logging (results in `logs/` directory), and cleanup for the tests it runs. Consult its output and the generated logs for detailed results.

- **Understanding the Test Suite**: The `run_all_tests.sh` script orchestrates various tests by calling other shell and Python scripts. These tests cover:
    - Core framework functionality (function discovery, RPC, agent interactions).
    - Specific service behaviors.
    - DDS-specific aspects like durability and communication.
    - Monitoring and logging capabilities.

- **Running Individual Test Scripts**: While `run_all_tests.sh` is the main entry point for comprehensive testing, it internally calls individual test scripts (e.g., `run_math.sh`, `run_simple_agent.sh`, etc., mostly found in `run_scripts/`). If `run_all_tests.sh` reports a failure in a specific sub-script, you might run that individual script for focused debugging. For example:
  ```bash
  # From the project root
  ./run_scripts/run_math.sh 
  ```
  However, for validating overall changes, always rely on the full `run_all_tests.sh`.

- **Test Before Commit/Merge**: Ensure `./run_scripts/run_all_tests.sh` completes successfully before committing changes or creating/merging pull requests. The goal is a consistently green test suite.

- **Adding/Updating Tests**: For any code you change or add, ensure it is covered by existing tests. If new functionality is added, new test scripts (callable by `run_all_tests.sh` or as standalone checks) should be created and placed appropriately (e.g., in `run_scripts/` or `test_functions/` if they are Python-based tests called by a script).

- **Linting**: Ensure your Python code adheres to PEP 8. Consider using a linter like Flake8 or Pylint locally. (If project-specific linting commands are established, they should be added here).

## Contribution Guidelines (PRs)
- **Branching**: Create a new branch for your feature or bug fix (e.g., `feature/my-new-feature` or `fix/bug-description`).
- **Commit Messages**: Write clear, concise, and descriptive commit messages. Consider a conventional format if adopted by the team (e.g., `feat: add new agent capability`).
- **Title Format for PRs**: Use a clear and descriptive title, possibly prefixed with the scope. Suggestion: `[<scope>] <Brief description of change>` (e.g., `[CoreLib] Fix message serialization issue` or `[Docs] Update AGENTS.md with testing details`).
- **Documentation**: If your changes affect behavior, add new features, or alter existing interfaces, update relevant documentation (e.g., `README.md`, `library-comprehensive.md`, docstrings within the code, or this `AGENTS.md` file).
- **Code Review**: All PRs should be reviewed by at least one other contributor before merging.
- **Keep it Focused**: Aim for PRs that address a single issue or implement a single, cohesive feature.

---
This document is intended to be a living guide. Please update it if you find outdated information or identify areas for improvement. 