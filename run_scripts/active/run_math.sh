#!/bin/bash

# Simple script to run the calculator service and test it

# Source the setup script to set up the environment
# Temporarily disabled as it's not needed for current testing
# source ../setup.sh

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(dirname $(dirname $(realpath $0)))

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

# Start the calculator service in the background
echo "Starting calculator service..."
python -m test_functions.calculator_service &
CALC_PID=$!
pids+=("$CALC_PID")

# Wait for service to start
echo "Waiting for service to start..."
sleep 5

# Run a test client that makes requests to the calculator service
echo "Running test client..."
python -c "
import sys
import asyncio
from genesis_lib.rpc_client import GenesisRPCClient

async def test_calculator():
    try:
        # Create client and wait for service
        client = GenesisRPCClient('CalculatorService')
        print('Waiting for calculator service to be available...')
        await client.wait_for_service(timeout_seconds=10)

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
        if abs(result.get('result') - 4.0) > 1e-10:  # Using float comparison with small epsilon
            raise ValueError(f'Division test failed: expected 4.0, got {result}')
        print(f'Division test passed: 20 / 5 = {result.get(\"result\")}')

        # Test division by zero error handling
        try:
            await client.call_function('divide', x=10, y=0)
            raise ValueError('Division by zero did not raise an error')
        except Exception as e:
            if 'Cannot divide by zero' not in str(e):
                raise ValueError(f'Division by zero test failed: unexpected error {str(e)}')
            print('Division by zero test passed: error handled correctly')

        print('All calculator tests completed successfully')
        print('Debug: Setting success to True', file=sys.stderr)  # Debug output
        return True
    except Exception as e:
        print(f'Error during test: {str(e)}', file=sys.stderr)
        print('Debug: Setting success to False', file=sys.stderr)  # Debug output
        return False

# Run the async test
success = asyncio.run(test_calculator())
print(f'Debug: Final success value: {success}', file=sys.stderr)  # Debug output
sys.exit(0 if success else 1)
"
EXIT_CODE=$?

# Debug output
echo "Debug: Script exit code: $EXIT_CODE"

# Cleanup
cleanup

# Exit with test status
exit $EXIT_CODE 

