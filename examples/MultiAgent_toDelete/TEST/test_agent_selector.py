#!/usr/bin/env python3
"""
Test Agent Selector

Test the agent discovery system independently of running agents.
"""

import sys
import os
import asyncio

# Add the parent directory to the path 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from interface.agent_selector import AgentSelector, AgentStatus, DiscoveredAgent

def test_agent_selector_init():
    """Test agent selector initialization."""
    print("🧪 Testing AgentSelector initialization...")
    
    selector = AgentSelector("TestInterface")
    
    assert selector.interface_name == "TestInterface"
    assert len(selector.general_assistant_configs) == 3
    assert selector._discovery_active == False
    
    print("✅ AgentSelector initialization test passed!")
    return True

async def test_mock_discovery():
    """Test agent discovery with mock data."""
    print("🧪 Testing mock agent discovery...")
    
    selector = AgentSelector("TestInterface")
    
    # Manually add some mock agents to test the functionality
    mock_agents = {
        "agent_1": {
            "prefered_name": "PersonalAssistant",
            "service_name": "PersonalAssistanceService",
            "name": "PersonalAssistant"
        },
        "agent_2": {
            "prefered_name": "BusinessAssistant", 
            "service_name": "BusinessAssistanceService",
            "name": "BusinessAssistant"
        }
    }
    
    # Process mock agents
    for agent_id, agent_info in mock_agents.items():
        await selector._process_discovered_agent(agent_id, agent_info)
    
    # Test results
    assert len(selector.discovered_agents) == 2
    
    available_agents = selector.get_available_agents()
    assert len(available_agents) == 2
    
    # Test getting agent by name
    personal = selector.get_agent_by_name("PersonalAssistant")
    assert personal is not None
    assert personal.display_name == "Personal Assistant"
    
    business = selector.get_agent_by_name("BusinessAssistant")
    assert business is not None
    assert business.display_name == "Business Assistant"
    
    print("✅ Mock agent discovery test passed!")
    return True

def test_agent_formatting():
    """Test agent list formatting.""" 
    print("🧪 Testing agent list formatting...")
    
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
    
    # Test formatting
    formatted = selector.format_agent_list()
    
    assert "Personal Assistant" in formatted
    assert "a friendly ai assistant" in formatted.lower()
    assert "🟢" in formatted  # Available status emoji
    assert "(0.150s)" in formatted  # Response time
    
    print("✅ Agent list formatting test passed!")
    return True

async def test_health_check():
    """Test agent health checking."""
    print("🧪 Testing agent health check...")
    
    selector = AgentSelector("TestInterface")
    
    # Create a mock agent
    mock_agent = DiscoveredAgent(
        agent_id="test_agent",
        name="PersonalAssistant", 
        display_name="Personal Assistant",
        service_name="PersonalAssistanceService",
        description="A test agent",
        capabilities=[],
        specializations=[],
        status=AgentStatus.AVAILABLE,
        last_seen=1234567890.0
    )
    
    selector.discovered_agents["test_agent"] = mock_agent
    
    # Test health check
    healthy = await selector.health_check_agent("test_agent")
    assert healthy == True
    assert mock_agent.response_time is not None
    assert mock_agent.response_time > 0
    
    # Test health check for non-existent agent
    healthy = await selector.health_check_agent("nonexistent")
    assert healthy == False
    
    print("✅ Agent health check test passed!")
    return True

async def main():
    """Run all agent selector tests."""
    print("🚀 Agent Selector Test Suite")
    print("=" * 50)
    
    try:
        # Run tests
        test_agent_selector_init()
        await test_mock_discovery()
        test_agent_formatting()
        await test_health_check()
        
        print("\n" + "=" * 50)
        print("🎉 All AgentSelector tests PASSED!")
        return 0
        
    except Exception as e:
        print(f"\n❌ AgentSelector test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 