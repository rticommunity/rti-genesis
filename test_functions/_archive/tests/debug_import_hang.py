#!/usr/bin/env python3
"""
Debug script to identify which import is causing the hang.
"""

import sys
import os

print("🚀 TRACE: Script starting")

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
print("✅ TRACE: Path added")

print("📦 TRACE: Importing asyncio...")
import asyncio
print("✅ TRACE: asyncio imported")

print("📦 TRACE: Importing logging...")
import logging
print("✅ TRACE: logging imported")

print("📦 TRACE: Importing time...")
import time
print("✅ TRACE: time imported")

print("📦 TRACE: Importing uuid...")
import uuid
print("✅ TRACE: uuid imported")

print("📦 TRACE: Importing typing...")
from typing import Dict, Any
print("✅ TRACE: typing imported")

print("📦 TRACE: Importing genesis_lib.monitored_agent...")
from genesis_lib.monitored_agent import MonitoredAgent
print("✅ TRACE: MonitoredAgent imported")

print("✅ TRACE: All imports successful")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

print("✅ TRACE: Logging configured")

print("🏗️ TRACE: About to create MonitoredAgent...")

try:
    agent = MonitoredAgent(
        agent_name="TestAgent",
        base_service_name="TestService",
        agent_type="AGENT",
        enable_agent_communication=True
    )
    print("✅ TRACE: MonitoredAgent created successfully")
except Exception as e:
    print(f"💥 TRACE: Error creating MonitoredAgent: {e}")
    import traceback
    print(f"💥 TRACE: Traceback: {traceback.format_exc()}")

print("✅ TRACE: Script completed") 