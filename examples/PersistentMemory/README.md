# Persistent Memory Example

Demonstrates Genesis persistent memory with both local (SQLite) and enterprise (PostgreSQL) pathways.

## Background

The persistent memory architecture is based on **Lossless Context Management (LCM)** from [Voltropy](https://papers.voltropy.com/LCM). LCM provides an immutable persistent store with a DAG of precomputed summaries and deterministic three-level compaction escalation that guarantees convergence without losing access to original data. Additional inspiration from [MemGPT](https://arxiv.org/abs/2310.08560) (LLMs as Operating Systems) and [HAT](https://arxiv.org/abs/2406.06124) (Hierarchical Aggregate Tree for Long-Term Memory). See the full technical vision in [`docs/architecture/persistent_memory_vision.md`](../../docs/architecture/persistent_memory_vision.md).

## Interactive Demo (Web GUI)

```bash
./run_interactive_demo.sh
```

Opens a web-based GUI at **http://127.0.0.1:5050** with:
- Chat panel with markdown rendering
- Real-time Genesis network topology (3D orbital viewer)
- Session info (message count, latency, agent status)
- Auto-discovery and connection to the PersistentMemoryAgent

The agent runs in the background as a proper MonitoredAgent with Anthropic Claude. Conversation history persists across restarts.

### Options

```bash
# Custom port
./run_interactive_demo.sh --port 8080

# CLI mode (no browser needed)
./run_interactive_demo.sh --cli

# Enterprise pathway (PostgreSQL)
./run_interactive_demo.sh --config config/enterprise_memory.json

# Choose model
./run_interactive_demo.sh --model claude-sonnet-4-20250514
```

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
