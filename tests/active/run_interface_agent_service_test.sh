#!/bin/bash

# Test for Interface -> Agent -> Service pipeline
# 1. Checks for clean DDS environment for relevant topics.
# 2. Starts SimpleGenesisAgent.
# 3. Starts CalculatorService.
# 4. Runs SimpleGenesisInterfaceStatic to send a math question.
# 5. Verifies the interaction through logs.

set -e # Exit immediately if a command exits with a non-zero status.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$PROJECT_ROOT/logs"
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# Get domain ID from environment (default to 0)
DOMAIN_ID="${GENESIS_DOMAIN_ID:-0}"
echo "Using DDS domain: $DOMAIN_ID"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log files
AGENT_LOG="$LOG_DIR/test_sga_pipeline.log"
CALC_LOG="$LOG_DIR/test_calc_pipeline.log"
STATIC_INTERFACE_LOG="$LOG_DIR/test_static_interface_pipeline.log"
SPY_LOG="$LOG_DIR/test_pipeline_spy.log"

# PIDs of background processes
pids=()

# Cleanup function
cleanup() {
    echo "Cleaning up pipeline test processes..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # PARALLEL-SAFE: Only kill rtiddsspy on OUR domain, not all rtiddsspy processes
    # The broad pkill commands below are REMOVED to prevent killing other parallel tests
    echo "Pipeline test cleanup complete."
}
trap cleanup EXIT

# --- 1. DDS Sanity Check ---
echo "Performing DDS sanity check for relevant topics..."
rm -f "$SPY_LOG"

# Check for NDDSHOME
if [ -z "$NDDSHOME" ]; then
    echo "ERROR: NDDSHOME environment variable is not set."
    echo "Please set NDDSHOME to your RTI Connext DDS installation directory."
    echo "Example: export NDDSHOME=/path/to/rti_connext_dds-7.3.0"
    exit 1
fi

# Verify rtiddsspy exists
if [ ! -f "$NDDSHOME/bin/rtiddsspy" ]; then
    echo "ERROR: rtiddsspy not found at $NDDSHOME/bin/rtiddsspy"
    echo "Please verify that NDDSHOME is set correctly and rtiddsspy exists in the bin directory."
    echo "Current NDDSHOME: $NDDSHOME"
    exit 1
fi

# Spy on topics that should be quiet before our test starts
"$NDDSHOME/bin/rtiddsspy" -domainId $DOMAIN_ID -printSample -topic 'RegistrationAnnouncement' -topic 'InterfaceAgentRequest' -topic 'rti/connext/genesis/rpc/CalculatorServiceRequest' -duration 5 > "$SPY_LOG" 2>&1 &
SPY_PID=$!
pids+=("$SPY_PID") # Add spy to cleanup, though it should exit on its own
wait "$SPY_PID" # Wait for spy to finish its 5-second run

# Check if spy detected any activity on these specific topics
# We are looking for evidence of existing writers or data samples.
if grep -E '(New writer for topic|SAMPLE for topic)' "$SPY_LOG"; then
    echo "ERROR: DDS Sanity Check FAILED. Existing activity detected on RegistrationAnnouncement, InterfaceAgentRequest, or unified RPC topics."
    echo "Relevant spy log entries:"
    grep -E '(New writer for topic|SAMPLE for topic)' "$SPY_LOG"
    exit 1
else
    echo "DDS Sanity Check PASSED. No pre-existing activity on target topics."
fi
rm -f "$SPY_LOG" # Clean up the spy log for this check

# --- 2. Start SimpleGenesisAgent ---
echo "Starting SimpleGenesisAgent..."
# Force the agent to always use tools for this test to ensure the RPC path is exercised.
export GENESIS_TOOL_CHOICE="required"

# Get domain argument if set
DOMAIN_ARG=""
if [ -n "${GENESIS_DOMAIN_ID:-}" ]; then
    DOMAIN_ARG="--domain ${GENESIS_DOMAIN_ID}"
    echo "Using domain ${GENESIS_DOMAIN_ID}"
fi

# Start the agent with verbose logging to aid discovery diagnostics
# RPC v2: No --tag needed, uses unified topics with GUID targeting
python "$SCRIPT_DIR/../helpers/simpleGenesisAgent.py" --verbose $DOMAIN_ARG > "$AGENT_LOG" 2>&1 &
pids+=("$!")

# --- 3. Start CalculatorService ---
echo "Starting CalculatorService..."
python "$PROJECT_ROOT/test_functions/services/calculator_service.py" $DOMAIN_ARG > "$CALC_LOG" 2>&1 &
pids+=("$!")

echo "Waiting 5 seconds for agent and service to initialize..."
sleep 5

# Proactively wait for the agent to discover calculator functions before sending the request.
# This avoids a race where the model answers directly (no tool schemas available yet).
echo "Ensuring agent has discovered calculator functions (waiting up to 25s)..."
DISCOVERY_WAIT_SECS=25
DISCOVERY_START_TS=$(date +%s)
while true; do
  # Check for either log format or print statement format (for robustness against logging config issues)
  if grep -q "Updated/Added discovered function: add" "$AGENT_LOG"; then
    echo "Function discovery confirmed in agent log."
    break
  fi
  NOW=$(date +%s)
  ELAPSED=$((NOW - DISCOVERY_START_TS))
  if [ $ELAPSED -ge $DISCOVERY_WAIT_SECS ]; then
    echo "ERROR: Agent did not log discovery of 'add' within ${DISCOVERY_WAIT_SECS}s."
    echo "--- Agent Log (tail) ---"; tail -n 80 "$AGENT_LOG"; echo "--- End Agent Log ---"
    echo "--- Service Log (tail) ---"; tail -n 80 "$CALC_LOG"; echo "--- End Service Log ---"
    exit 1
  fi
  sleep 0.5
done

# --- 4. Run SimpleGenesisInterfaceStatic ---
# It will use the question "What is 123 plus 456?" and expect 579
QUESTION_TO_ASK="What is 123 plus 456?"
EXPECTED_SUM=579

echo "Running SimpleGenesisInterfaceStatic with question: '$QUESTION_TO_ASK'..."
if python "$SCRIPT_DIR/../helpers/simpleGenesisInterfaceStatic.py" --question "$QUESTION_TO_ASK" --verbose $DOMAIN_ARG > "$STATIC_INTERFACE_LOG" 2>&1; then
    echo "SimpleGenesisInterfaceStatic completed successfully (exit code 0)."
else
    echo "ERROR: SimpleGenesisInterfaceStatic failed (exit code $?)."
    echo "--- Static Interface Log ($STATIC_INTERFACE_LOG) ---"
    cat "$STATIC_INTERFACE_LOG"
    echo "--- End Static Interface Log ---"
    exit 1
fi

# --- 5. Verify Interaction through Logs ---
echo "Verifying interactions via logs..."

# Check 1: Connected to SimpleGenesisAgent with RPC v2 unified topics
# RPC v2: Service name is now just 'OpenAIChat' (no tag suffix)
if ! grep -q "Successfully connected to agent: 'SimpleGenesisAgentForTheWin' (Service: 'OpenAIChat')." "$STATIC_INTERFACE_LOG"; then
    echo "ERROR: Verification FAILED. Did not find print statement for connection to 'SimpleGenesisAgentForTheWin' (Service: 'OpenAIChat') in $STATIC_INTERFACE_LOG"
    exit 1
fi
echo "  ✅ Verified: Connection to Agent (via print statement)."

# Check 2: Sent the correct question
# Escape quotes for grep pattern if question contains them (not in this case)
if ! grep -q "Sending to agent.*message': '$QUESTION_TO_ASK'" "$STATIC_INTERFACE_LOG"; then
    echo "ERROR: Verification FAILED. Did not find question '${QUESTION_TO_ASK}' being sent in $STATIC_INTERFACE_LOG"
    exit 1
fi
echo "  ✅ Verified: Question sent."

# Check 3: GenesisRequester log in CalculatorService log indicating correct function call and result
# The calculator_service.py uses GenesisReplier, but the *agent* uses GenesisRequester (via GenericFunctionClient)
# We need to check the *agent's* log for the client-side confirmation of the call to the calculator.
# The agent log ($AGENT_LOG) should show this via GenericFunctionClient -> GenesisRequester traces.
EXPECTED_RPC_CLIENT_LOG_PATTERN="GenesisRequester - INFO - Function add returned:.*{'result': $EXPECTED_SUM}"
if ! grep -qE "$EXPECTED_RPC_CLIENT_LOG_PATTERN" "$AGENT_LOG"; then
    echo "ERROR: Verification FAILED. Did not find requester confirmation of 'add' returning result $EXPECTED_SUM in $AGENT_LOG"
    echo "--- Agent Log ($AGENT_LOG) --- Tail:"
    tail -n 30 "$AGENT_LOG"
    echo "--- End Agent Log ---"
    exit 1
fi
echo "  ✅ Verified: RPC Client call to calculator service and correct raw result in agent log."

# Check 4: Final agent response in static interface log
# Example: Agent response: The sum of 123 and 456 is 579.
EXPECTED_AGENT_RESPONSE_PATTERN="Agent response: .*$EXPECTED_SUM"
if ! grep -qE "$EXPECTED_AGENT_RESPONSE_PATTERN" "$STATIC_INTERFACE_LOG"; then
    echo "ERROR: Verification FAILED. Did not find agent response containing '$EXPECTED_SUM' in $STATIC_INTERFACE_LOG"
    exit 1
fi
echo "  ✅ Verified: Final agent response contains correct sum."

echo "All pipeline verifications PASSED!"

# Cleanup is handled by trap
exit 0 
