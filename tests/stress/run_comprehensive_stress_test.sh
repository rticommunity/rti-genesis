#!/usr/bin/env bash
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

# Comprehensive stress test for Genesis - Tests full end-to-end system
# Configuration: 2 interfaces, 6 agents, 20 services, multiple questions
#
# This test validates:
# - Large-scale topology (146 nodes: 6 agents + 20 services + 80 functions + 40 edges minimum)
# - Agent discovery and connection
# - Multi-hop agent-to-agent communication
# - Agent-to-service function calls
# - Interface querying and response handling
# - Monitoring and graph topology tracking
# - System stability under load

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$ROOT_DIR"

# Configuration
AGENTS=6
SERVICES=20
INTERFACES=2
TIMEOUT=300  # 5 minutes

# Test questions to exercise different paths
QUESTIONS=(
    "What is 42 * 18?"
    "Calculate 100 divided by 5"
    "What's the weather in Paris?"
    "Tell me about the weather in Tokyo"
    "What is 256 + 512?"
    "What is 1000 minus 250?"
)

echo "=== Genesis Comprehensive Stress Test ==="
echo "Configuration:"
echo "  - Agents: $AGENTS (PersonalAssistant + WeatherExpert)"
echo "  - Services: $SERVICES (Calculator services)"
echo "  - Interfaces: $INTERFACES"
echo "  - Timeout: ${TIMEOUT}s"
echo "  - Questions: ${#QUESTIONS[@]}"
echo ""
echo "Expected topology:"
echo "  - ~146 total nodes (6 agents + 20 services + 80 functions + edges)"
echo "  - Agent→Service edges for function discovery"
echo "  - Service→Function edges for capabilities"
echo "  - Interface→Agent request/reply edges"
echo ""
echo "Press Ctrl-C to stop early..."
echo ""

# Build questions arguments
QUESTION_ARGS=()
for q in "${QUESTIONS[@]}"; do
    QUESTION_ARGS+=(--interface-question "$q")
done

# Run the stress test
./tests/stress/start_topology.sh \
    --agents "$AGENTS" \
    --services "$SERVICES" \
    --interfaces "$INTERFACES" \
    --timeout "$TIMEOUT" \
    --extra-agent-cmd "python examples/MultiAgent/agents/weather_agent.py" \
    "${QUESTION_ARGS[@]}" \
    --force

echo ""
echo "=== Stress Test Complete ==="
echo "Check logs in: tests/stress/logs/"

