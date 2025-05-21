#!/bin/bash

# limited_mesh_test.sh - Verifies services do not subscribe to FunctionCapability
#
# This script starts multiple services and uses rtiddsspy to ensure that
# these services only act as DataWriters for the FunctionCapability topic
# and do not create DataReaders for it.

# Set strict error handling
set -e

# Initialize test status
TEST_FAILED=0
DEBUG=${DEBUG:-false}

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Define service scripts and their log file names
CALCULATOR_SERVICE_SCRIPT="$PROJECT_ROOT/test_functions/calculator_service.py"
TEXTPROC_SERVICE_SCRIPT="$PROJECT_ROOT/test_functions/text_processor_service.py"
LETTERCOUNT_SERVICE_SCRIPT="$PROJECT_ROOT/test_functions/letter_counter_service.py"

CALCULATOR_SERVICE_LOG="$LOG_DIR/limited_mesh_calculator.log"
TEXTPROC_SERVICE_LOG="$LOG_DIR/limited_mesh_textproc.log"
LETTERCOUNT_SERVICE_LOG="$LOG_DIR/limited_mesh_lettercount.log"
RTIDDSSPY_LOG="$LOG_DIR/limited_mesh_rtiddsspy.log"

declare -a SERVICE_PIDS=()
SPY_PID=""

# Function to display detailed log content on failure
detailed_log_on_failure() {
    local message=$1
    echo "❌ FAILURE: $message"
    echo "=================================================="
    echo "Relevant log file contents:"
    echo "=================================================="
    if [ -f "$RTIDDSSPY_LOG" ]; then
        echo "--- rtiddsspy Log: $RTIDDSSPY_LOG ---"
        cat "$RTIDDSSPY_LOG" # Display full spy log on failure
        echo "--- End rtiddsspy Log ---"
    else
        echo "--- rtiddsspy Log not found: $RTIDDSSPY_LOG ---"
    fi
    # Add other service logs if needed
    for log_file in "$CALCULATOR_SERVICE_LOG" "$TEXTPROC_SERVICE_LOG" "$LETTERCOUNT_SERVICE_LOG"; do
        if [ -f "$log_file" ]; then
            echo "--- Service Log: $log_file (Last 20 lines) ---"
            tail -n 20 "$log_file"
            echo "--- End Service Log ---"
        fi
    done
    echo "=================================================="
    echo "Full logs available in: $LOG_DIR"
    echo "=================================================="
}


# Function to cleanup processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "🧹 TRACE: Cleaning up processes..."
    if [ -n "$SPY_PID" ] && ps -p "$SPY_PID" > /dev/null; then
        echo "🔫 TRACE: Stopping rtiddsspy (PID: $SPY_PID)..."
        kill -TERM "$SPY_PID" 2>/dev/null || true
        wait "$SPY_PID" 2>/dev/null || true
    fi
    SPY_PID=""

    for pid in "${SERVICE_PIDS[@]}"; do
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null; then
            echo "🔫 TRACE: Stopping service (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true # Wait for process to terminate
        fi
    done
    SERVICE_PIDS=()
    [ "$DEBUG" = "true" ] && echo "🧹 TRACE: Cleanup complete."
}

# Set up trap for cleanup on script termination or error
trap cleanup EXIT SIGINT SIGTERM

# Main execution
echo "🚀 TRACE: Starting Limited Mesh Test..."
echo "🧹 TRACE: Cleaning up any pre-existing logs..."
rm -f "$CALCULATOR_SERVICE_LOG" "$TEXTPROC_SERVICE_LOG" "$LETTERCOUNT_SERVICE_LOG" "$RTIDDSSPY_LOG"

echo "🚀 TRACE: Starting services..."
PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$CALCULATOR_SERVICE_SCRIPT" > "$CALCULATOR_SERVICE_LOG" 2>&1 &
SERVICE_PIDS+=($!)
echo "  -> Calculator Service started (PID: ${SERVICE_PIDS[${#SERVICE_PIDS[@]}-1]})"

PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$TEXTPROC_SERVICE_SCRIPT" > "$TEXTPROC_SERVICE_LOG" 2>&1 &
SERVICE_PIDS+=($!)
echo "  -> Text Processor Service started (PID: ${SERVICE_PIDS[${#SERVICE_PIDS[@]}-1]})"

PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$LETTERCOUNT_SERVICE_SCRIPT" > "$LETTERCOUNT_SERVICE_LOG" 2>&1 &
SERVICE_PIDS+=($!)
echo "  -> Letter Counter Service started (PID: ${SERVICE_PIDS[${#SERVICE_PIDS[@]}-1]})"

echo "⏳ TRACE: Waiting a few seconds for services to initialize before starting spy..."
sleep 5

echo "🕵️ TRACE: Starting rtiddsspy to monitor FunctionCapability..."
# RTI Connext DDS Spy command
# Ensure the path to rtiddsspy is correct for your environment
DDS_SPY_CMD="$NDDSHOME/bin/rtiddsspy"
if [ ! -f "$DDS_SPY_CMD" ]; then
    echo "❌ ERROR: rtiddsspy command not found at $DDS_SPY_CMD"
    exit 1
fi

"$DDS_SPY_CMD" \
    -printSample \
    -topic FunctionCapability \
    -qosFile "$PROJECT_ROOT/spy_transient.xml" \
    -qosProfile SpyLib::TransientReliable \
    > "$RTIDDSSPY_LOG" 2>&1 &
SPY_PID=$!
echo "  -> rtiddsspy started (PID: $SPY_PID, Log: $RTIDDSSPY_LOG)"

echo "⏳ TRACE: Short wait for rtiddsspy to initialize..."
sleep 2

echo "⏳ TRACE: Waiting for 30 seconds for DDS discovery and spy logging..."
sleep 30

echo "🛑 TRACE: Stopping services and spy..."
cleanup # Call cleanup explicitly to stop processes before analysis

echo "🔎 TRACE: Analyzing rtiddsspy log ($RTIDDSSPY_LOG)..."

if [ ! -f "$RTIDDSSPY_LOG" ] || [ ! -s "$RTIDDSSPY_LOG" ]; then
    detailed_log_on_failure "rtiddsspy log file is missing or empty."
    exit 1
fi

# Extract participant GUIDs of writers for FunctionCapability
# These are assumed to be our services
# Awk script:
# /Discovered new writer:/ : Start of a writer block
# in_writer_block && /Topic name: FunctionCapability/ : If in block and topic matches
# in_writer_block && topic_name_fc && /Participant:/ : If in block, topic matched, and line has Participant, print GUID and reset
# NF == 0 : Reset block flag on empty line (robustness)
SERVICE_PARTICIPANT_GUIDS_STR=$(awk '
    /Discovered new writer:/            {in_block=1; topic_match=0; guid=""}
    in_block && /Topic name: FunctionCapability/ {topic_match=1}
    in_block && topic_match && /Participant:/ {guid=$2; print guid; in_block=0; topic_match=0}
    in_block && NF == 0                 {in_block=0}
' "$RTIDDSSPY_LOG" | sort -u)

# Convert to array
read -r -a SERVICE_PARTICIPANT_GUIDS <<< "$SERVICE_PARTICIPANT_GUIDS_STR"

NUM_SERVICE_WRITERS=${#SERVICE_PARTICIPANT_GUIDS[@]}
echo "  INFO: Found $NUM_SERVICE_WRITERS unique participant GUIDs writing to FunctionCapability."
[ "$DEBUG" = "true" ] && echo "    Service Writer GUIDs: ${SERVICE_PARTICIPANT_GUIDS[*]}"

if [ "$NUM_SERVICE_WRITERS" -ne 3 ]; then
    detailed_log_on_failure "Expected 3 services writing to FunctionCapability, found $NUM_SERVICE_WRITERS."
    TEST_FAILED=1
else
    echo "  ✅ INFO: Correct number of FunctionCapability writers (3) detected."
fi

# Extract participant GUIDs of readers for FunctionCapability
FC_READER_PARTICIPANT_GUIDS_STR=$(awk '
    /Discovered new reader:/              {in_block=1; topic_match=0; guid=""}
    in_block && /Topic name: FunctionCapability/ {topic_match=1}
    in_block && topic_match && /Participant:/ {guid=$2; print guid; in_block=0; topic_match=0}
    in_block && NF == 0                   {in_block=0}
' "$RTIDDSSPY_LOG" | sort -u)

read -r -a FC_READER_PARTICIPANT_GUIDS <<< "$FC_READER_PARTICIPANT_GUIDS_STR"

NUM_FC_READERS=${#FC_READER_PARTICIPANT_GUIDS[@]}
echo "  INFO: Found $NUM_FC_READERS unique participant GUIDs reading FunctionCapability."
[ "$DEBUG" = "true" ] && echo "    FunctionCapability Reader GUIDs: ${FC_READER_PARTICIPANT_GUIDS[*]}"

SERVICE_IS_A_READER=0
if [ "$TEST_FAILED" -eq 0 ]; then # Only proceed if previous checks passed
    for reader_guid in "${FC_READER_PARTICIPANT_GUIDS[@]}"; do
        is_known_service_writer=0
        for service_writer_guid in "${SERVICE_PARTICIPANT_GUIDS[@]}"; do
            if [[ "$reader_guid" == "$service_writer_guid" ]]; then
                # This means a participant that is writing FunctionCapability (a service)
                # is ALSO reading FunctionCapability. This is the failure condition.
                detailed_log_on_failure "Service (Participant GUID: $reader_guid) is incorrectly subscribed (reading) to FunctionCapability topic."
                TEST_FAILED=1
                SERVICE_IS_A_READER=1 # Mark that a service was found as a reader
                break # Exit inner loop
            fi
        done
        if [ "$SERVICE_IS_A_READER" -eq 1 ]; then
            break # Exit outer loop if a service reader is found
        fi
    done
fi

if [ "$SERVICE_IS_A_READER" -eq 0 ] && [ "$TEST_FAILED" -eq 0 ]; then
    echo "  ✅ SUCCESS: No service participants were found to be reading the FunctionCapability topic."
    # Further check: if NUM_FC_READERS is 0, it means spy also didn't see anything, which might be an issue with spy itself.
    # But spy *should* be a reader. So if there are readers, and none are services, that's good.
    if [ "$NUM_FC_READERS" -gt 0 ]; then
         echo "    INFO: The ${NUM_FC_READERS} reader(s) found are assumed to be rtiddsspy itself or other legitimate non-service entities."
    elif [ "$NUM_FC_READERS" -eq 0 ] && [ "$NUM_SERVICE_WRITERS" -gt 0 ]; then
        # This is a bit strange: services are writing, but spy sees no readers (not even itself).
        # This could happen if spy terminates too quickly or has issues.
        # However, the primary goal is that services are NOT readers.
        echo "    ⚠️ WARNING: rtiddsspy reported zero readers for FunctionCapability, even for itself. This might indicate a spy issue, but the primary test (services not reading) is based on services not appearing as readers."

    fi
else
    # TEST_FAILED was already set by the loop or previous checks
    if [ "$SERVICE_IS_A_READER" -eq 1 ]; then
        echo "  ❌ FAILURE: A service was found to be reading the FunctionCapability topic."
    fi
fi


# Final report
echo "=============================================="
if [ $TEST_FAILED -eq 0 ]; then
    echo "✅🎉 TRACE: Limited Mesh Test PASSED! Services are not subscribing to each other's FunctionCapability."
    exit 0
else
    echo "❌😭 TRACE: Limited Mesh Test FAILED."
    exit 1
fi 