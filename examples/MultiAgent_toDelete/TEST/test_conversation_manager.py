#!/usr/bin/env python3
"""
Test Conversation Manager

Test the conversation management system.
"""

import sys
import os
import asyncio
import time

# Add the parent directory to the path 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from interface.conversation_manager import ConversationManager, MessageRole, ConversationMessage
from interface.agent_selector import DiscoveredAgent, AgentStatus

async def test_conversation_manager():
    """Test conversation manager functionality."""
    print("🧪 Testing ConversationManager...")
    
    # Create a mock agent
    mock_agent = DiscoveredAgent(
        agent_id="test_agent",
        name="PersonalAssistant",
        display_name="Personal Assistant",
        service_name="PersonalAssistanceService",
        description="A friendly AI assistant for testing",
        capabilities=["general_assistance"],
        specializations=["personal_productivity"],
        status=AgentStatus.AVAILABLE,
        last_seen=time.time()
    )
    
    manager = ConversationManager("TestConversation")
    
    try:
        # Test starting the manager
        await manager.start()
        assert manager._connected == True
        print("✅ Manager started successfully")
        
        # Test connecting to agent
        connected = await manager.connect_to_agent(mock_agent)
        assert connected == True
        assert manager.current_session is not None
        print("✅ Connected to agent successfully")
        
        # Test sending a message
        response = await manager.send_message("Hello, can you help me?")
        assert response is not None
        assert response.role == MessageRole.ASSISTANT
        assert response.agent_name == "Personal Assistant"
        assert response.response_time is not None
        print(f"✅ Message sent and response received in {response.response_time:.3f}s")
        
        # Test conversation history
        history = manager.get_conversation_history()
        assert len(history) >= 3  # System message + user message + assistant response
        print(f"✅ Conversation history has {len(history)} messages")
        
        # Test session stats
        stats = manager.get_session_stats()
        assert "session_id" in stats
        assert stats["agent_name"] == "Personal Assistant"
        assert stats["total_messages"] > 0
        print("✅ Session statistics generated")
        
        # Test formatting
        formatted = manager.format_conversation()
        assert "Personal Assistant" in formatted
        assert "Hello, can you help me?" in formatted
        print("✅ Conversation formatting works")
        
        # Test disconnection
        manager.disconnect()
        assert manager.current_session is None
        print("✅ Disconnection works")
        
    finally:
        await manager.close()
        print("✅ Manager closed successfully")
    
    return True

async def main():
    """Run conversation manager tests."""
    print("🚀 Conversation Manager Test Suite")
    print("=" * 50)
    
    try:
        await test_conversation_manager()
        
        print("\n" + "=" * 50)
        print("🎉 All ConversationManager tests PASSED!")
        return 0
        
    except Exception as e:
        print(f"\n❌ ConversationManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 