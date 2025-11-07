#!/usr/bin/env python3
"""
PersonalAssistant Test Service

A test personal assistant service for testing agent-to-agent communication.
Uses the standard OpenAIGenesisAgent with built-in enhanced tracing.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    Test personal assistant with enhanced built-in tracing.
    """
    
    def __init__(self, domain_id=0):
        print(f"🚀 TRACE: PersonalAssistant.__init__() starting on domain {domain_id}...")
        
        # Initialize with built-in enhanced tracing enabled
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant",
            base_service_name="PersonalAssistant",
            description="Test personal assistant with access to specialized agents and services",
            enable_agent_communication=True,
            enable_tracing=True,  # Enable built-in enhanced tracing
            domain_id=domain_id
        )
        
        print(f"✅ TRACE: PersonalAssistant initialized with agent_id: {self.app.agent_id} on domain {domain_id}")
        logger.info(f"PersonalAssistant ready for multi-agent interactions on domain {domain_id}")

async def main():
    """Main entry point for PersonalAssistant"""
    import argparse
    parser = argparse.ArgumentParser(description='Personal Assistant Service')
    parser.add_argument('--domain', type=int, default=None,
                       help='DDS domain ID (default: 0 or GENESIS_DOMAIN_ID env var)')
    args = parser.parse_args()
    
    # Priority: command line arg > env var > default (0)
    domain_id = args.domain if args.domain is not None else int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    print(f"🤖 Starting PersonalAssistant test service on domain {domain_id}...")
    logger.info(f"Starting PersonalAssistant test service on domain {domain_id}...")
    
    agent = PersonalAssistant(domain_id=domain_id)

    # Give auto-start a moment to announce and match
    await asyncio.sleep(2)
    if agent.enable_tracing:
        agent._trace_discovery_status("STARTUP CHECK (auto-run)")

    # Do NOT call run(); rely on auto-run started in constructor.
    # Block the process so the background service stays alive for tests.
    print("🟢 TRACE: PersonalAssistant running via auto-start. Blocking without explicit run()...")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        print("🛑 TRACE: Cancellation received; shutting down PersonalAssistant...")

if __name__ == "__main__":
    asyncio.run(main()) 
