#!/bin/bash
# Wrapper script to ensure the correct environment is set up before running tests

# Source the setup script to activate the conda environment and set up RTI Connext DDS
source ./setup.sh

# Check if RTI is available
python -c "import rti.connextdds as dds; print('RTI Connext DDS is available!')" || {
    echo "Error: RTI Connext DDS is not available. Please check your setup."
    exit 1
}

# Run the specified test script
if [ "$1" == "unit" ]; then
    echo "Running unit tests..."
    python test_function_calling.py
elif [ "$1" == "interactive" ]; then
    echo "Running interactive tests..."
    python test_function_interactive.py
elif [ "$1" == "agent1" ]; then
    echo "Running agent1..."
    python agent1.py
elif [ "$1" == "agent2" ]; then
    echo "Running agent2..."
    python agent2.py
else
    echo "Usage: $0 [unit|interactive|agent1|agent2]"
    echo "  unit        - Run unit tests"
    echo "  interactive - Run interactive tests"
    echo "  agent1      - Run agent1.py"
    echo "  agent2      - Run agent2.py"
    exit 1
fi 