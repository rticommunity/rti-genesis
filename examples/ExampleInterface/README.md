# Example Interface, Agent, and Service Pipeline

This example demonstrates a complete pipeline involving a command-line interface (CLI), an AI agent, and a backend service, all interacting through the Genesis framework.

## Purpose

The primary goal of this example is to showcase:
1.  **Service Creation**: How to create a simple service (`CalculatorService`) using `MonitoredService` with functions exposed via the `@genesis_function` decorator.
2.  **Agent Implementation**: How to build a basic agent (`SimpleGenesisAgent`) derived from `OpenAIGenesisAgent` that can be discovered and communicated with.
3.  **Interface Interaction**: How to use a `MonitoredInterface` (`SimpleGenesisInterfaceCLI`) to discover available agents, connect to one, and send requests.
4.  **Orchestration**: How to manage these components using a shell script (`run_example.sh`) that handles backgrounding processes, logging, and graceful shutdown.
5.  **Basic RPC**: How an agent (conceptually, as this agent is simple) would call a service.

## Components

The example consists of the following key files:

*   `example_service.py`:
    *   Implements `CalculatorService`, which offers basic arithmetic operations (`add`, `subtract`, `multiply`, `divide`).
    *   Extends `MonitoredService` for automatic function registration and discovery.
    *   Includes custom exceptions for operations like division by zero.
*   `example_agent.py`:
    *   Implements `SimpleGenesisAgent`, a basic agent built on `OpenAIGenesisAgent`.
    *   This agent is discoverable by the Genesis interface. While this specific agent doesn\'t have complex logic to call the `CalculatorService` based on natural language, it\'s set up to receive messages. A more advanced version would parse these messages and interact with services like the `CalculatorService`.
*   `example_interface.py`:
    *   Implements `SimpleGenesisInterfaceCLI`, a command-line tool.
    *   It discovers available agents (like `SimpleGenesisAgent`).
    *   Allows the user to select an agent to connect to.
    *   Sends user input as messages to the selected agent and displays the agent\'s responses.
*   `run_example.sh`:
    *   A shell script that automates the startup and shutdown of the example.
    *   Creates a `logs/` directory for storing service and agent logs.
    *   Starts `example_service.py` and `example_agent.py` in the background, redirecting their output to log files.
    *   Starts `example_interface.py` in the foreground for user interaction.
    *   Handles `Ctrl+C` (SIGINT) and other termination signals for graceful cleanup of background processes.
*   `logs/` (created by `run_example.sh`):
    *   `agent.log`: Contains the standard output and error streams from `example_agent.py`.
    *   `service.log`: Contains the standard output and error streams from `example_service.py`.

## How to Run

1.  **Prerequisites**:
    *   Ensure Python 3.x is installed.
    *   The Genesis LIB and its dependencies must be installed (typically via a `setup.sh` script or `pip install` from the root of the Genesis_LIB project).
    *   Ensure your environment is configured for Genesis LIB (e.g., any necessary RTI Connext DDS environment variables like `NDDSHOME` are set if DDS is the transport).

2.  **Make the script executable** (if you haven\'t already):
    ```bash
    chmod +x run_example.sh
    ```

3.  **Run the example**:
    ```bash
    ./run_example.sh
    ```

## Expected Functionality

1.  The `run_example.sh` script will first create a `logs` directory within `examples/ExampleInterface/`.
2.  It will then start the `CalculatorService` in the background. Its logs will go to `logs/service.log`.
3.  Next, it will start the `SimpleGenesisAgent` in the background. Its logs will go to `logs/agent.log`.
4.  The script will pause for a few seconds to allow the service and agent to initialize and announce themselves on the network (e.g., via DDS discovery).
5.  Finally, the `SimpleGenesisInterfaceCLI` will start in the foreground.
6.  The interface will print "Waiting for any agent(s) to become available..."
7.  Once agents are discovered, it will list them, for example:
    ```
    Available agents:
      1. Name: \'SimpleGenesisAgentForTheWin\', ID: \'some-unique-id\', Service: \'SimpleGenesisAgentForTheWinService\'
    ```
8.  You will be prompted to "Select agent by number:". Enter the number corresponding to `SimpleGenesisAgentForTheWin`.
9.  Upon successful connection, you\'ll see a message like "Successfully connected to agent: \'SimpleGenesisAgentForTheWin\'..." and "You can now send messages. Type \'quit\' or \'exit\' to stop."
10. You can type any message and press Enter. The message will be sent to the `SimpleGenesisAgent`. Since this agent is a basic echo agent (it doesn't yet parse input to call the calculator), it will likely respond with a message indicating it received your input, or a default reply based on its `OpenAIGenesisAgent` configuration.
11. Type `quit` or `exit` in the interface, or press `Ctrl+C` in the terminal where `run_example.sh` is running. This will trigger the cleanup process:
    *   The interface will shut down.
    *   The `run_example.sh` script will stop the background agent and service processes.
    *   Messages indicating shutdown and log locations will be printed.

## Key Genesis LIB Features Demonstrated

*   **Service Implementation**: `MonitoredService` for robust service creation.
*   **Function Exposure**: `@genesis_function` decorator for easily making service methods available via RPC.
*   **Agent Architecture**: `OpenAIGenesisAgent` as a base for creating AI agents.
*   **Interface Development**: `MonitoredInterface` for discovering and interacting with agents.
*   **Process Management**: Shell scripting for orchestrating multiple Python components.
*   **Logging**: Redirection of standard output/error for background processes to log files.
*   **Graceful Shutdown**: Using `trap` in shell scripts to ensure cleanup of child processes.

This example provides a foundational understanding of how different parts of the Genesis framework can be wired together to create a functional application. 