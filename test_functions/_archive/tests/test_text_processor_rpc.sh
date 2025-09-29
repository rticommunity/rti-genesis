#!/bin/bash

# Start the service in the background
python3 test_functions/text_processor_service.py &

# Capture the service's process ID (PID)
SERVICE_PID=$!

# Wait 5 seconds to let the service initialize
sleep 5

# Run the client (we'll use SIGALRM instead of timeout command for portability)
(
    # Set up a timeout handler
    trap "exit 124" ALRM
    # Set an alarm for 15 seconds
    perl -e 'alarm shift; exec @ARGV' 15 python3 test_functions/text_processor_client.py
)

# Check if the client timed out (exit code 124 means timeout occurred)
if [ $? -eq 124 ]; then
    echo "Client timed out, killing the service"
    kill $SERVICE_PID
fi

# Clean up by killing the service process regardless of client outcome
kill $SERVICE_PID 2>/dev/null

# Wait for the service to fully exit
wait $SERVICE_PID 2>/dev/null 