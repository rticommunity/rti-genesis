#!/usr/bin/env python3
"""
Conversation Manager

This module handles natural language conversations with selected agents.
It follows the Genesis pattern of letting the framework handle discovery,
connection, and communication while providing simple conversation history.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface
from interface.agent_selector import DiscoveredAgent

logger = logging.getLogger(__name__)

@dataclass
class ConversationMessage:
    """A simple conversation message for history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    response_time: Optional[float] = None

class ConversationManager(MonitoredInterface):
    """
    Simple conversation manager that follows Genesis patterns.
    
    Genesis handles:
    - Agent discovery and connection
    - Request/response communication
    - All DDS complexity
    
    This class adds:
    - Simple conversation history
    - User-friendly conversation flow
    """
    
    def __init__(self):
        """Initialize the conversation manager."""
        super().__init__(
            interface_name="ConversationManager", 
            service_name="ConversationService"
        )
        
        # Simple conversation state
        self.current_agent: Optional[DiscoveredAgent] = None
        self.conversation_history: List[ConversationMessage] = []
        
        logger.info("ConversationManager initialized")
    
    async def connect_to_agent(self, agent: DiscoveredAgent) -> bool:
        """
        Connect to an agent using Genesis built-in connection.
        
        Args:
            agent: The discovered agent to connect to
            
        Returns:
            True if connection successful, False otherwise
        """
        logger.info(f"Connecting to agent: {agent.display_name}")
        
        try:
            # Wait for MonitoredInterface to discover agents
            logger.info("⏳ Waiting for agent discovery...")
            
            # Wait for available_agents to be populated (Genesis pattern)
            timeout = 10.0
            start_time = time.time()
            while time.time() - start_time < timeout:
                if hasattr(self, 'available_agents') and self.available_agents:
                    break
                await asyncio.sleep(0.5)
            
            if not hasattr(self, 'available_agents') or not self.available_agents:
                logger.error("❌ No agents discovered by MonitoredInterface")
                return False
            
            # Find the agent in available_agents by service name or name
            target_agent_info = None
            target_agent_id = None
            
            for agent_id, agent_info in self.available_agents.items():
                service_name = agent_info.get('service_name', '')
                prefered_name = agent_info.get('prefered_name', '')
                
                # Match by service name or agent name
                if (service_name == agent.service_name or 
                    prefered_name.lower() == agent.name.lower() or
                    agent_id == agent.agent_id):
                    target_agent_info = agent_info
                    target_agent_id = agent_id
                    break
            
            if not target_agent_info:
                logger.error(f"❌ Agent {agent.display_name} not found in available_agents")
                logger.info(f"Available agents: {list(self.available_agents.keys())}")
                return False
            
            logger.info(f"🔗 Found agent in available_agents: {target_agent_info.get('prefered_name')} ({target_agent_id})")
            
            # Use Genesis built-in connection with the service name
            agent_service_name = target_agent_info.get('service_name', agent.service_name)
            success = await super().connect_to_agent(agent_service_name)
            
            if success:
                self.current_agent = agent
                logger.info(f"✅ Connected to {agent.display_name}")
                
                # Add system message to history
                self.conversation_history.append(ConversationMessage(
                    role="system",
                    content=f"Connected to {agent.display_name}",
                    timestamp=datetime.now()
                ))
                
                return True
            else:
                logger.error(f"❌ Failed to connect to {agent.display_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to {agent.display_name}: {e}")
            return False
    
    async def send_message(self, message: str) -> Optional[str]:
        """
        Send a message to the connected agent using Genesis.
        
        Args:
            message: User message to send
            
        Returns:
            Agent's response or None if failed
        """
        if not self.current_agent:
            logger.error("No agent connected")
            return None
        
        logger.info(f"Sending message to {self.current_agent.display_name}: {message[:50]}...")
        
        try:
            # Add user message to history
            user_msg = ConversationMessage(
                role="user",
                content=message,
                timestamp=datetime.now()
            )
            self.conversation_history.append(user_msg)
            
            # Build conversation context for the agent
            context = self._build_conversation_context()
            
            # Use Genesis built-in send_request
            start_time = time.time()
            response = await super().send_request(
                request_data={"message": context},
                timeout_seconds=30.0
            )
            response_time = time.time() - start_time
            
            if response and response.get('status') == 0:
                response_content = response.get('message', str(response))
                
                # Add assistant message to history
                assistant_msg = ConversationMessage(
                    role="assistant",
                    content=response_content,
                    timestamp=datetime.now(),
                    response_time=response_time
                )
                self.conversation_history.append(assistant_msg)
                
                logger.info(f"✅ Received response in {response_time:.3f}s")
                return response_content
            else:
                logger.error(f"Invalid response from {self.current_agent.display_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def _build_conversation_context(self) -> str:
        """
        Build simple conversation context from recent history.
        Keep it minimal - Genesis doesn't have memory yet.
        """
        # Get recent messages (last 5 exchanges)
        recent_messages = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history
        
        # Build simple context
        context_parts = []
        
        for msg in recent_messages:
            if msg.role == "user":
                context_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                context_parts.append(f"Assistant: {msg.content}")
        
        # Add current user message at the end
        if context_parts:
            return "\n".join(context_parts)
        else:
            # If no history, just return the latest user message
            return recent_messages[-1].content if recent_messages else ""
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the current conversation."""
        if not self.current_agent:
            return "No active conversation"
        
        total_messages = len([msg for msg in self.conversation_history if msg.role in ["user", "assistant"]])
        user_messages = len([msg for msg in self.conversation_history if msg.role == "user"])
        assistant_messages = len([msg for msg in self.conversation_history if msg.role == "assistant"])
        
        avg_response_time = 0.0
        response_times = [msg.response_time for msg in self.conversation_history if msg.response_time]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
        
        return f"""💬 Conversation with {self.current_agent.display_name}
📊 Messages: {total_messages} ({user_messages} from you, {assistant_messages} responses)
⏱️  Average response time: {avg_response_time:.3f}s
🕐 Started: {self.conversation_history[0].timestamp.strftime('%H:%M:%S') if self.conversation_history else 'Unknown'}"""
    
    def disconnect(self) -> None:
        """Disconnect from current agent."""
        if self.current_agent:
            logger.info(f"Disconnecting from {self.current_agent.display_name}")
            self.current_agent = None
            # Note: We don't clear conversation_history - user might want to see it
        else:
            logger.warning("No active connection to disconnect from")

# Test/Demo Functions  
async def demo_conversation():
    """Simple demo following Genesis patterns."""
    print("💬 Starting Simple Conversation Manager Demo...")
    
    # Create mock agent for demo
    from interface.agent_selector import DiscoveredAgent, AgentStatus
    
    mock_agent = DiscoveredAgent(
        agent_id="demo_agent",
        name="PersonalAssistant", 
        display_name="Personal Assistant",
        service_name="PersonalAssistanceService",
        description="Demo agent",
        capabilities=["general_assistance"],
        specializations=["personal_productivity"],
        status=AgentStatus.AVAILABLE,
        last_seen=time.time()
    )
    
    manager = ConversationManager()
    
    try:
        # Connect to agent
        print(f"🔗 Connecting to {mock_agent.display_name}...")
        connected = await manager.connect_to_agent(mock_agent)
        
        if connected:
            print("✅ Connected! (This demo would need a real agent to work)")
            print("🔍 In real usage, send_message() would use Genesis to communicate")
        else:
            print("❌ Connection failed (expected in demo without real agent)")
        
    finally:
        await manager.close()
    
    print("✅ Demo completed!")

if __name__ == "__main__":
    asyncio.run(demo_conversation()) 