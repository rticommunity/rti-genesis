# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

"""
LLM MODULE - Lightweight Chat Agent Abstractions (and How They Integrate)

=================================================================================================
ARCHITECTURE OVERVIEW - What This Module Provides
=================================================================================================

This module defines a minimal, provider‑agnostic abstraction for chat‑style LLMs that can be used
standalone OR alongside the full Genesis agent/provider stack.

Core components:
- ChatAgent (abstract): Small facade around a conversation history and a single synchronous
  "generate_response" operation. It defines the return format and lifecycle for lightweight
  chat adapters.
- AnthropicChatAgent (concrete): Provider‑specific adapter that uses the official Anthropic
  Python SDK to call Claude models.

How this relates to MonitoredAgent‑based providers:
- ChatAgent implementations themselves do not publish graph topology, chain events, or integrate
  with DDS. They are lightweight adapters by design.
- However, they ARE used within the broader Genesis stack:
  • LLMFactory creates ChatAgent instances for classification and other lightweight LLM tasks.
  • GenesisAgent imports these types and can use a ChatAgent for classifier_llm when enabled.
  • A mix‑in variant (GenesisAnthropicChatAgent) combines GenesisAgent with AnthropicChatAgent;
    in this case, monitoring and DDS integration are provided by the GenesisAgent/MonitoredAgent
    inheritance chain, while AnthropicChatAgent supplies the lightweight chat capability.

Use this module when you need a simple, direct chat interaction, a classifier LLM, or a provider
adapter to be composed into a monitored agent. For production agents that orchestrate tools and
participate in distributed monitoring, build a MonitoredAgent‑based provider (see
`genesis_lib/monitored_agent.py`) and optionally compose a ChatAgent where appropriate.

=================================================================================================
CURRENT RUNTIME USAGE - Where It’s Used Today
=================================================================================================
1) LLMFactory: Creates ChatAgent instances (e.g., AnthropicChatAgent) for classification/specialized
   lightweight calls.
2) GenesisAgent: Imports ChatAgent/AnthropicChatAgent; supports passing a classifier_llm ChatAgent.
3) genesis_agent.py defines GenesisAnthropicChatAgent, a mix‑in that combines ChatAgent capability
   with the monitored agent stack (monitoring is provided by the agent hierarchy, not ChatAgent).

=================================================================================================
WHAT YOU GET - Capabilities in This Module
=================================================================================================
1. Conversation History Management
   - Per-conversation message lists keyed by a caller-provided conversation_id
   - Bounded history with least-recently-updated conversation cleanup
2. System Prompt Support
   - Optional system prompt applied to each provider call
3. Explicit Return Contract (applies to all ChatAgent implementations)
   - generate_response(message, conversation_id) -> tuple[str, int]
   - str: assistant text response (empty string on failure)
   - int: status code (0 = success, non-zero = error)
4. Official SDK Usage
   - Providers are implemented with official SDKs (e.g., Anthropic), not raw HTTP

=================================================================================================
ERROR HANDLING POLICY - No Silent Failures
=================================================================================================
- Provider errors are logged with ERROR severity
- generate_response returns ("<error message>", 1) on failure
- Consumers can rely on the explicit status code to branch logic

=================================================================================================
EXTENSION POINTS
=================================================================================================
- Subclass ChatAgent to add a new provider adapter:
    class MyProviderChatAgent(ChatAgent):
        def __init__(...): ...
        def generate_response(...): ...
- For production‑grade, monitored providers integrated with DDS and chain events, build a
  MonitoredAgent‑based provider (see `genesis_lib/monitored_agent.py`) and optionally compose a
  ChatAgent where you need simple chat/classification behavior.

=================================================================================================
USAGE EXAMPLE
=================================================================================================

    from genesis_lib.llm import AnthropicChatAgent

    agent = AnthropicChatAgent(
        model_name="claude-3-opus-20240229",
        system_prompt="You are a concise assistant."
    )
    text, status = agent.generate_response("Hello!", conversation_id="demo")
    if status == 0:
        print(text)
    else:
        print(f"LLM error: {text}")

=================================================================================================
DEPENDENCIES
=================================================================================================
- AnthropicChatAgent requires environment variable ANTHROPIC_API_KEY to be set
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
    """
    Represents a single message in a conversation transcript.

    Fields:
    - role: "user" or "assistant"
    - content: message text
    - timestamp: auto-populated creation time (datetime.now())
    """
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

class ChatAgent(ABC):
    """
    Base class for lightweight chat agents.

    Responsibilities:
    - Maintain per-conversation message history keyed by conversation_id
    - Provide a provider-agnostic generate_response() contract

    Initialization:
    - agent_name: human-readable provider/agent name
    - model_name: provider-specific model identifier
    - system_prompt: optional system prompt applied to calls
    - max_history: maximum number of active conversation transcripts to retain;
                   least-recently-updated conversations are discarded first
    """
    def __init__(self, agent_name: str, model_name: str, system_prompt: Optional[str] = None,
                 max_history: int = 10):
        self.agent_name = agent_name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.conversations: Dict[str, List[Message]] = {}
        self.logger = logging.getLogger(__name__)
    
    def _cleanup_old_conversations(self):
        """
        Remove oldest conversation transcripts when max_history is exceeded.
        Uses the most recent message timestamp in each conversation to determine recency.
        """
        if len(self.conversations) > self.max_history:
            # Remove oldest conversation
            oldest_id = min(self.conversations.items(), key=lambda x: x[1][-1].timestamp)[0]
            del self.conversations[oldest_id]
    
    @abstractmethod
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """
        Generate a response to the given message for the specified conversation.

        Return format (EXPLICIT CONTRACT):
        - (response_text: str, status: int)
          - response_text: assistant's textual reply; empty string on error
          - status: 0 on success; non-zero on error (implementation-defined)
        """
        pass

class AnthropicChatAgent(ChatAgent):
    """
    Provider adapter for Anthropic's Claude models.

    Requirements:
    - Uses the official Anthropic Python SDK
    - Requires ANTHROPIC_API_KEY in the environment if api_key not provided

    Notes:
    - Emits WARN logs at initialization and call-time to remind about potential rate limits
    - Maintains per-conversation message history (user/assistant turns)
    """
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
        """
        Generate a response using Anthropic Claude.

        Return format:
        - (response_text: str, status: int)
          - response_text: model reply text; empty string if provider returns no content
          - status: 0 on success; 1 on error
        """
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


class OpenAIChatAgent(ChatAgent):
    """
    Provider adapter for OpenAI's GPT models.
    
    Requirements:
    - Uses the official OpenAI Python SDK
    - Requires OPENAI_API_KEY in the environment if api_key not provided
    
    Notes:
    - Lightweight chat interface for classification and simple tasks
    - Maintains per-conversation message history (user/assistant turns)
    """
    def __init__(self, model_name: str = "gpt-4o", api_key: Optional[str] = None,
                 system_prompt: Optional[str] = None, max_history: int = 10):
        super().__init__("OpenAI", model_name, system_prompt, max_history)
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key is None:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Import OpenAI SDK
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Install with: pip install openai")
        
        self.client = OpenAI(api_key=api_key)
        self.logger.info(f"OpenAIChatAgent initialized with model {model_name}")
    
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """
        Generate a response using OpenAI GPT.
        
        Return format:
        - (response_text: str, status: int)
          - response_text: model reply text; empty string if provider returns no content
          - status: 0 on success; 1 on error
        """
        try:
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
            
            # Build messages for OpenAI API
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in self.conversations[conversation_id]
            ])
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=4096,
                temperature=0.7
            )
            
            # Get response text, handling empty responses
            response_text = response.choices[0].message.content if response.choices else ""
            
            # Add assistant response only if it's not empty
            if response_text and response_text.strip():
                self.conversations[conversation_id].append(
                    Message(role="assistant", content=response_text)
                )
            
            # Cleanup old conversations
            self._cleanup_old_conversations()
            
            return response_text or "", 0
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return str(e), 1