#!/bin/bash
# Zero-config: uses SQLite, no external DB needed
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source ../../venv/bin/activate && source ../../.env 2>/dev/null
python persistent_memory_agent.py --config config/local_memory.json
