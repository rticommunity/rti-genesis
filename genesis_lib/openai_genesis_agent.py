#!/usr/bin/env python3
"""
OpenAI Genesis Agent - LLM Provider Implementation

This module provides the OpenAIGenesisAgent class, which implements the OpenAI API
integration for the Genesis framework. It serves as the reference implementation for
creating new LLM provider agents.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the Inheritance Hierarchy
=================================================================================================

GenesisAgent (genesis_lib/genesis_agent.py)
├─ Provider-Agnostic Business Logic:
│  ├─ process_request() - Main request processing flow
│  ├─ process_agent_request() - Agent-to-agent communication wrapper
│  ├─ _orchestrate_tool_request() - Multi-turn conversation orchestration
│  ├─ _route_tool_call() - Routes tool calls to functions/agents/internal tools
│  ├─ _ensure_internal_tools_discovered() - Discovers @genesis_tool methods
│  ├─ _get_available_functions() - Returns discovered external functions
│  ├─ _get_available_agent_tools() - Returns discovered agents
│  ├─ _call_function() - Executes external function via RPC
│  ├─ _call_agent() - Calls another agent via agent-to-agent protocol
│  └─ _call_internal_tool() - Executes internal @genesis_tool method
│
└─ Abstract Methods (MUST implement in provider):
   ├─ _call_llm() - Call provider's API
   ├─ _format_messages() - Format conversation in provider's format
   ├─ _extract_tool_calls() - Parse tool calls from provider's response
   ├─ _extract_text_response() - Extract text from provider's response
   ├─ _create_assistant_message() - Create assistant message dict
   ├─ _get_tool_schemas() - Generate tool schemas in provider's format
   └─ _get_tool_choice() - Return provider's tool choice setting

    ↓ inherits

MonitoredAgent (genesis_lib/monitored_agent.py)
├─ Observability & Monitoring:
│  ├─ Wraps process_request() with BUSY/READY/DEGRADED state publishing
│  ├─ _publish_llm_call_start() - Publish LLM call start event
│  ├─ _publish_llm_call_complete() - Publish LLM call complete event
│  ├─ _publish_classification_node() - Publish tool classification
│  └─ _publish_agent_chain_event() - Publish agent-to-agent events
│
└─ Note: All monitoring is AUTOMATIC - providers don't need to implement anything

    ↓ inherits

OpenAIGenesisAgent (THIS FILE - genesis_lib/openai_genesis_agent.py)
└─ OpenAI-Specific Implementation:
   ├─ client.chat.completions.create() - OpenAI API calls
   ├─ OpenAI message format: [{"role": "system"|"user"|"assistant", "content": "..."}]
   ├─ OpenAI tool format: {"type": "function", "function": {...}}
   └─ Implements 7 abstract methods (see detailed docs below)

=================================================================================================
WHAT YOU INHERIT FOR FREE - No Need to Implement
=================================================================================================

When you create a new provider (AnthropicGenesisAgent, GeminiGenesisAgent, etc.), you 
automatically get ALL of this functionality without writing any code:

1. **Tool Discovery** (from GenesisAgent):
   - External function discovery via DDS advertisements
   - Agent-to-agent discovery via DDS advertisements
   - Internal tool discovery via @genesis_tool decorator
   - Automatic tool registration and caching

2. **Tool Routing** (from GenesisAgent):
   - _route_tool_call() automatically determines tool type
   - Routes to functions, agents, or internal tools
   - Handles argument parsing and result extraction
   - Error handling and logging

3. **Multi-Turn Orchestration** (from GenesisAgent):
   - _orchestrate_tool_request() handles conversation loops
   - Calls LLM → extracts tool calls → executes tools → calls LLM with results → repeat
   - Manages conversation history across turns
   - Handles max turn limits and timeout scenarios

4. **Memory Management** (from GenesisAgent):
   - Conversation history storage and retrieval
   - Automatic memory writes after each turn
   - Memory pruning and summarization (if using advanced adapters)
   - Context window management

5. **Monitoring & Observability** (from MonitoredAgent):
   - State machine (DISCOVERING → READY → BUSY → READY or DEGRADED)
   - Event publishing for visualization (graph topology, chains, events)
   - Automatic tracing of all LLM calls and tool executions
   - Error tracking and recovery mechanisms

6. **Agent Communication** (from MonitoredAgent):
   - process_agent_request() for agent-to-agent calls
   - Chain event tracking across agent boundaries
   - Automatic conversation ID propagation
   - Source agent attribution

7. **RPC Infrastructure** (from MonitoredAgent via GenesisApp):
   - DDS participant and topic management
   - Service registration and advertisement
   - Request/reply pattern handling
   - Content filtering by service instance tags

8. **User-Defined Capabilities** (from GenesisAgent) - **OPTIONAL**:
   - define_capabilities() - Programmatic capability definition
   - add_capability() - Add individual capabilities
   - add_specialization() - Add domain specializations
   - set_performance_metric() - Set performance characteristics
   - get_agent_capabilities() - Override for custom logic
   - Class-level CAPABILITIES attribute support
   - Rich metadata for agent discovery and routing
   - **If not used**: Automatic intelligent capability generation (model-based → heuristic)

=================================================================================================
WHAT YOU MUST IMPLEMENT - The 7 Abstract Methods
=================================================================================================

To create a new provider, you ONLY need to implement these 7 methods (see detailed docs below):

1. _call_llm() - How to call your provider's API
2. _format_messages() - How to format conversation history
3. _extract_tool_calls() - How to parse tool calls from responses
4. _extract_text_response() - How to extract text from responses
5. _create_assistant_message() - How to create assistant message dicts
6. _get_tool_schemas() - How to generate tool schemas
7. _get_tool_choice() - What tool choice setting to use

That's it! ~50-100 lines of provider-specific code gives you a fully functional agent
with discovery, routing, orchestration, monitoring, and multi-turn conversations.

=================================================================================================
IMPLEMENTATION GUIDE - Step-by-Step for New Providers
=================================================================================================

Example: Creating AnthropicGenesisAgent

1. Copy this file to `anthropic_genesis_agent.py`
2. Rename class to `AnthropicGenesisAgent`
3. Replace OpenAI client with Anthropic client
4. Update __init__() to use Anthropic API key and models
5. Implement the 7 abstract methods (see detailed docs below)
6. Update tool schema generation methods (_get_all_tool_schemas_for_anthropic)
7. Test using existing test suite (just swap the agent class)

That's it! Your new agent will automatically integrate with all existing infrastructure.

=================================================================================================

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
import sys
import logging
import json
import asyncio
import time
import traceback
import uuid
from openai import OpenAI
from typing import Dict, Any, List, Optional
import collections

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.function_classifier import FunctionClassifier
from genesis_lib.generic_function_client import GenericFunctionClient
from genesis_lib.schema_generators import get_schema_generator

logger = logging.getLogger("openai_genesis_agent")

class OpenAIGenesisAgent(MonitoredAgent):
    """
    OpenAI API implementation of GenesisAgent.
    
    This class implements the OpenAI API integration for the Genesis framework,
    serving as the reference implementation for creating new LLM provider agents.
    """
    
    def __init__(self, model_name="gpt-4o", classifier_model_name="gpt-4o-mini", 
                 domain_id: int = 0, agent_name: str = "OpenAIAgent", 
                 base_service_name: str = "OpenAIChat",
                 description: str = None, 
                 enable_tracing: bool = False,
                 enable_monitoring: bool = True,
                 enable_agent_communication: bool = True, 
                 memory_adapter=None,
                 auto_run: bool = True, 
                 service_instance_tag: str = ""):
        """
        Initialize OpenAI-based Genesis agent.
        
        Args:
            model_name: OpenAI model identifier (e.g., "gpt-4o", "gpt-4o-mini")
            classifier_model_name: Model for function classification (usually cheaper/faster)
            domain_id: DDS domain ID (0-232) - network isolation boundary
            agent_name: Human-readable instance identifier
            base_service_name: Service capability type (e.g., "OpenAIChat", "WeatherService")
            description: Optional human-readable description for monitoring/docs
            enable_tracing: Enable detailed debug logging (use in development only)
            enable_monitoring: Enable monitoring and observability features (default True)
            enable_agent_communication: Allow this agent to discover and call other agents
            memory_adapter: Pluggable conversation memory backend
            auto_run: Automatically start run() loop if event loop exists
            service_instance_tag: Optional tag for content filtering
        """
        # Store tracing configuration before super().__init__ since parent might use it
        self.enable_tracing = enable_tracing
        
        logger.debug(f"OpenAIGenesisAgent __init__ called for {agent_name}")
        
        if self.enable_tracing:
            logger.debug(f"Initializing OpenAIGenesisAgent with model {model_name}")
        
        # Store provider-specific model configuration
        # For Anthropic: {"model_name": "claude-3-5-sonnet-20241022", ...}
        # For Google: {"model_name": "gemini-1.5-pro", ...}
        self.model_config = {
            "model_name": model_name,
            "classifier_model_name": classifier_model_name
        }
        
        # Initialize parent class (MonitoredAgent → GenesisAgent)
        # Pass classifier provider and model - GenesisAgent will create the LLM via LLMFactory
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="AGENT",  # PRIMARY_AGENT for monitoring (coordinator role)
            description=description or f"An OpenAI-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            enable_monitoring=enable_monitoring,
            memory_adapter=memory_adapter,
            auto_run=auto_run,
            service_instance_tag=service_instance_tag,
            classifier_provider="openai" if enable_agent_communication else None,
            classifier_model=classifier_model_name if enable_agent_communication else None
        )
        
        # Get provider API key from environment
        # For Anthropic: os.environ.get("ANTHROPIC_API_KEY")
        # For Google: os.environ.get("GOOGLE_API_KEY")
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize provider-specific client
        # For Anthropic: self.client = anthropic.Anthropic(api_key=self.api_key)
        # For Google: self.client = genai.configure(api_key=self.api_key)
        self.client = OpenAI(api_key=self.api_key)

        # Provider-specific tool_choice configuration
        # OpenAI: "auto" | "required" | "none"
        # Anthropic: {"type": "auto"} | {"type": "any"} | {"type": "tool", "name": "..."}
        # Google: "AUTO" | "ANY" | "NONE"
        #
        # Controlled via GENESIS_TOOL_CHOICE environment variable:
        # - "auto" (default): LLM decides whether to use tools - PRODUCTION setting
        # - "required": LLM MUST use tools - TESTING ONLY (deterministic, slow, expensive)
        # - "none": LLM cannot use tools - TESTING edge cases
        self.openai_tool_choice = os.getenv("GENESIS_TOOL_CHOICE", "auto")
        
        # Initialize generic function client for RPC calls
        # Uses the agent's FunctionRegistry (shared with GenesisApp) for function discovery
        # This is provider-agnostic - same for all LLM providers
        logger.debug(f"===== TRACING: Initializing GenericFunctionClient using agent app's FunctionRegistry: {id(self.app.function_registry)} =====")
        self.generic_client = GenericFunctionClient(function_registry=self.app.function_registry)
        
        # Initialize function classifier (OpenAI-specific)
        # Used to intelligently select relevant functions from large function sets
        # For other providers: pass their client (e.g., anthropic_client)
        # Or skip if not needed (just expose all tools to LLM)
        self.function_classifier = FunctionClassifier(llm_client=self.client)
        
        # Define system prompts for different scenarios
        # These are OpenAI-tuned but work well for most providers
        # Adjust tone/style for your provider's personality
        self.function_based_system_prompt = """You are a helpful assistant that can perform various operations using remote services and consult specialized agents.
You have access to:
1. Functions that can help you solve problems (calculations, data processing, etc.)
2. Specialized agents that have expertise in specific domains (weather, finance, etc.)
3. An external memory system that stores our conversation history, allowing you to recall previous interactions

When a function or specialized agent is available that can help with a task, you should use it rather than trying to solve the problem yourself.
This is especially important for:
- Mathematical calculations (use calculator functions)
- Domain-specific queries (consult specialized agents)
- Data processing tasks (use appropriate functions)

You can recall information from our previous conversations using your memory system. When users ask about something they mentioned before, you should be able to recall and reference that information.

Always explain your reasoning and the steps you're taking when using tools or consulting agents."""

        self.general_system_prompt = """You are a helpful and engaging AI assistant with an external memory system that stores our conversation history.
You can:
- Answer questions and provide information
- Tell jokes and engage in casual conversation
- Help with creative tasks like writing and brainstorming
- Provide explanations and teach concepts
- Assist with problem-solving and decision making
- Recall information from our previous conversations

You can remember and reference information that users have shared with you in our conversation. When users ask about something they mentioned before, you should be able to recall that information.

Be friendly, professional, and maintain a helpful tone while being concise and clear in your responses."""

        # Start with general prompt, will switch to function-based if tools are discovered
        self.system_prompt = self.general_system_prompt
        
        # Set agent capabilities for monitoring/discovery
        # Other agents can query these to understand what this agent can do
        self.set_agent_capabilities(
            supported_tasks=["text_generation", "conversation"],
            additional_capabilities=self.model_config
        )
        
        if self.enable_tracing:
            logger.debug("OpenAIGenesisAgent initialized successfully")
    
    # =============================================================================================
    # TOOL SCHEMA GENERATION - Provider-Specific Format Conversion
    # =============================================================================================
    # These methods convert Genesis's universal tool representations into provider-specific formats
    # Each provider has different schema requirements - implement accordingly
    
    def _convert_agents_to_tools(self):
        """
        Convert discovered agents to OpenAI tool schema format.
        
        Returns:
            List of agent tools in OpenAI format
        """
        logger.debug("===== TRACING: Converting agent schemas to OpenAI tool format =====")
        
        # Get universal agent schemas from parent (provider-agnostic)
        agent_schemas = self._get_agent_tool_schemas()
        
        # Wrap in OpenAI-specific format
        openai_tools = []
        for schema in agent_schemas:
            openai_tools.append({
                "type": "function",  # OpenAI requires this wrapper
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": {
                        "type": "object",  # OpenAI requires explicit "object" type
                        "properties": {
                            "message": schema["parameters"]["message"]
                        },
                        "required": schema["required"]
                    }
                }
            })
            logger.debug(f"===== TRACING: Wrapped agent tool in OpenAI format: {schema['name']} =====")
        
        logger.debug(f"===== TRACING: Generated {len(openai_tools)} OpenAI agent tools =====")
        return openai_tools
    
    def _get_function_schemas_for_openai(self, relevant_functions: Optional[List[str]] = None):
        """
        Convert discovered external functions to OpenAI tool schema format.
        
        Args:
            relevant_functions: Optional list of function names to filter
            
        Returns:
            List of function schemas in OpenAI format
        """
        logger.debug("===== TRACING: Converting function schemas for OpenAI =======")
        function_schemas = []
        
        # Get all discovered functions from parent's registry
        available_functions = self._get_available_functions()
        
        for name, func_info in available_functions.items():
            # Optional filtering if relevant_functions is provided
            # Used by function classifier to show LLM only relevant tools
            if relevant_functions is not None and name not in relevant_functions:
                continue
            
            # Wrap in OpenAI's tool format
            schema = {
                "type": "function",  # OpenAI wrapper
                "function": {
                    "name": name,
                    "description": func_info["description"],
                    "parameters": func_info["schema"]  # Already JSON Schema
                }
            }
            function_schemas.append(schema)
            logger.debug(f"===== TRACING: Added schema for function: {name} =====")
        
        return function_schemas
    
    def _get_all_tool_schemas_for_openai(self, relevant_functions: Optional[List[str]] = None):
        """
        Get ALL tool schemas in OpenAI format: functions + agents + internal tools.
        
        Args:
            relevant_functions: Optional list of function names to filter
            
        Returns:
            Combined list of all tool schemas in OpenAI format
        """
        logger.debug("===== TRACING: Getting ALL tool schemas (functions + agents + internal tools) for OpenAI =====")
        
        # Get each tool type in OpenAI format
        function_tools = self._get_function_schemas_for_openai(relevant_functions)
        agent_tools = self._convert_agents_to_tools()
        internal_tools = self._get_internal_tool_schemas_for_openai()
        
        # Combine all tool types into one list
        all_tools = function_tools + agent_tools + internal_tools
        
        logger.debug(f"===== TRACING: Combined {len(function_tools)} function tools + {len(agent_tools)} agent tools + {len(internal_tools)} internal tools = {len(all_tools)} total tools =====")
        
        return all_tools

    def _get_internal_tool_schemas_for_openai(self) -> List[Dict[str, Any]]:
        """
        Generate OpenAI tool schemas for internal @genesis_tool decorated methods.
        
        Returns:
            List of internal tool schemas in OpenAI format
        """
        # Return empty list if no internal tools discovered
        if not hasattr(self, 'internal_tools_cache') or not self.internal_tools_cache:
            return []
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generating OpenAI schemas for {len(self.internal_tools_cache)} internal tools =====")
        
        internal_schemas = []
        
        # Get provider-specific schema generator
        # For Anthropic: get_schema_generator("anthropic")
        # For Google: get_schema_generator("gemini")
        schema_generator = get_schema_generator("openai")
        
        # Generate schema for each internal tool
        for tool_name, tool_info in self.internal_tools_cache.items():
            metadata = tool_info["metadata"]
            
            try:
                # Generate provider-specific schema from universal metadata
                openai_schema = schema_generator.generate_tool_schema(metadata)
                internal_schemas.append(openai_schema)
                
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Generated schema for internal tool: {tool_name} =====")
                    
            except Exception as e:
                logger.error(f"Error generating schema for internal tool {tool_name}: {e}")
                
        return internal_schemas
    
    # =============================================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS - Required by GenesisAgent
    # =============================================================================================
    # These 7 methods are the ONLY provider-specific code you need to write!
    # Everything else (discovery, routing, orchestration, monitoring) is inherited.
    
    async def _get_tool_schemas(self) -> List[Dict]:
        """
        Get all tool schemas in provider-specific format.
        
        Returns:
            List of tool schemas in OpenAI format
        """
        return self._get_all_tool_schemas_for_openai()
    
    def _get_tool_choice(self) -> str:
        """
        Get provider-specific tool choice setting.
        
        Returns:
            Tool choice setting in OpenAI format
        """
        return self.openai_tool_choice
    
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None, 
                        tool_choice: str = "auto") -> Any:
        """
        Call the LLM provider's API.
        
        Args:
            messages: Conversation history in OpenAI format
            tools: Optional tool schemas in OpenAI format
            tool_choice: How LLM should use tools
            
        Returns:
            OpenAI response object
        """
        # Build API call parameters
        kwargs = {
            "model": self.model_config['model_name'],
            "messages": messages
        }
        
        # Add tools if provided (for tool-based conversations)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        
        # Make the API call
        # For Anthropic: self.client.messages.create(**kwargs)
        # For Google: model.generate_content(**kwargs)
        return self.client.chat.completions.create(**kwargs)

    def _format_messages(self, user_message: str, system_prompt: str, 
                         memory_items: List[Dict]) -> List[Dict]:
        """
        Format conversation history in provider-specific message format.
        
        Args:
            user_message: Current message from user
            system_prompt: System instructions for agent behavior
            memory_items: Retrieved conversation history
            
        Returns:
            List of messages in OpenAI format
        """
        # Start with system message (OpenAI-specific placement)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history from memory
        for entry in memory_items:
            item = entry["item"]
            meta = entry.get("metadata", {})
            role = meta.get("role")
            
            # Filter out tool messages - they require full tool_calls context
            # which isn't preserved in memory (only the result strings are saved)
            if role in ("tool", "assistant_tool"):
                continue
            
            # Validate role or infer from position
            if role not in ("user", "assistant"):
                # Fallback: alternate roles if metadata is missing
                idx = memory_items.index(entry)
                role = "user" if idx % 2 == 0 else "assistant"
            
            messages.append({"role": role, "content": str(item)})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict]]:
        """
        Extract tool calls from provider's response.
        
        Args:
            response: OpenAI response object
            
        Returns:
            List of tool calls in standard format, or None if no tool calls
        """
        # Access the message from OpenAI response
        message = response.choices[0].message
        
        # Check if tool_calls exist
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return None
        
        # Convert to standard format
        return [
            {
                'id': tc.id,  # OpenAI provides unique IDs
                'name': tc.function.name,
                'arguments': json.loads(tc.function.arguments)  # OpenAI returns JSON string
            }
            for tc in message.tool_calls
        ]

    def _extract_text_response(self, response: Any) -> str:
        """
        Extract text response from provider's response.
        
        Args:
            response: OpenAI response object
            
        Returns:
            Extracted text content as string
        """
        # OpenAI stores text in message.content
        # For Anthropic: filter content blocks by type="text"
        # For Google: access candidates[0].content.parts[0].text
        return response.choices[0].message.content

    def _create_assistant_message(self, response: Any) -> Dict:
        """
        Create assistant message dict from provider's response.
        
        Args:
            response: OpenAI response object
            
        Returns:
            Message dict in OpenAI format, ready to add to conversation history
        """
        # Extract message from OpenAI response
        message = response.choices[0].message
        
        # Create base assistant message
        assistant_msg = {
            "role": "assistant",
            "content": message.content if message.content is not None else ""
        }
        
        # Add tool_calls if present (CRITICAL for OpenAI)
        # Without this, next turn will fail with:
        # "Invalid parameter: messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
        if hasattr(message, 'tool_calls') and message.tool_calls:
            assistant_msg["tool_calls"] = message.tool_calls
        
        return assistant_msg
    
    # =============================================================================================
    # UTILITY METHODS - Optional but Helpful
    # =============================================================================================
    
    async def close(self):
        """
        Clean up provider-specific resources.
        """
        try:
            # Close OpenAI-specific resources
            if hasattr(self, 'generic_client') and self.generic_client is not None:
                if asyncio.iscoroutinefunction(self.generic_client.close):
                    await self.generic_client.close()
                else:
                    self.generic_client.close()
            
            # Close base class resources (DDS, RPC, monitoring)
            await super().close()
            
            logger.debug(f"OpenAIGenesisAgent closed successfully")
        except Exception as e:
            logger.error(f"Error closing OpenAIGenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    async def process_message(self, message: str) -> str:
        """
        Process a message and return response (convenience method).
        
        Args:
            message: User message to process
            
        Returns:
            Agent response text
        """
        try:
            # Process via standard process_request (gets monitoring, etc.)
            response = await self.process_request({"message": message})
            
            # Publish monitoring event (optional)
            self.publish_monitoring_event(
                event_type="AGENT_RESPONSE",
                result_data={"response": response}
            )
            
            return response.get("message", "No response generated")
            
        except Exception as e:
            # Publish error monitoring event (optional)
            self.publish_monitoring_event(
                event_type="AGENT_STATUS",
                status_data={"error": str(e)}
            )
            raise
