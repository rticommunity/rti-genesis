# Copyright (c) 2025, RTI & Jason Upchurch

"""
LLM-related functionality for the GENESIS library
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from anthropic import Anthropic
import os

@dataclass
class Message:
    """Represents a single message in the conversation"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

class ChatAgent(ABC):
    """Base class for chat agents"""
    def __init__(self, agent_name: str, model_name: str, system_prompt: Optional[str] = None,
                 max_history: int = 10):
        self.agent_name = agent_name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.conversations: Dict[str, List[Message]] = {}
        self.logger = logging.getLogger(__name__)
    
    def _cleanup_old_conversations(self):
        """Remove old conversations if we exceed max_history"""
        if len(self.conversations) > self.max_history:
            # Remove oldest conversation
            oldest_id = min(self.conversations.items(), key=lambda x: x[1][-1].timestamp)[0]
            del self.conversations[oldest_id]
    
    @abstractmethod
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """Generate a response to the given message"""
        pass

class AnthropicChatAgent(ChatAgent):
    """Chat agent using Anthropic's Claude model"""
    def __init__(self, model_name: str = "claude-3-opus-20240229", api_key: Optional[str] = None,
                 system_prompt: Optional[str] = None, max_history: int = 10):
        super().__init__("Claude", model_name, system_prompt, max_history)
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key is None:
                raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = Anthropic(api_key=api_key)
        self.logger.warning("AnthropicChatAgent initialized - this may cause rate limit issues")
    
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """Generate a response using Claude"""
        try:
            self.logger.warning(f"AnthropicChatAgent.generate_response called with message: '{message[:30]}...' - this may cause rate limit issues")
            
            # Get or create conversation history
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = []
            
            # Add user message
            self.conversations[conversation_id].append(
                Message(role="user", content=message)
            )
            
            # Clean up empty messages from conversation history
            self.conversations[conversation_id] = [
                msg for msg in self.conversations[conversation_id]
                if msg.content.strip()  # Keep only messages with non-empty content
            ]
            
            # Generate response
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.system_prompt if self.system_prompt else "You are a helpful AI assistant.",
                messages=[
                    {"role": msg.role, "content": msg.content}
                    for msg in self.conversations[conversation_id]
                ]
            )
            
            # Get response text, handling empty responses
            response_text = response.content[0].text if response.content else ""
            
            # Add assistant response only if it's not empty
            if response_text.strip():
                self.conversations[conversation_id].append(
                    Message(role="assistant", content=response_text)
                )
            
            # Cleanup old conversations
            self._cleanup_old_conversations()
            
            return response_text, 0
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return str(e), 1 