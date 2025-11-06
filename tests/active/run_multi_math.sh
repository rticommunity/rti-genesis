#!/bin/bash

# Script to run multiple calculator services and test them

# Source the setup script to set up the environment
# Temporarily disabled as it's not needed for current testing
# source ../setup.sh

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(dirname $(dirname $(realpath $0)))

# Set up log directory
PROJECT_ROOT="$(dirname $(dirname $(realpath $0)))"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
SPY_LOG="$LOG_DIR/spy_run_multi_math.log"

# Initialize array to store PIDs
declare -a pids=()

# Function to cleanup processes
cleanup() {
    echo "Cleaning up processes..."
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

# Start multiple calculator services in the background
echo "Starting calculator services..."
for i in {1..3}; do
    python -m test_functions.services.calculator_service > /dev/null 2>&1 &
    CALC_PID=$!
    pids+=("$CALC_PID")
    echo "Started calculator service $i with PID $CALC_PID"
done

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Run a test client that makes requests to multiple calculator services
echo "Running test client..."
python -c "
import sys
import asyncio
from genesis_lib.requester import GenesisRequester

async def test_calculators():
    try:
        # Create client for calculator service
        client = GenesisRequester(service_type='CalculatorService')
        print('Waiting for calculator service to be available...')
        await client.wait_for_service(timeout_seconds=10)

        # Test multiple operations
        print('\nTesting calculator service:')
        
        # Test addition
        result = await client.call_function('add', x=5, y=3)
        if result.get('result') != 8:
            raise ValueError(f'Addition test failed: expected 8, got {result}')
        print(f'Addition test passed: 5 + 3 = {result.get(\"result\")}')

        # Test subtraction
        result = await client.call_function('subtract', x=10, y=4)
        if result.get('result') != 6:
            raise ValueError(f'Subtraction test failed: expected 6, got {result}')
        print(f'Subtraction test passed: 10 - 4 = {result.get(\"result\")}')

        # Test multiplication
        result = await client.call_function('multiply', x=7, y=6)
        if result.get('result') != 42:
            raise ValueError(f'Multiplication test failed: expected 42, got {result}')
        print(f'Multiplication test passed: 7 * 6 = {result.get(\"result\")}')

        # Test division
        result = await client.call_function('divide', x=20, y=5)
        if result.get('result') != 4:
            raise ValueError(f'Division test failed: expected 4, got {result}')
        print(f'Division test passed: 20 / 5 = {result.get(\"result\")}')

        print('\nAll calculator tests completed successfully')
        return True
    except Exception as e:
        print(f'Error during test: {str(e)}', file=sys.stderr)
        return False

# Run the async test
success = asyncio.run(test_calculators())
sys.exit(0 if success else 1)
"
EXIT_CODE=$?

# Cleanup
cleanup

# Exit with test status
exit $EXIT_CODE
