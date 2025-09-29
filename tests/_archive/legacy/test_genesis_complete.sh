#!/bin/bash

# Genesis Complete Test Suite
# This script performs a comprehensive test of all Genesis components

# Set up error handling
set -e

# Source the setup script to set environment variables
echo "===== Sourcing setup.sh ====="
source ../setup.sh

# Add project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(dirname $(dirname $(realpath $0)))

# Create logs directory if it doesn't exist
mkdir -p ../logs
LOG_DIR="../logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="$LOG_DIR/genesis_test_${TIMESTAMP}.log"

# Function to log messages
log_message() {
    echo "$1" | tee -a $MAIN_LOG
}

# Function to check if a process is running
check_process() {
    if ps -p $1 > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start core services
start_core_services() {
    log_message "===== Starting Core Services ====="
    
    # Start calculator service
    log_message "Starting Calculator Service..."
    python ../test_functions/services/calculator_service.py > "$LOG_DIR/calculator.log" 2>&1 &
    CALC_PID=$!
    
    # Start text processor
    log_message "Starting Text Processor Service..."
    python ../test_functions/services/text_processor_service.py > "$LOG_DIR/text_processor.log" 2>&1 &
    TEXT_PID=$!
    
    # Start letter counter
    log_message "Starting Letter Counter Service..."
    python ../test_functions/services/letter_counter_service.py > "$LOG_DIR/letter_counter.log" 2>&1 &
    LETTER_PID=$!
    
    # Wait for services to initialize
    log_message "Waiting for services to initialize..."
    sleep 5
    
    # Verify services are running
    for pid in $CALC_PID $TEXT_PID $LETTER_PID; do
        if ! check_process $pid; then
            log_message "ERROR: Service with PID $pid failed to start"
            cleanup_processes
            exit 1
        fi
    done
    
    log_message "All core services started successfully"
}

# Function to test core services
test_core_services() {
    log_message "===== Testing Core Services ====="
    
    # Run service tests using test_all_services.py
    log_message "Running service test suite..."
    python ../test_functions/test_all_services.py > "$LOG_DIR/service_tests.log" 2>&1
    if [ $? -ne 0 ]; then
        log_message "ERROR: Core service tests failed"
        return 1
    fi
    log_message "Core service tests completed successfully"
}

# Function to test agent functionality
test_agent() {
    log_message "===== Testing Agent Layer ====="
    
    # Start test agent
    log_message "Starting Test Agent..."
    python -c "
from genesis_lib.agent import MonitoredAgent
from genesis_lib.function_discovery import FunctionRegistry
from genesis_lib.rpc_client import GenesisRPCClient
import asyncio

class TestAgent(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="TestAgent",
            service_name="TestService",
            agent_type="AGENT"
        )
        logger.info("TestAgent initialized")

    def _process_request(self, request):
        # Simple echo implementation
        return {'response': request}

async def run_agent():
    try:
        # Initialize function registry first
        registry = FunctionRegistry()
        
        # Then create agent
        agent = TestAgent()
        print('Agent initialized successfully')
        return agent
    except Exception as e:
        print(f'Agent initialization failed: {str(e)}')
        raise

asyncio.run(run_agent())
" > "$LOG_DIR/agent.log" 2>&1 &
    AGENT_PID=$!
    
    # Wait for agent to initialize
    sleep 3
    
    # Test agent with calculator service
    log_message "Testing agent with calculator service..."
    python -c "
from genesis_lib.rpc_client import GenesisRPCClient
import asyncio

async def test_agent():
    try:
        # Create client
        client = GenesisRPCClient('CalculatorService')
        await client.wait_for_service()
        
        # Test calculation
        result = await client.call_function('add', x=5, y=3)
        assert result['result'] == 8, f'Expected 8, got {result}'
        
        print('Agent test successful')
    except Exception as e:
        print(f'Agent test failed: {str(e)}')
        exit(1)

asyncio.run(test_agent())
" > "$LOG_DIR/agent_test.log" 2>&1
    
    AGENT_TEST_RESULT=$?
    kill $AGENT_PID 2>/dev/null || true
    
    if [ $AGENT_TEST_RESULT -ne 0 ]; then
        log_message "ERROR: Agent tests failed"
        return 1
    fi
    log_message "Agent tests completed successfully"
}

# Function to test interface
test_interface() {
    echo "Testing interface..."
    
    # Create a Python script for interface test
    cat > test_interface.py << 'EOF'
#!/usr/bin/env python3

import sys
import os
import time
import logging
import json
from genesis_lib.interface import GenesisInterface
from genesis_lib.datamodel import FunctionRequest, FunctionReply

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("interface_test")

class TestInterface(GenesisInterface):
    def __init__(self):
        super().__init__("TestInterface", "CalculatorService")
    
    def test_add(self):
        # Create request data
        request_data = {
            "function_name": "add",
            "parameters": {
                "x": 5,
                "y": 3
            }
        }
        
        # Send request
        reply = self.send_request(request_data)
        
        if reply and reply["success"]:
            result = reply["result"]
            logger.info(f"Add test passed: {result}")
            return True
        else:
            error = reply["error_message"] if reply else "No reply received"
            logger.error(f"Add test failed: {error}")
            return False

def main():
    try:
        # Create interface
        interface = TestInterface()
        
        # Wait for agent
        if not interface.wait_for_agent():
            logger.error("Failed to discover agent")
            return 1
        
        # Run test
        if not interface.test_add():
            logger.error("Interface test failed")
            return 1
        
        logger.info("Interface test passed")
        return 0
        
    except Exception as e:
        logger.error(f"Error in interface test: {e}")
        return 1
    finally:
        if 'interface' in locals():
            interface.close()

if __name__ == "__main__":
    sys.exit(main())
EOF

    chmod +x test_interface.py
    
    # Start calculator service
    python3 ../test_functions/services/calculator_service.py &
    CALC_PID=$!
    sleep 2
    
    # Run interface test
    python3 test_interface.py > ../logs/interface_test.log 2>&1
    INTERFACE_RESULT=$?
    
    # Clean up
    kill $CALC_PID
    rm test_interface.py
    
    return $INTERFACE_RESULT
}

# Function to test OpenAI integration
test_openai_integration() {
    echo "===== Testing OpenAI Integration ====="
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "Warning: OPENAI_API_KEY not set"
        return 1
    fi

    python3 - > "$LOG_DIR/openai_test.log" 2>&1 <<EOF
import asyncio
import uuid
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

async def test_openai():
    try:
        agent = OpenAIGenesisAgent()
        conversation_id = str(uuid.uuid4())
        request = {'message': 'What is 4242 * 31337?', 'conversation_id': conversation_id}
        response = await agent.process_request(request)
        print(f"Response: {response}")
        
        # Remove any commas from the response before checking
        response_text = str(response).replace(',', '')
        if '132931554' in response_text:
            print("OpenAI agent test successful")
            return 0
        else:
            print("OpenAI agent test failed: Response does not contain expected result")
            return 1
    except Exception as e:
        print(f"OpenAI agent test failed: {str(e)}")
        return 1
    finally:
        try:
            await agent.close()
        except Exception as e:
            print(f"Warning: Error closing agent: {str(e)}")

if __name__ == "__main__":
    exit_code = asyncio.run(test_openai())
    exit(exit_code)
EOF

    if [ $? -ne 0 ]; then
        echo "ERROR: OpenAI integration tests failed"
        return 1
    fi
    echo "OpenAI integration tests completed successfully"
    return 0
}

# Function to cleanup processes
cleanup_processes() {
    log_message "===== Cleaning Up ====="
    
    # Kill all spawned processes
    for pid in $CALC_PID $TEXT_PID $LETTER_PID $AGENT_PID; do
        if [ ! -z "$pid" ]; then
            kill $pid 2>/dev/null || true
            wait $pid 2>/dev/null || true
        fi
    done
    
    # Kill any remaining Python processes (safety cleanup)
    pkill -f "python.*calculator_service" || true
    pkill -f "python.*text_processor_service" || true
    pkill -f "python.*letter_counter_service" || true
    pkill -f "python.*simple_agent" || true
    
    log_message "Cleanup completed"
}

# Set up cleanup trap
trap cleanup_processes EXIT

# Main test execution
main() {
    local test_status=0
    
    log_message "===== Starting Genesis Complete Test Suite ====="
    log_message "Date: $(date)"
    log_message "Log directory: $LOG_DIR"
    
    # Start core services
    start_core_services || test_status=1
    
    # Only continue with tests if services started successfully
    if [ $test_status -eq 0 ]; then
        # Run all test suites
        test_core_services || test_status=1
        test_agent || test_status=1
        test_interface || test_status=1
        test_openai_integration || test_status=1
    fi
    
    # Print final results
    log_message "===== Test Suite Complete ====="
    if [ $test_status -eq 0 ]; then
        log_message "✅ All tests passed successfully"
    else
        log_message "❌ Some tests failed - check logs for details"
    fi
    
    return $test_status
}

# Run the test suite
main
exit $? 
