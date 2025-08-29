#!/bin/bash

# Genesis Test Suite
# =================
#
# This script runs the complete test suite for the Genesis framework, ensuring
# all components work together correctly in a distributed environment. It tests
# the core functionality of the framework including:
#
# - Function discovery and registration
# - RPC communication between services
# - Agent interactions and function calling
# - Monitoring and logging capabilities
# - Error handling and recovery
#
# The test suite follows this sequence:
# 1. Starts the monitoring system to observe test execution
# 2. Launches test services (Calculator, TextProcessor, etc.)
# 3. Runs test agents that interact with the services
# 4. Executes integration tests
# 5. Performs cleanup of all components
#
# Prerequisites:
# - Python 3.10 or higher
# - RTI Connext DDS 7.3.0 or higher
# - Required API keys (OpenAI, Anthropic) in environment
# - All dependencies installed via setup.sh
#
# Usage:
#   ./run_all_tests.sh
#
# Environment Variables:
#   NDDSHOME: Path to RTI Connext DDS installation
#   OPENAI_API_KEY: OpenAI API key for LLM tests
#   ANTHROPIC_API_KEY: Anthropic API key for Claude tests
#
# Exit Codes:
#   0: All tests passed successfully
#   1: One or more tests failed
#   2: Environment setup failed
#
# Copyright (c) 2025, RTI & Jason Upchurch

# run_all_tests.sh - A script to run all Genesis-LIB test scripts with timeouts
# This script runs each test script with a timeout and proper error handling
# If any test fails, the script will stop for debugging

###############################
# Strict mode and preamble    #
###############################
set -e

# Configuration
TIMEOUT=120  # Default timeout in seconds
DEBUG=${DEBUG:-false}  # Set to true to show debug output

# Get the script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# If we're not in the run_scripts directory, cd to it
if [ "$(basename "$PWD")" != "run_scripts" ]; then
    cd "$SCRIPT_DIR"
fi

# Resolve script path across new structure (active/) with backward compatibility
resolve_path() {
    local rel="$1"
    if [ -e "$rel" ]; then echo "$rel"; return 0; fi
    if [ -e "active/$rel" ]; then echo "active/$rel"; return 0; fi
    echo "$rel" # fall through; run_with_timeout will report failure if missing
}

#########################################
# Environment activation and preflight  #
#########################################

# Activate venv if not already active
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Load project .env if present to pick up NDDSHOME and API keys
if [ -f "$PROJECT_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
fi

# Ensure expected Python version (3.10.x)
PY_MM=$(python - <<'EOF'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
EOF
)
if [ "${PY_MM%%.*}" != "3" ] || [ "${PY_MM#*.}" != "10" ]; then
    echo "Error: Python 3.10 is required. Current python is ${PY_MM}." >&2
    echo "Hint: run 'source venv/bin/activate' before invoking this script." >&2
    exit 2
fi

# Attempt to locate NDDSHOME if not set
if [ -z "${NDDSHOME:-}" ]; then
    # Common macOS and Linux install locations
    guess=$(ls -d /Applications/rti_connext_dds-* 2>/dev/null | sort -V | tail -n1)
    if [ -z "$guess" ]; then
        guess=$(ls -d "$HOME"/rti_connext_dds-* 2>/dev/null | sort -V | tail -n1)
    fi
    if [ -n "$guess" ]; then
        export NDDSHOME="$guess"
    fi
fi

# Resolve rtiddsspy location with overrides
# Priority: RTIDDSSPY_BIN -> RTI_BIN_DIR/rtiddsspy -> $NDDSHOME/bin/rtiddsspy
if [ -n "${RTIDDSSPY_BIN:-}" ]; then
    CANDIDATE_RTIDDSSPY="$RTIDDSSPY_BIN"
elif [ -n "${RTI_BIN_DIR:-}" ]; then
    CANDIDATE_RTIDDSSPY="$RTI_BIN_DIR/rtiddsspy"
else
    CANDIDATE_RTIDDSSPY="${NDDSHOME:-}/bin/rtiddsspy"
fi

if [ ! -x "$CANDIDATE_RTIDDSSPY" ]; then
    echo "Error: Could not find an executable 'rtiddsspy'." >&2
    echo "Checked: RTIDDSSPY_BIN='$RTIDDSSPY_BIN', RTI_BIN_DIR='$RTI_BIN_DIR', NDDSHOME='$NDDSHOME'" >&2
    echo "Tips:" >&2
    echo "  - Ensure NDDSHOME is set correctly (e.g., /Applications/rti_connext_dds-7.3.0)" >&2
    echo "  - Or copy the binary locally: mkdir -p \"$PROJECT_ROOT/bin\" && cp \"$NDDSHOME/bin/rtiddsspy\" \"$PROJECT_ROOT/bin/\"" >&2
    echo "    then run: export RTI_BIN_DIR=\"$PROJECT_ROOT/bin\"" >&2
    exit 2
fi
RTIDDSSPY_BIN="$CANDIDATE_RTIDDSSPY"

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Function to check for and clean up DDS processes
check_and_cleanup_dds() {
    echo "🔍 TRACE: Checking for existing DDS processes..."
    
    # Start spy to check for DDS activity
    SPY_LOG="$LOG_DIR/dds_check.log"
    "$RTIDDSSPY_BIN" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    
    # Wait a bit to see if any DDS activity is detected
    sleep 5
    
    # Check if spy detected any activity
    if grep -q "New writer\|New data" "$SPY_LOG"; then
        echo "⚠️ TRACE: Detected DDS activity. Attempting to clean up..."
        
        # Try to kill any DDS processes (first pass)
        pkill -f "rtiddsspy.*SpyLib::TransientReliable" || true
        pkill -f "python.*genesis_lib" || true
        
        # Specifically find and kill known test service PIDs (second pass)
        TARGET_SCRIPTS=(\
            "test_functions/calculator_service.py"\
            "test_functions/text_processor_service.py"\
            "test_functions/letter_counter_service.py"\
        )
        for script_pattern in "${TARGET_SCRIPTS[@]}"; do
            PIDS=$(pgrep -f "python.*${script_pattern}")
            if [ -n "$PIDS" ]; then
                echo "🎯 TRACE: Forcefully killing lingering processes for ${script_pattern} by PID: $PIDS"
                # Use xargs to handle potential multiple PIDs
                echo "$PIDS" | xargs kill -9 || true
            fi
        done
        
        # Wait a bit and check again
        sleep 10 # Increased duration to allow processes to fully terminate
        
        # Start a new spy to verify cleanup
        rm -f "$SPY_LOG"
        "$RTIDDSSPY_BIN" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$SPY_LOG" 2>&1 &
        SPY_PID=$!
        sleep 5
        
        # Check if DDS activity is still present on specific test topics
        # Use extended regex (-E) to match specific topics
        if grep -E '(New writer|New data).*topic="(FunctionCapability|CalculatorServiceRequest|TextProcessorServiceRequest|LetterCounterServiceRequest)"' "$SPY_LOG"; then
            echo "❌ ERROR: Detected lingering DDS activity on test topics (FunctionCapability or Service Requests) after cleanup attempt."
            kill $SPY_PID 2>/dev/null || true
            return 1
        fi
    fi
    
    # Clean up spy
    kill $SPY_PID 2>/dev/null || true
    echo "✅ TRACE: DDS process cleanup attempted."
    return 0
}

[ "$DEBUG" = "true" ] && echo "Project root: $PROJECT_ROOT"
[ "$DEBUG" = "true" ] && echo "Script directory: $SCRIPT_DIR"
[ "$DEBUG" = "true" ] && echo "Log directory: $LOG_DIR"

# Function to display log content on failure
display_log_on_failure() {
    local error_type=$1
    local error_message=$2
    shift 2 # Remove error_type and error_message from arguments

    echo "❌ ERROR: $error_message"
    echo "=================================================="
    echo "Relevant log file contents (last 20 lines each):"
    echo "=================================================="

    for log_file in "$@"; do
        if [ -f "$log_file" ]; then
            echo "--- Log: $log_file ---"
            # Show the last 20 lines of the log file
            tail -n 20 "$log_file" | sed 's/^/  /'
            echo "--- End Log: $log_file ---"
        else
            echo "--- Log not found: $log_file ---"
        fi
    done
    echo "=================================================="
    echo "Full logs available in: $LOG_DIR"
    echo "=================================================="
}

# Function to run a script with timeout and log output
run_with_timeout() {
    local script_name=$1
    local timeout=$2
    local script_basename=$(basename "$script_name")
    local primary_log_file="$LOG_DIR/${script_basename%.*}.log"
    local failure_detected=0
    local error_type=""
    local error_message=""
    local all_log_files=()
    
    echo "=================================================="
    echo "Running $script_name with ${timeout}s timeout..."
    [ "$DEBUG" = "true" ] && echo "Log file: $primary_log_file"
    echo "=================================================="
    
    # Determine if this is a Python script or a shell script
    if [[ "$script_name" == *.py ]]; then
        # Run Python script with timeout and capture output
        PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $timeout python "$script_name" > "$primary_log_file" 2>&1
    else
        # Run shell script with timeout and capture output
        PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $timeout bash "$script_name" > "$primary_log_file" 2>&1
    fi
    
    # Check exit status
    local exit_code=$?
    if [ $exit_code -eq 124 ]; then
        failure_detected=1
        error_type="timeout"
        error_message="$script_name timed out after ${timeout}s"
    elif [ $exit_code -ne 0 ]; then
        failure_detected=1
        error_type="exit_code"
        error_message="$script_name failed with exit code $exit_code"
    fi
    
    # Check for test failures in the log if no other failure detected yet
    if [ $failure_detected -eq 0 ] && grep -q "Some tests failed" "$primary_log_file"; then
        failure_detected=1
        error_type="test_failure"
        error_message="$script_name reported test failures"
    fi
    
    # Check for Python errors in the log if no other failure detected yet
    if [ $failure_detected -eq 0 ] && grep -q "ImportError\|NameError\|TypeError\|AttributeError\|RuntimeError\|SyntaxError\|IndentationError" "$primary_log_file"; then
        failure_detected=1
        error_type="python_error"
        error_message="$script_name encountered Python errors"
    fi
    
    # Check for unexpected error messages in the log if no other failure detected yet
    if [ $failure_detected -eq 0 ]; then
        # Create a temporary file with filtered content
        local temp_log=$(mktemp)
        # Filter out INFO, DEBUG, and expected warning/error messages
        grep -v "INFO\|DEBUG\|WARNING\|Cannot divide by zero\|Function call failed\|All calculator tests completed successfully\|Debug: \|test passed\|Test passed\|DivisionByZeroError\|Error executing function: Cannot divide by zero" "$primary_log_file" > "$temp_log"
        
        # Only show debug output if DEBUG is true
        if [ "$DEBUG" = "true" ]; then
            echo "Debug: Remaining content after filtering:"
            cat "$temp_log"
            echo "Debug: End of filtered content"
        fi
        
        # Check for remaining error messages, being more specific about what constitutes an error
        if grep -q "^ERROR:\|^Error:\|^error:" "$temp_log" || \
           (grep -q "Traceback (most recent call last)" "$temp_log" && \
            ! grep -q "DivisionByZeroError: Cannot divide by zero" "$primary_log_file"); then
            failure_detected=1
            error_type="unexpected_error"
            error_message="$script_name encountered unexpected errors"
            # Show the matching lines
            if [ "$DEBUG" = "true" ]; then
                echo "Debug: Lines containing errors:"
                grep "^ERROR:\|^Error:\|^error:\|Traceback (most recent call last)\|Exception:" "$temp_log"
                echo "Debug: End of error lines"
            fi
        fi
        rm "$temp_log"
    fi
    
    # Check for unexpected termination if no other failure detected yet
    if [ $failure_detected -eq 0 ] && grep -q "Killed\|Segmentation fault\|Aborted\|core dumped" "$primary_log_file"; then
        failure_detected=1
        error_type="termination"
        error_message="$script_name terminated unexpectedly"
    fi
    
    # --- Failure Handling --- 
    if [ $failure_detected -ne 0 ]; then
        # Prepare list of logs to display
        all_log_files+=("$primary_log_file")
        
        # --- Add Heuristics to find related logs --- 
        local script_prefix="${script_basename%.*}" # Get script name without extension
        
        # Example Heuristic: For run_test_agent_with_functions.sh
        if [[ "$script_basename" == "run_test_agent_with_functions.sh" ]]; then
            # Add logs generated by this specific script
            related_logs=($(ls "$LOG_DIR/test_agent_"*".log" "$LOG_DIR/calculator_service_"*".log" 2>/dev/null))
            all_log_files+=("${related_logs[@]}")
        fi
        
        # Example Heuristic: For start_services_and_agent.py
        if [[ "$script_basename" == "start_services_and_agent.py" ]]; then
            related_logs=($(ls "$LOG_DIR/"*"_service_"*".log" "$LOG_DIR/openai_chat_agent.log" 2>/dev/null))
            all_log_files+=("${related_logs[@]}")
        fi
        
        # Example Heuristic: For start_services_and_cli.sh
        if [[ "$script_basename" == "start_services_and_cli.sh" ]]; then
            related_logs=($(ls "$LOG_DIR/"*"_service_"*".log" "$LOG_DIR/interface_cli.log" 2>/dev/null))
            all_log_files+=("${related_logs[@]}")
        fi
        
        # Example Heuristic: For run_math_interface_agent_simple.sh
        if [[ "$script_basename" == "run_math_interface_agent_simple.sh" ]]; then
            related_logs=($(ls "$LOG_DIR/math_test_agent.log" "$LOG_DIR/math_test_interface.log" "$LOG_DIR/rtiddsspy_math.log" 2>/dev/null))
            all_log_files+=("${related_logs[@]}")
        fi
        
        # Heuristic for run_interface_agent_service_test.sh
        if [[ "$script_basename" == "run_interface_agent_service_test.sh" ]]; then
            related_logs=($(ls "$LOG_DIR/test_sga_pipeline.log" "$LOG_DIR/test_calc_pipeline.log" "$LOG_DIR/test_static_interface_pipeline.log" "$LOG_DIR/test_pipeline_spy.log" 2>/dev/null))
            all_log_files+=("${related_logs[@]}")
        fi
        
        # --- Display all found logs --- 
        # Remove duplicates (although unlikely with current heuristics)
        unique_log_files=($(printf "%s\n" "${all_log_files[@]}" | sort -u))
        
        # Call display function with all unique log files
        display_log_on_failure "$error_type" "$error_message" "${unique_log_files[@]}"
        
        # Clean up any processes that might still be running
        cleanup
        return 1
    fi
    
    # If no failure detected
    echo "✅ SUCCESS: $script_name completed successfully"
    return 0
}

# Function to clean up processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up any remaining processes..."
    pkill -f "python.*calculator_service" || true
    pkill -f "python.*text_processor_service" || true
    pkill -f "python.*letter_counter_service" || true
    pkill -f "python.*simple_agent" || true
    pkill -f "python.*simple_client" || true
    pkill -f "python.*openai_chat_agent" || true
    pkill -f "python.*interface_cli" || true
    pkill -f "python.*test_agent" || true
    # Multi-agent test cleanup
    pkill -f "python.*personal_assistant.py" || true
    pkill -f "python.*weather_agent.py" || true
    pkill -f "python.*test_interactive_multi_agent.py" || true
    # Agent-to-agent test service cleanup
    pkill -f "python.*personal_assistant_service.py" || true
    pkill -f "python.*weather_agent_service.py" || true
    [ "$DEBUG" = "true" ] && echo "Cleanup complete"
}

# Set up trap for cleanup on script termination
trap cleanup EXIT

# Main execution
echo "Starting Genesis-LIB test suite..."
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"

# Check for and clean up any existing DDS processes
check_and_cleanup_dds || { echo "Test suite aborted due to DDS process issues"; exit 1; }

# Memory Test (FIRST - Core Agent Memory Functionality)
echo "🧠 Running agent memory recall test..."
run_with_timeout "$(resolve_path run_test_agent_memory.sh)" 60 || { echo "Test failed: run_test_agent_memory.sh - AGENT MEMORY FUNCTIONALITY BROKEN"; exit 1; }

# Agent-to-Agent Communication Test (SECOND - Comprehensive Core Genesis Test)
echo "🚀 Running comprehensive agent-to-agent communication test..."
run_with_timeout "$(resolve_path test_agent_to_agent_communication.py)" 120 || { echo "Test failed: test_agent_to_agent_communication.py - CORE GENESIS FUNCTIONALITY BROKEN"; exit 1; }

# Interface -> Agent -> Service Pipeline Test (Moved to be second after agent-to-agent)
run_with_timeout "$(resolve_path run_interface_agent_service_test.sh)" 75 || { echo "Test failed: run_interface_agent_service_test.sh"; exit 1; }

# Math Interface/Agent Simple Test (Checks RPC and Durability)
run_with_timeout "$(resolve_path run_math_interface_agent_simple.sh)" 60 || { echo "Test failed: run_math_interface_agent_simple.sh"; exit 1; }

# Basic calculator test
run_with_timeout "$(resolve_path run_math.sh)" 30 || { echo "Test failed: run_math.sh"; exit 1; }

# Multi-instance calculator test
run_with_timeout "$(resolve_path run_multi_math.sh)" 60 || { echo "Test failed: run_multi_math.sh"; exit 1; }

# Simple agent test
run_with_timeout "$(resolve_path run_simple_agent.sh)" 60 || { echo "Test failed: run_simple_agent.sh"; exit 1; }

# Simple client test
run_with_timeout "$(resolve_path run_simple_client.sh)" 60 || { echo "Test failed: run_simple_client.sh"; exit 1; }

# Calculator durability test
run_with_timeout "$(resolve_path test_calculator_durability.sh)" 60 || { echo "Test failed: test_calculator_durability.sh"; exit 1; }

# Example agent test
# Guard: skip run_test_agent_with_functions when OPENAI_API_KEY is not set
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "⚠️  Skipping run_test_agent_with_functions.sh: OPENAI_API_KEY not set."
else
    DEBUG=true run_with_timeout "$(resolve_path run_test_agent_with_functions.sh)" 60 || { echo "Test failed: run_test_agent_with_functions.sh"; exit 1; }
fi

# Services and agent test
# run_with_timeout "start_services_and_agent.py" 90 || { echo "Test failed: start_services_and_agent.py"; exit 1; }

# Services and CLI test
run_with_timeout "$(resolve_path start_services_and_cli.sh)" 90 || { echo "Test failed: start_services_and_cli.sh"; exit 1; }

# Genesis framework test
run_with_timeout "$(resolve_path test_genesis_framework.sh)" 120 || { echo "Test failed: test_genesis_framework.sh"; exit 1; }

# Monitoring test
# Guard: test_monitoring.sh may require API keys; skip if absent
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "⚠️  Skipping test_monitoring.sh: OPENAI_API_KEY not set."
else
    run_with_timeout "$(resolve_path test_monitoring.sh)" 90 || { echo "Test failed: test_monitoring.sh"; exit 1; }
fi

echo "=================================================="
echo "All tests completed successfully!"
[ "$DEBUG" = "true" ] && echo "Logs are available in $LOG_DIR"
echo "==================================================" 
