##!/bin/bash

# Source the setup script to set environment variables
echo "===== Sourcing setup.sh ====="
source setup.sh

# Create logs directory if it doesn't exist
mkdir -p logs

# Get current timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/all_services_test_${TIMESTAMP}.log"

echo "===== Starting All Services Test ====="
echo "Date: $(date)"
echo "Log file: ${LOG_FILE}"

# Start multiple calculator services in the background
echo "===== Starting Multiple Calculator Services ====="
echo "Starting Calculator Service Instance 1..."
python3 test_functions/calculator_service.py &
CALCULATOR_PID_1=$!

#echo "Starting Calculator Service Instance 2..."
#python3 test_functions/calculator_service.py &
#CALCULATOR_PID_2=$!

#echo "Starting Calculator Service Instance 3..."
#python3 test_functions/calculator_service.py &
#CALCULATOR_PID_3=$!

# Start the letter counter service in the background
echo "===== Starting Letter Counter Service ====="
python3 test_functions/letter_counter_service.py &
LETTER_COUNTER_PID=$!

# Start the text processor service in the background
echo "===== Starting Text Processor Service ====="
python3 test_functions/text_processor_service.py &
TEXT_PROCESSOR_PID=$!

# Give the services time to start up
echo "Waiting for services to start..."
sleep 10

# Run the comprehensive test
echo "===== Running All Services Test ====="
echo "Command: python3 test_functions/test_all_services.py"
python3 test_functions/test_all_services.py | tee -a ${LOG_FILE}
TEST_RESULT=$?

# Clean up
echo "===== Cleaning Up ====="
echo "Stopping calculator service instances..."
for pid in ${CALCULATOR_PID_1} ${CALCULATOR_PID_2} ${CALCULATOR_PID_3}; do
    echo "Stopping calculator service (PID: ${pid})..."
    kill ${pid} 2>/dev/null || true
    wait ${pid} 2>/dev/null || true
done

echo "Stopping letter counter service (PID: ${LETTER_COUNTER_PID})..."
kill ${LETTER_COUNTER_PID} 2>/dev/null || true
wait ${LETTER_COUNTER_PID} 2>/dev/null || true

echo "Stopping text processor service (PID: ${TEXT_PROCESSOR_PID})..."
kill ${TEXT_PROCESSOR_PID} 2>/dev/null || true
wait ${TEXT_PROCESSOR_PID} 2>/dev/null || true

echo "Cleanup complete."

# Exit with the test result
echo "===== Test completed with exit code: ${TEST_RESULT} ====="
exit ${TEST_RESULT} 