# Persistent Memory Example

Demonstrates Genesis persistent memory with both local (SQLite) and enterprise (PostgreSQL) pathways.

## Quick Start (Local — Zero Config)

```bash
./run_local_demo.sh
```

This starts an interactive agent with SQLite-backed memory. Conversation survives restarts.

## Multi-Agent Shared Memory

```bash
python multi_agent_shared_memory.py
```

Two agents sharing one database with namespace-isolated shared memory.

## Enterprise Pathway (PostgreSQL)

1. Edit `config/enterprise_memory.json` with your PostgreSQL connection URL
2. Run:
```bash
./run_enterprise_demo.sh
```

## Tests

```bash
# Local pathway E2E
python tests/test_local_pathway.py

# Enterprise pathway E2E (requires GENESIS_TEST_PG_URL)
GENESIS_TEST_PG_URL="postgresql://user:pass@localhost/genesis" python tests/test_enterprise_pathway.py
```
