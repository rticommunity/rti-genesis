#!/bin/bash

# Debug Agent Discovery Script
# This script uses RTIDDSpy to monitor DDS traffic while testing agent discovery
# 
# Copyright (c) 2025, RTI & Jason Upchurch

set -e

# Global variables for process IDs
RTIDDSSPY_PID=""
AGENT_PID=""

# Cleanup function to ensure processes are killed
cleanup() {
    echo ""
    echo "🧹 Cleaning up processes..."
    
    # Kill the agent if running
    if [ -n "$AGENT_PID" ] && kill -0 $AGENT_PID 2>/dev/null; then
        kill $AGENT_PID
        echo "   ✅ PersonalAssistant stopped (PID: $AGENT_PID)"
    fi
    
    # Kill RTIDDSpy if running
    if [ -n "$RTIDDSSPY_PID" ] && kill -0 $RTIDDSSPY_PID 2>/dev/null; then
        kill $RTIDDSSPY_PID
        echo "   ✅ RTIDDSpy stopped (PID: $RTIDDSSPY_PID)"
    fi
    
    # Also kill any stray rtiddsspy processes
    pkill -f rtiddsspy 2>/dev/null || true
    
    # Wait for processes to terminate
    sleep 2
    echo "   🧹 Cleanup complete"
}

# Set trap to ensure cleanup happens on script exit or interruption
trap cleanup EXIT INT TERM

echo "🔍 AGENT DISCOVERY DEBUG SCRIPT"
echo "================================"

# Check if NDDSHOME is set
if [ -z "$NDDSHOME" ]; then
    echo "❌ NDDSHOME environment variable not set"
    echo "   Please set NDDSHOME to your RTI Connext DDS installation directory"
    exit 1
fi

# Check if rtiddsspy exists
RTIDDSSPY="$NDDSHOME/bin/rtiddsspy"
if [ ! -f "$RTIDDSSPY" ]; then
    echo "❌ RTIDDSpy not found at: $RTIDDSSPY"
    echo "   Please check your RTI Connext DDS installation"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Clean up any existing log files
rm -f logs/rtiddsspy.log logs/agent_output.log

echo "🚀 Starting RTIDDSpy to monitor DDS traffic..."

# Start RTIDDSpy in background, logging to file
$RTIDDSSPY -domainId 0 -printSample > logs/rtiddsspy.log 2>&1 &
RTIDDSSPY_PID=$!

echo "   ✅ RTIDDSpy started (PID: $RTIDDSSPY_PID)"
echo "   📄 Logging to: logs/rtiddsspy.log"

# Wait a moment for RTIDDSpy to initialize
sleep 2

echo ""
echo "🤖 Starting PersonalAssistant agent..."

# Start PersonalAssistant agent with timeout
timeout 20s env PYTHONPATH=/Users/jason/Documents/Genesis_LIB python ./agents/general/personal_assistant.py > logs/agent_output.log 2>&1 &
AGENT_PID=$!

echo "   ✅ PersonalAssistant started (PID: $AGENT_PID)"
echo "   📄 Logging to: logs/agent_output.log"

# Wait for agent to initialize and publish data
echo ""
echo "⏳ Monitoring DDS traffic for 15 seconds..."
sleep 15

echo ""
echo "🛑 Stopping monitoring..."

# The cleanup will be handled by the trap, but we can also call it explicitly
# cleanup  # This will be called automatically by the trap

# Wait a moment for processes to fully terminate
sleep 2

echo ""
echo "📊 ANALYSIS RESULTS"
echo "==================="

echo ""
echo "🔍 DDS Topics discovered:"
echo "------------------------"
grep -E "Topic:|Found new Topic" logs/rtiddsspy.log | head -20 || echo "No topic discoveries found"

echo ""
echo "📋 Genesis-related topics:"
echo "--------------------------"
grep -i "genesis" logs/rtiddsspy.log || echo "No Genesis topics found"

echo ""
echo "📢 Registration announcements:"
echo "------------------------------"
grep -i "registration\|announce" logs/rtiddsspy.log || echo "No registration announcements found"

echo ""
echo "🎯 Agent capability data:"
echo "-------------------------"
grep -i "capability\|agent" logs/rtiddsspy.log | head -10 || echo "No agent capability data found"

echo ""
echo "🚀 Agent startup messages:"
echo "--------------------------"
head -20 logs/agent_output.log || echo "No agent output found"

echo ""
echo "📄 Full logs available at:"
echo "   - RTIDDSpy: logs/rtiddsspy.log"
echo "   - Agent:    logs/agent_output.log"

echo ""
echo "✅ Debug script completed!" 