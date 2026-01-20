# Genesis Stress Testing Tools

Tools for testing Genesis at scale - launching many agents, services, and interfaces to validate performance, monitoring, and scalability.

## Quick Start

```bash
# Basic stress test: 10 agents, 20 services, 1 interface for 3 minutes
./tests/stress/start_topology.sh -a 10 -s 20 -i 1 -t 180

# Comprehensive test: Full configuration with visualization
./tests/stress/run_comprehensive_stress_test.sh
```

## Tools

### `start_topology.sh`

Launch arbitrary numbers of Genesis components for stress testing.

**Options:**
```bash
./tests/stress/start_topology.sh [options]

  -a, --agents N           Number of agent instances (default: 1)
  -s, --services N         Number of service instances (default: 1)
  -i, --interfaces N       Number of interface instances (default: 1)
  -t, --timeout SEC        Timeout in seconds (default: 120)
  --logs-dir DIR           Log directory (default: tests/stress/logs)
  --no-spy                 Disable rtiddsspy logging
  --force                  Ignore pre-existing DDS activity
  --interface-question TXT Ask a question (repeatable)
  --extra-agent-cmd CMD    Start additional agent type (repeatable)
  -h, --help               Show help
```

**Features:**
- Configurable agent/service/interface counts
- Automatic cleanup on Ctrl-C or timeout
- Optional DDS traffic capture via rtiddsspy
- Support for heterogeneous agent types
- Comprehensive logging to `tests/stress/logs/`

**Examples:**

```bash
# Large-scale test
./tests/stress/start_topology.sh -a 50 -s 100 -i 5 -t 600

# With custom questions
./tests/stress/start_topology.sh -a 2 -s 1 -i 1 \
  --interface-question "What is 100 + 200?" \
  --interface-question "Calculate 50 * 25"

# Multiple agent types
./tests/stress/start_topology.sh -a 1 -s 1 -i 1 \
  --extra-agent-cmd "python examples/MultiAgent/agents/weather_agent.py" \
  --interface-question "What's the weather in Seattle?"
```

### `monitor_graph_snapshot.py`

Capture a point-in-time snapshot of the Genesis network topology.

**Usage:**
```bash
python tests/stress/monitor_graph_snapshot.py [options]

Options:
  --domain ID              DDS domain ID (default: 0)
  --duration SEC           Monitoring duration (default: 8.0)
  --out PATH               Output snapshot file
  --activity-out PATH      Output activity log (optional)
  --pretty                 Pretty-print JSON (default)
```

**Example:**
```bash
# Start components in background
./tests/stress/start_topology.sh -a 5 -s 10 -i 1 -t 300 &
sleep 10

# Capture snapshot
python tests/stress/monitor_graph_snapshot.py \
  --duration 10 \
  --out topology_snapshot.json
```

### `run_comprehensive_stress_test.sh`

Full end-to-end stress test with a realistic large-scale configuration.

**Configuration:**
- 6 PersonalAssistant agents + 1 WeatherExpert agent
- 20 Calculator services (80 functions total)
- 2 interfaces asking 6 questions
- Expected topology: ~146 nodes

**Run It:**
```bash
./tests/stress/run_comprehensive_stress_test.sh
```

**Recommended: Run with Visualization**
```bash
# Terminal 1: Start standalone viewer
./examples/StandaloneGraphViewer/run.sh

# Terminal 2: Run stress test
./tests/stress/run_comprehensive_stress_test.sh

# Open http://localhost:5000/ and watch the topology appear!
```

**What It Tests:**
- Large-scale topology monitoring (100+ nodes)
- Agent discovery across multiple instances
- Multi-agent communication patterns
- Agent-to-service function calls
- Interface querying with load balancing
- System stability under sustained load
- Graph visualization with complex topologies

## Common Use Cases

### Performance Testing

```bash
# Test with large numbers of components
./tests/stress/start_topology.sh -a 50 -s 100 -i 5 -t 600
```

### Monitoring Validation

```bash
# Terminal 1: Start viewer
./examples/StandaloneGraphViewer/run.sh

# Terminal 2: Launch components and watch graph populate
./tests/stress/start_topology.sh -a 20 -s 40 -i 2 -t 300
```

### Network Analysis

```bash
# Launch topology and capture snapshots over time
./tests/stress/start_topology.sh -a 10 -s 20 -i 1 -t 300 &

for i in {1..5}; do
  sleep 30
  python tests/stress/monitor_graph_snapshot.py --out snapshot_$i.json
done
```

## Tips

### Running Long Tests

```bash
# Use nohup for long-running tests
nohup ./tests/stress/start_topology.sh -a 50 -s 100 -t 3600 > stress.log 2>&1 &
```

### Analyzing rtiddsspy Logs

```bash
# Count samples per topic
grep "topic=" tests/stress/logs/rtiddsspy.log | sort | uniq -c

# Monitor activity in real-time
tail -f tests/stress/logs/rtiddsspy.log | grep "ChainEvent"
```

### Clean Up Processes

```bash
# If processes don't clean up properly
pkill -f "personal_assistant.py|weather_agent.py|calculator_service.py"
```

## Troubleshooting

**"DDS activity detected before start"**
- Use `--force` to proceed anyway, or kill existing processes

**"No spy log generated"**
- Check `NDDSHOME` is set: `echo $NDDSHOME`
- Use `--no-spy` if rtiddsspy isn't available

**"Out of file descriptors"**
- Increase limits: `ulimit -n 4096`
- Reduce component counts

## See Also

- `examples/StandaloneGraphViewer/` - Visualize large topologies
- `V2_MONITORING_USAGE.md` - Monitoring architecture
- `tests/run_all_tests_parallel.sh` - Parallel test runner

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
