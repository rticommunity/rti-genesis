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

# Get the absolute path of the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source the setup script to set environment variables
# Temporarily disabled as it's not needed for current testing
# source "$PROJECT_ROOT/setup.sh"

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
SPY_LOG="$LOG_DIR/spy_start_services_and_cli.log"

# Start rtiddsspy to monitor DDS traffic
if [ -n "$NDDSHOME" ] && [ -f "$NDDSHOME/bin/rtiddsspy" ]; then
    RTIDDSSPY_PROFILEFILE="$PROJECT_ROOT/spy_transient.xml" "$NDDSHOME/bin/rtiddsspy" > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    echo "Started rtiddsspy monitoring (PID: $SPY_PID, Log: $SPY_LOG)"
fi

# Start the calculator service
echo "===== Starting Calculator Service ====="
python3 "$PROJECT_ROOT/test_functions/services/calculator_service.py" &
CALCULATOR_PID=$!

# Start the letter counter service
echo "===== Starting Letter Counter Service ====="
python3 "$PROJECT_ROOT/test_functions/services/letter_counter_service.py" &
LETTER_COUNTER_PID=$!

# Start the text processor service
echo "===== Starting Text Processor Service ====="
python3 "$PROJECT_ROOT/test_functions/services/text_processor_service.py" &
TEXT_PROCESSOR_PID=$!

# Wait for services to initialize
echo "Waiting 5 seconds for services to initialize..."
sleep 5

# Start the CLI agent
#echo "===== Starting CLI Agent ====="
##python3 "$PROJECT_ROOT/test_agents/cli_direct_agent.py"

# Clean up on exit
echo "===== Cleaning Up ====="
# Kill spy if running
if [ -n "$SPY_PID" ] && kill -0 "$SPY_PID" 2>/dev/null; then
    kill "$SPY_PID" 2>/dev/null || true
fi
kill $CALCULATOR_PID 2>/dev/null || true
kill $LETTER_COUNTER_PID 2>/dev/null || true
kill $TEXT_PROCESSOR_PID 2>/dev/null || true

# Wait for processes to finish
wait $CALCULATOR_PID 2>/dev/null || true
wait $LETTER_COUNTER_PID 2>/dev/null || true
wait $TEXT_PROCESSOR_PID 2>/dev/null || true

echo "===== All done =====" 
