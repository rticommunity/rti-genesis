#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source the setup script to set environment variables
# Temporarily disabled as it's not needed for current testing
# source "$PROJECT_ROOT/setup.sh"

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# Start the calculator service
echo "===== Starting Calculator Service ====="
python3 "$PROJECT_ROOT/test_functions/calculator_service.py" &
CALCULATOR_PID=$!

# Start the letter counter service
echo "===== Starting Letter Counter Service ====="
python3 "$PROJECT_ROOT/test_functions/letter_counter_service.py" &
LETTER_COUNTER_PID=$!

# Start the text processor service
echo "===== Starting Text Processor Service ====="
python3 "$PROJECT_ROOT/test_functions/text_processor_service.py" &
TEXT_PROCESSOR_PID=$!

# Wait for services to initialize
echo "Waiting 5 seconds for services to initialize..."
sleep 5

# Start the CLI agent
#echo "===== Starting CLI Agent ====="
##python3 "$PROJECT_ROOT/test_agents/cli_direct_agent.py"

# Clean up on exit
echo "===== Cleaning Up ====="
kill $CALCULATOR_PID 2>/dev/null || true
kill $LETTER_COUNTER_PID 2>/dev/null || true
kill $TEXT_PROCESSOR_PID 2>/dev/null || true

# Wait for processes to finish
wait $CALCULATOR_PID 2>/dev/null || true
wait $LETTER_COUNTER_PID 2>/dev/null || true
wait $TEXT_PROCESSOR_PID 2>/dev/null || true

echo "===== All done =====" 
