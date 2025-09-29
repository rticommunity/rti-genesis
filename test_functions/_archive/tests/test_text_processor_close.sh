#!/bin/bash

# Start the service in the background
python3 test_functions/text_processor_service.py &

# Capture the service's process ID (PID)
SERVICE_PID=$!

# Wait 5 seconds to let the service initialize
sleep 5

# Run the close test
python3 test_functions/test_text_processor_close.py

# Clean up by killing the service process regardless of test outcome
kill $SERVICE_PID 2>/dev/null

# Wait for the service to fully exit
wait $SERVICE_PID 2>/dev/null 