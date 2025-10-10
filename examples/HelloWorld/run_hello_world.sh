#!/bin/bash

# Set up logging directory
mkdir -p logs

# Start the Hello World service
echo "Starting Hello World service..."
python3 hello_world_service.py > logs/hello_world_service.log 2>&1 &
SERVICE_PID=$!
echo "Service started with PID: $SERVICE_PID"

# Wait for service to start
echo "Waiting for service to initialize..."
sleep 5

# Start the Hello World agent with a test message
echo "Starting Hello World agent with test message..."
python3 hello_world_agent.py "What is 42 plus 24?" > logs/hello_world_agent.log 2>&1 &
AGENT_PID=$!
echo "Agent started with PID: $AGENT_PID"

# Wait for agent to complete
echo "Waiting for agent to complete..."
wait $AGENT_PID
AGENT_EXIT=$?

# Clean up
echo "Stopping service..."
kill $SERVICE_PID
wait $SERVICE_PID

# Check results
if [ $AGENT_EXIT -eq 0 ]; then
    echo "✅ Test completed successfully"
    echo "Agent response:"
    grep "Agent response:" logs/hello_world_agent.log
    
    # Check for function call result
    echo "Checking for function call result..."
    if grep -q "{'result':" logs/hello_world_agent.log; then
        echo "✅ Function call detected"
        grep "{'result':" logs/hello_world_agent.log
    else
        echo "❌ No function call detected - test failed"
        exit 1
    fi
else
    echo "❌ Test failed with exit code $AGENT_EXIT"
    echo "Check logs/hello_world_agent.log for details"
fi 