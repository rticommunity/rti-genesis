#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source the setup script from the project root
source "$PROJECT_ROOT/setup.sh"

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# Start the calculator service in the background
echo "Starting calculator service..."
python "$PROJECT_ROOT/test_functions/calculator_service.py" > /dev/null 2>&1 &
SERVICE_PID=$!

# Wait for 120 seconds
echo "Service running for 240 seconds..."
sleep 240

# Kill the service
echo "Stopping calculator service..."
kill $SERVICE_PID 2>/dev/null || true

echo "Service stopped." 