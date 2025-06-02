#!/usr/bin/env python3
"""Debug agent formatting output."""

import sys
import os

# Add the parent directory to the path 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from interface.agent_selector import AgentSelector, AgentStatus, DiscoveredAgent

def debug_formatting():
    """Debug the agent list formatting."""
    print("🔍 Debugging agent list formatting...")
    
    selector = AgentSelector("TestInterface")
    
    # Create a mock discovered agent
    mock_agent = DiscoveredAgent(
        agent_id="test_agent",
        name="PersonalAssistant",
        display_name="Personal Assistant",
        service_name="PersonalAssistanceService", 
        description="A friendly AI assistant",
        capabilities=["general_assistance", "task_planning"],
        specializations=["personal_productivity", "daily_planning"],
        status=AgentStatus.AVAILABLE,
        last_seen=1234567890.0,
        response_time=0.150
    )
    
    selector.discovered_agents["test_agent"] = mock_agent
    
    # Get formatting output
    formatted = selector.format_agent_list()
    
    print("=" * 60)
    print("FORMATTED OUTPUT:")
    print("=" * 60)
    print(formatted)
    print("=" * 60)
    print(f"Length: {len(formatted)}")
    print(f"Contains 'Personal Assistant': {'Personal Assistant' in formatted}")
    print(f"Contains 'friendly AI assistant' (case insensitive): {'friendly AI assistant' in formatted.lower()}")
    print(f"Contains '🟢': {'🟢' in formatted}")
    print(f"Contains '(0.150s)': {'(0.150s)' in formatted}")
    print("=" * 60)

if __name__ == "__main__":
    debug_formatting() 