# Persistent Memory Example

Demonstrates Genesis persistent memory with both local (SQLite) and enterprise (PostgreSQL) pathways.

## Interactive Demo

```bash
./run_interactive_demo.sh
```

Starts a PersistentMemoryAgent (MonitoredAgent with Anthropic Claude) in the background and a MonitoredInterface in the foreground. Chat normally — conversation history persists across restarts.

The agent registers on the Genesis DDS network with full monitoring (state machine, graph topology, chain events). The interface discovers the agent via DDS and connects via standard RPC.

### Enterprise (PostgreSQL)

```bash
./run_interactive_demo.sh --config config/enterprise_memory.json
```

Edit `config/enterprise_memory.json` with your PostgreSQL connection URL first.

## Multi-Agent Shared Memory

```bash
python multi_agent_shared_memory.py
```

Two agents sharing one database with namespace-isolated shared memory.

## Tests

```bash
# Local pathway E2E
python tests/test_local_pathway.py

# Enterprise pathway E2E (requires GENESIS_TEST_PG_URL)
GENESIS_TEST_PG_URL="postgresql://user:pass@localhost/genesis" python tests/test_enterprise_pathway.py
```
