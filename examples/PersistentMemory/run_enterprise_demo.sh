#!/bin/bash
# Requires PostgreSQL: set connection URL in config/enterprise_memory.json
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source ../../venv/bin/activate && source ../../.env 2>/dev/null
python persistent_memory_agent.py --config config/enterprise_memory.json
