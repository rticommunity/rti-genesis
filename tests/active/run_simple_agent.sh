#!/bin/bash
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

# Simple script to run the SimpleAgent with function services
# This script starts the necessary function services and the SimpleAgent

# Source the setup script to set up the environment
# Temporarily disabled as it's not needed for current testing
# source ../setup.sh

# Add the project root to PYTHONPATH
PROJECT_ROOT="$(dirname $(dirname $(realpath $0)))"
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
SPY_LOG="$LOG_DIR/spy_run_simple_agent.log"

# Initialize array to store PIDs
declare -a pids=()

# Function to cleanup processes
cleanup() {
    echo "Cleaning up processes..."
    # Kill spy if running
    if [ -n "$SPY_PID" ] && kill -0 "$SPY_PID" 2>/dev/null; then
        kill "$SPY_PID" 2>/dev/null || true
    fi
    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
        fi
    done
}

# Set up trap for cleanup on script termination
trap cleanup SIGINT SIGTERM EXIT

# Start rtiddsspy to monitor DDS traffic
if [ -n "$NDDSHOME" ] && [ -f "$NDDSHOME/bin/rtiddsspy" ]; then
    RTIDDSSPY_PROFILEFILE="$PROJECT_ROOT/spy_transient.xml" "$NDDSHOME/bin/rtiddsspy" > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    pids+=("$SPY_PID")
    echo "Started rtiddsspy monitoring (PID: $SPY_PID, Log: $SPY_LOG)"
fi

# Start the calculator service in the background
echo "Starting calculator service..."
python -m test_functions.services.calculator_service > /dev/null 2>&1 &
CALC_PID=$!
pids+=("$CALC_PID")

# Start the text processor service in the background
echo "Starting text processor service..."
python -m test_functions.services.text_processor_service > /dev/null 2>&1 &
TEXT_PID=$!
pids+=("$TEXT_PID")

# Start the letter counter service in the background
echo "Starting letter counter service..."
python -m test_functions.services.letter_counter_service > "$LOG_DIR/letter_counter_service.log" 2>&1 &
LETTER_PID=$!
pids+=("$LETTER_PID")

# Wait for services to start
# Increased to 20 seconds to ensure all services fully initialize their RPC endpoints
echo "Waiting for services to start (20 seconds)..."
sleep 20

# Start the SimpleAgent
echo "Starting SimpleAgent..."
python ../genesis_lib/simple_agent.py > /dev/null 2>&1 &
AGENT_PID=$!
pids+=("$AGENT_PID")

# Wait for agent to start
echo "Waiting for agent to start (10 seconds)..."
sleep 10

# Run a test client that makes requests to the services
echo "Running test client..."
python -c "
import sys
import time
import asyncio
from genesis_lib.requester import GenesisRequester

async def test_client():
    try:
        # Test calculator service
        calc_client = GenesisRequester(service_type='CalculatorService')
        print('Waiting for calculator service to be available...')
        await calc_client.wait_for_service(timeout_seconds=10)
        result = await calc_client.call_function('add', x=10, y=20)
        result_value = result.get('result')
        if result_value != 30:
            raise ValueError(f'Calculator test failed: expected 30, got {result_value}')
        print(f'Calculator test passed: 10 + 20 = {result_value}')

        # Test text processor service
        text_client = GenesisRequester(service_type='TextProcessorService')
        print('Waiting for text processor service to be available...')
        await text_client.wait_for_service(timeout_seconds=15)
        result = await text_client.call_function('count_words', text='This is a test sentence with seven words.')
        result_value = result.get('word_count')
        if result_value != 8:
            raise ValueError(f'Text processor test failed: expected 8, got {result_value}')
        print(f'Text processor test passed: Word count = {result_value}')

        # Test letter counter service
        letter_client = GenesisRequester(service_type='LetterCounterService')
        print('Waiting for letter counter service to be available...')
        await letter_client.wait_for_service(timeout_seconds=15)
        result = await letter_client.call_function('count_letter', text='Hello World', letter='l')
        result_value = result.get('result')
        if result_value != 3:
            raise ValueError(f'Letter counter test failed: expected 3, got {result_value}')
        print(f'Letter counter test passed: Letter count = {result_value}')

        print('All service tests completed successfully')
        return True
    except Exception as e:
        print(f'Error during test: {str(e)}', file=sys.stderr)
        return False

# Run the async test
success = asyncio.run(test_client())
sys.exit(0 if success else 1)
"
EXIT_CODE=$?

# Cleanup
cleanup

# Exit with test status
exit $EXIT_CODE 
