#!/bin/bash

# Source the setup script if it exists
if [ -f "setup.sh" ]; then
    source setup.sh
fi

echo "Starting calculator service..."
# Start the service in the background
python3 test_functions/calculator_service.py &

# Capture the service's process ID (PID)
SERVICE_PID=$!

# Wait for the service to initialize
echo "Waiting for service to initialize (5 seconds)..."
sleep 5

# Run the calculator client test
echo "Running calculator client test..."
(
    # Set up a timeout handler
    trap "exit 124" ALRM
    # Set an alarm for 15 seconds
    perl -e 'alarm shift; exec @ARGV' 15 python3 test_functions/calculator_client.py
)

# Check if the client timed out (exit code 124 means timeout occurred)
CLIENT_EXIT=$?
if [ $CLIENT_EXIT -eq 124 ]; then
    echo "Client timed out, killing the service"
elif [ $CLIENT_EXIT -ne 0 ]; then
    echo "Client exited with error code $CLIENT_EXIT"
else
    echo "Client completed successfully"
fi

# Clean up by killing the service process
echo "Shutting down service..."
kill $SERVICE_PID 2>/dev/null

# Wait for the service to fully exit
wait $SERVICE_PID 2>/dev/null

echo "Test completed." 