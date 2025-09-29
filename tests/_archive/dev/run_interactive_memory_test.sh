#!/bin/bash

# run_interactive_memory_test.sh - Interactive Memory Test for Genesis Agents
# This script provides a clean way to run the interactive memory test

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Set up environment
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

echo "🧠 Starting Genesis Interactive Memory Test..."
echo "================================================"
echo
echo "💡 This test allows you to manually interact with a Genesis agent"
echo "   and observe how it maintains memory across conversation turns."
echo
echo "🔧 Initializing agent (this may take a few seconds)..."
echo

# Run the interactive test, suppressing DDS errors but keeping the main output
python "$SCRIPT_DIR/helpers/interactive_memory_test.py" 2>/dev/null || {
    echo "❌ Error running interactive memory test"
    echo "💡 Make sure OPENAI_API_KEY is set in your environment"
    exit 1
}

echo
echo "👋 Interactive memory test completed!" 
