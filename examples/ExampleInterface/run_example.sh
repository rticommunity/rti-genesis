#!/bin/bash

# Define process ID variables
agent_pid=""
service_pid=""

# Define quiet flag (default: no, set to "yes" to enable quiet mode)
QUIET_MODE="${QUIET_MODE:-no}"
QUIET_FLAG=""
if [ "$QUIET_MODE" = "yes" ]; then
    QUIET_FLAG="-q"
fi

# Get the directory of the currently executing script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Define the log directory
LOG_DIR="$SCRIPT_DIR/logs"

# Function to clean up background processes
cleanup() {
    echo "" # Newline for cleaner output
    echo "Initiating shutdown procedure..."

    if [ -n "$agent_pid" ]; then
        echo "Stopping Example Agent (PID: $agent_pid)..."
        if kill "$agent_pid" > /dev/null 2>&1; then
            wait "$agent_pid" 2>/dev/null
            echo "Example Agent stopped."
        else
            echo "Example Agent (PID: $agent_pid) was not running or already stopped."
        fi
    else
        echo "Example Agent PID not set."
    fi

    if [ -n "$service_pid" ]; then
        echo "Stopping Example Service (PID: $service_pid)..."
        if kill "$service_pid" > /dev/null 2>&1; then
            wait "$service_pid" 2>/dev/null
            echo "Example Service stopped."
        else
            echo "Example Service (PID: $service_pid) was not running or already stopped."
        fi
    else
        echo "Example Service PID not set."
    fi

    echo "Logs for agent and service are in: $LOG_DIR"
    echo "Cleanup complete. Exiting."
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM to call the cleanup function
# Also trap EXIT to ensure cleanup happens even if the script exits for other reasons
# after the PIDs have been set (e.g., interface exits normally).
trap cleanup SIGINT SIGTERM EXIT

# Create the log directory
echo "Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"

echo "Starting Example Service in the background... Outputting to $LOG_DIR/service.log"
# Run the service. Redirect stdout and stderr to a log file.
# The -u flag for python is still useful for unbuffered output to the log file.
python3 -u "$SCRIPT_DIR/example_service.py" > "$LOG_DIR/service.log" 2>&1 &
service_pid=$!
echo "Example Service started with PID: $service_pid"
sleep 1 # Brief pause

echo "Starting Example Agent in the background... Outputting to $LOG_DIR/agent.log"
# Run the agent. Redirect stdout and stderr to a log file.
# You can add --tag here if you want to run multiple instances, e.g., --tag my_test_agent
python3 -u "$SCRIPT_DIR/example_agent.py" $QUIET_FLAG > "$LOG_DIR/agent.log" 2>&1 &
agent_pid=$!
echo "Example Agent started with PID: $agent_pid"

# Give the agent and service a moment to fully initialize and announce themselves
echo "Waiting for agent and service to initialize (e.g., DDS discovery)... (5 seconds)"
sleep 5

echo "Starting Example Interface in the foreground."
echo "Use 'quit' or 'exit' in the interface, or press Ctrl+C here to stop everything."
# Run the interface in the foreground. It will be the primary interaction point.
# If it exits, the EXIT trap will call the cleanup function.
python3 "$SCRIPT_DIR/example_interface.py" $QUIET_FLAG

# The EXIT trap will handle cleanup, so no explicit call to cleanup here is strictly needed
# if the script is only exited by the interface terminating or by a trapped signal.
# However, if there were other ways for the script to proceed past the interface call
# without exiting, an explicit cleanup might be desired. For this setup, EXIT trap is sufficient.
echo "Interface has finished. Cleanup is being handled by EXIT trap."
