#!/bin/bash

# Source the setup script if it exists
if [ -f "setup.sh" ]; then
    source setup.sh
fi

echo "Starting calculator service..."
# Start the calculator service in the background
python3 test_functions/calculator_service.py &
CALCULATOR_PID=$!

echo "Starting letter counter service..."
# Start the letter counter service in the background
python3 test_functions/letter_counter_service.py &
LETTER_COUNTER_PID=$!

echo "Starting text processor service..."
# Start the text processor service in the background
python3 test_functions/text_processor_service.py &
TEXT_PROCESSOR_PID=$!

# Wait for services to initialize
echo "Waiting for services to initialize (5 seconds)..."
sleep 5

# Run the schema verification test
echo "Running schema verification test..."
(
    # Set up a timeout handler
    trap "exit 124" ALRM
    # Set an alarm for 15 seconds
    perl -e 'alarm shift; exec @ARGV' 15 python3 test_functions/test_function_schemas.py
)

# Check if the test timed out (exit code 124 means timeout occurred)
TEST_EXIT=$?
if [ $TEST_EXIT -eq 124 ]; then
    echo "Test timed out, killing the services"
elif [ $TEST_EXIT -ne 0 ]; then
    echo "Test exited with error code $TEST_EXIT"
else
    echo "Test completed successfully"
fi

# Clean up by killing the service processes
echo "Shutting down services..."
kill $CALCULATOR_PID 2>/dev/null
kill $LETTER_COUNTER_PID 2>/dev/null
kill $TEXT_PROCESSOR_PID 2>/dev/null

# Wait for the services to fully exit
wait $CALCULATOR_PID 2>/dev/null
wait $LETTER_COUNTER_PID 2>/dev/null
wait $TEXT_PROCESSOR_PID 2>/dev/null

echo "Test completed." 