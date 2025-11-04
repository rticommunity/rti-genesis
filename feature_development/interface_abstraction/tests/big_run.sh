#!/bin/bash
# Big integration test for interface abstraction
# Uses relative paths for portability

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

INTERFACE_BETWEEN_Q_SEC=2 "$SCRIPT_DIR/../start_topology.sh" \
  --agents 3 \
  --services 20 \
  --interfaces 2 \
  -t 150 \
  --force \
  --service-cmd "python $PROJECT_ROOT/test_functions/calculator_service.py" \
  --extra-agent-cmd "GENESIS_TRACE_AGENTS=1 python $PROJECT_ROOT/examples/MultiAgent/agents/personal_assistant.py" \
  --extra-agent-cmd "GENESIS_TRACE_AGENTS=1 python $PROJECT_ROOT/examples/MultiAgent/agents/weather_agent.py" \
  --extra-agent-cmd "GENESIS_TRACE_AGENTS=1 python $PROJECT_ROOT/run_scripts/baseline_test_agent.py" \
  --extra-agent-cmd "GENESIS_TRACE_AGENTS=1 python $PROJECT_ROOT/run_scripts/math_test_agent.py" \
  --interface-question "What is 424242 * 1.4222424?" \
  --interface-question "Compute (12345 * 678) - (9876 / 4) and round to 3 decimals." \
  --interface-question "Add 1.2345 and 6.789, then multiply the sum by 3.21." \
  --interface-question "If x=12 and y=7, what is x^2 + 3xy - y^2?" \
  --interface-question "Divide 100 by 0; report the error gracefully." \
  --interface-question "What is the sum of integers from 1 to 1000?" \
  --interface-question "Convert 212 Fahrenheit to Celsius." \
  --interface-question "What is the weather in Colorado Springs, Colorado?" \
  --interface-question "Give a 3-day weather forecast for Tokyo, Japan." \
  --interface-question "Is it raining in Seattle today?" \
  --interface-question "Using the calculator, evaluate: (3.5 + 2.75) * (8.2 - 4.1) / 2." \
  --interface-question "Multiply 987654321 by 12345." \
  --interface-question "What is 2^20, and what is log10(1000000)?" \
  --interface-question "Subtract 0.000123 from 1 and then divide by 3.14."
