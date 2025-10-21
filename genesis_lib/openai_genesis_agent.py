#!/usr/bin/env python3
"""
OpenAI Genesis Agent - LLM Provider Implementation Template

This module serves as the REFERENCE IMPLEMENTATION for creating new LLM provider agents.
It demonstrates how to implement the 7 abstract methods required by GenesisAgent to create
a fully functional agent with minimal code (~500 lines vs 2000+ without the framework).

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the Inheritance Hierarchy
=================================================================================================

GenesisAgent (genesis_lib/agent.py)
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
    
    This class serves as a reference implementation and template for creating new LLM providers.
    Study this implementation to understand how to integrate any LLM API with Genesis.
    """
    
    def __init__(self, model_name="gpt-4o", classifier_model_name="gpt-4o-mini", 
                 domain_id: int = 0, agent_name: str = "OpenAIAgent", 
                 base_service_name: str = "OpenAIChat",
                 description: str = None, enable_tracing: bool = False, 
                 enable_agent_communication: bool = True, memory_adapter=None,
                 auto_run: bool = True, service_instance_tag: str = ""):
        """
        Initialize OpenAI-based Genesis agent.
        
        Provider Implementation Notes:
        ------------------------------
        For a new provider (e.g., Anthropic), you would:
        1. Replace OpenAI() client with your provider's client (e.g., anthropic.Anthropic())
        2. Change model_name to your provider's model (e.g., "claude-3-5-sonnet-20241022")
        3. Update API key environment variable (e.g., "ANTHROPIC_API_KEY")
        4. Adjust tool_choice values to match provider (e.g., {"type": "auto"} for Anthropic)
        
        Args:
            model_name: OpenAI model identifier (e.g., "gpt-4o", "gpt-4o-mini")
                       For Anthropic: "claude-3-5-sonnet-20241022"
                       For Google: "gemini-1.5-pro"
                       
            classifier_model_name: Model for function classification (usually cheaper/faster)
                                  Not all providers need this - some use the same model
                                  
            domain_id: DDS domain ID (0-232) - network isolation boundary
                      All agents/services on same domain can discover each other
                      Use different domains for: dev/staging/prod, different projects, testing
                      
            agent_name: Human-readable instance identifier (e.g., "WeatherBot_Primary")
                       Used for: logging, monitoring UI, human identification
                       Multiple agents can have different agent_names but same base_service_name
                       
            base_service_name: Service capability type (e.g., "OpenAIChat", "WeatherService")
                              Used for: RPC service naming, capability discovery, service routing
                              Multiple agents with same base_service_name provide redundancy
                              
            description: Optional human-readable description for monitoring/docs
            
            enable_tracing: Enable detailed debug logging (use in development only)
                           Logs: LLM calls, tool calls, responses, state transitions
                           
            enable_agent_communication: Allow this agent to discover and call other agents
                                       Disable for: specialized tools, security boundaries
                                       
            memory_adapter: Pluggable conversation memory backend
                           None = SimpleMemoryAdapter (in-memory, ephemeral)
                           Custom = Your implementation (vector DB, graph DB, persistent)
                           
            auto_run: Automatically start run() loop if event loop exists
                     False = You must call await agent.run() manually
                     
            service_instance_tag: Optional tag for content filtering
                                 Use for: versioning (v1/v2), environments (prod/staging)
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
        # This sets up: DDS participant, RPC service, monitoring, memory, etc.
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="AGENT",  # PRIMARY_AGENT for monitoring (coordinator role)
            description=description or f"An OpenAI-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=memory_adapter,
            auto_run=auto_run,
            service_instance_tag=service_instance_tag
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
        
        Provider Implementation Guide:
        ------------------------------
        This method shows how to convert Genesis's universal agent schemas into
        provider-specific tool schemas.
        
        What You Get (from parent class):
            - self._get_agent_tool_schemas() returns universal agent schemas:
              [
                {
                  "name": "WeatherAgent",
                  "description": "Specialized agent for weather queries",
                  "parameters": {
                    "message": {
                      "type": "string",
                      "description": "Message to send to the agent"
                    }
                  },
                  "required": ["message"]
                }
              ]
        
        What You Must Return (provider-specific format):
        
        OpenAI Format (this implementation):
            [
              {
                "type": "function",
                "function": {
                  "name": "WeatherAgent",
                  "description": "Specialized agent for weather queries",
                  "parameters": {
                    "type": "object",
                    "properties": {
                      "message": {"type": "string", "description": "..."}
                    },
                    "required": ["message"]
                  }
                }
              }
            ]
        
        Anthropic Format (for reference):
            [
              {
                "name": "WeatherAgent",
                "description": "Specialized agent for weather queries",
                "input_schema": {
                  "type": "object",
                  "properties": {
                    "message": {"type": "string", "description": "..."}
                  },
                  "required": ["message"]
                }
              }
            ]
        
        Google Gemini Format (for reference):
            [
              {
                "name": "WeatherAgent",
                "description": "Specialized agent for weather queries",
                "parameters": {
                  "type_": "OBJECT",
                  "properties": {
                    "message": {"type_": "STRING", "description": "..."}
                  },
                  "required": ["message"]
                }
              }
            ]
        
        Key Differences Across Providers:
            - OpenAI: Wraps in {"type": "function", "function": {...}}
            - Anthropic: Uses "input_schema" instead of "parameters"
            - Google: Uses "type_" enum values (OBJECT, STRING) instead of strings
            - Some providers support additional fields: examples, strict mode, etc.
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
        
        Provider Implementation Guide:
        ------------------------------
        This method shows how to convert Genesis function schemas into provider-specific formats.
        
        What You Get (from parent class):
            - self._get_available_functions() returns discovered functions:
              {
                "add": {
                  "description": "Add two numbers",
                  "schema": {  # Already in JSON Schema format
                    "type": "object",
                    "properties": {
                      "x": {"type": "number", "description": "First number"},
                      "y": {"type": "number", "description": "Second number"}
                    },
                    "required": ["x", "y"]
                  }
                },
                ...
              }
        
        What You Must Return (provider-specific format):
        
        OpenAI Format (this implementation):
            [
              {
                "type": "function",
                "function": {
                  "name": "add",
                  "description": "Add two numbers",
                  "parameters": {  # Directly use the JSON Schema
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                  }
                }
              }
            ]
        
        Anthropic Format (for reference):
            [
              {
                "name": "add",
                "description": "Add two numbers",
                "input_schema": {  # Anthropic uses "input_schema"
                  "type": "object",
                  "properties": {...},
                  "required": [...]
                }
              }
            ]
        
        Google Gemini Format (for reference):
            Function declarations with FunctionDeclaration type
            Must convert JSON Schema types to Gemini Type enums
        
        Important Notes:
            - Genesis functions already provide JSON Schema-compatible parameter definitions
            - Most providers accept JSON Schema with minor adaptations
            - Key differences: wrapper format, field names, type representations
            - relevant_functions parameter allows filtering (for classification/optimization)
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
        
        Provider Implementation Guide:
        ------------------------------
        This is your main "schema aggregator" method that combines all tool types.
        
        Genesis Tool Ecosystem:
            1. External Functions - Discovered via DDS (services like Calculator, Weather)
            2. Agents - Other agents discovered via DDS (specialized agents)
            3. Internal Tools - Methods decorated with @genesis_tool in this class
        
        For a new provider:
            1. Create provider-specific schema generation methods (like we have _for_openai)
            2. Call parent methods to get universal schemas
            3. Convert to provider format
            4. Combine and return
        
        Example for Anthropic:
            def _get_all_tool_schemas_for_anthropic(self):
                function_tools = self._get_function_schemas_for_anthropic()
                agent_tools = self._convert_agents_to_anthropic_tools()
                internal_tools = self._get_internal_tool_schemas_for_anthropic()
                return function_tools + agent_tools + internal_tools
        
        This unified approach gives your LLM access to the complete tool ecosystem!
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
        
        Provider Implementation Guide:
        ------------------------------
        Internal tools are methods in your agent class decorated with @genesis_tool.
        They provide agent-specific capabilities (e.g., memory search, config changes).
        
        What You Get (from parent class):
            - self.internal_tools_cache contains discovered internal tools:
              {
                "search_memory": {
                  "method": <bound method>,
                  "metadata": {
                    "name": "search_memory",
                    "description": "Search conversation memory",
                    "parameters": {
                      "query": {"type": "string", "description": "Search query"}
                    },
                    "returns": {"type": "array", "description": "Matching memories"}
                  }
                }
              }
        
        What You Must Do:
            1. Get the schema generator for your provider (OpenAI, Anthropic, etc.)
            2. For each internal tool, generate provider-specific schema
            3. Return list of schemas
        
        Schema Generators (genesis_lib/schema_generators.py):
            - get_schema_generator("openai") - OpenAI format
            - get_schema_generator("anthropic") - Anthropic format
            - get_schema_generator("gemini") - Google Gemini format
            - Extend with your own if needed
        
        For Anthropic example:
            schema_generator = get_schema_generator("anthropic")
            anthropic_schema = schema_generator.generate_tool_schema(metadata)
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
        ABSTRACT METHOD #1: Get all tool schemas in provider-specific format.
        
        Purpose:
        --------
        Called by parent's process_request() to get tools for the LLM call.
        This is your "schema entry point" - return all tools in your provider's format.
        
        What This Does (for OpenAI):
        ----------------------------
        Returns all discovered tools (functions + agents + internal tools) in OpenAI format.
        
        What Other Providers Would Do:
        ------------------------------
        Anthropic: Return tools in Anthropic's format (name, description, input_schema)
        Google: Return tools in Gemini's FunctionDeclaration format
        Local LLM: Return tools in whatever format your model expects (often OpenAI-compatible)
        
        Implementation Pattern:
        ----------------------
        1. Create a provider-specific aggregator method (like _get_all_tool_schemas_for_openai)
        2. That method calls schema conversion methods for each tool type
        3. This method just delegates to the aggregator
        
        Called By:
        ---------
        - GenesisAgent.process_request() when initializing tool-based conversation
        
        Returns:
        -------
        List of tool schemas in provider-specific format
        """
        return self._get_all_tool_schemas_for_openai()
    
    def _get_tool_choice(self) -> str:
        """
        ABSTRACT METHOD #2: Get provider-specific tool choice setting.
        
        Purpose:
        --------
        Tells the LLM how it should use tools (must use, can use, cannot use).
        
        What This Returns (for OpenAI):
        ------------------------------
        - "auto": LLM decides whether to use tools (PRODUCTION default)
        - "required": LLM must use a tool (TESTING only - deterministic but expensive)
        - "none": LLM cannot use tools (edge case testing)
        
        What Other Providers Would Return:
        ----------------------------------
        Anthropic:
            - {"type": "auto"}: LLM decides
            - {"type": "any"}: LLM must use any tool
            - {"type": "tool", "name": "specific_tool"}: Must use specific tool
        
        Google Gemini:
            - "AUTO": LLM decides
            - "ANY": Must use a tool
            - "NONE": Cannot use tools
        
        Local LLMs:
            - Often use OpenAI-compatible values ("auto", "required", "none")
        
        Environment Control:
        -------------------
        Controlled via GENESIS_TOOL_CHOICE environment variable:
        - Allows runtime configuration without code changes
        - Tests can set to "required" for deterministic behavior
        - Production should use "auto" for best UX
        
        Called By:
        ---------
        - GenesisAgent.process_request() when calling _orchestrate_tool_request()
        - Used in every LLM call that includes tools
        
        Returns:
        -------
        Tool choice setting in provider's format
        """
        return self.openai_tool_choice
    
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None, 
                        tool_choice: str = "auto") -> Any:
        """
        ABSTRACT METHOD #3: Call the LLM provider's API.
        
        Purpose:
        --------
        This is your "API bridge" - the only place where you actually call your provider's API.
        All other code is provider-agnostic.
        
        What This Does (for OpenAI):
        ----------------------------
        Calls OpenAI's chat.completions.create() API with:
        - model: From self.model_config (e.g., "gpt-4o")
        - messages: Formatted conversation history
        - tools: Optional tool schemas (if available)
        - tool_choice: How to use tools ("auto", "required", "none")
        
        What Other Providers Would Do:
        ------------------------------
        Anthropic:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                messages=messages,  # Note: Anthropic separates system message
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=4096  # Anthropic requires max_tokens
            )
        
        Google Gemini:
            model = genai.GenerativeModel('gemini-1.5-pro', tools=tools)
            response = model.generate_content(messages)
        
        Local LLM (OpenAI-compatible):
            response = self.client.chat.completions.create(
                model="llama-3-70b",
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                base_url="http://localhost:8000/v1"  # Point to local server
            )
        
        Important Notes:
        ---------------
        - Parent class handles retry logic, error handling, and monitoring
        - You just need to make the API call and return the response
        - Return the raw response object - parent will call _extract_* methods
        - Tools parameter can be None (for non-tool conversations)
        
        Called By:
        ---------
        - GenesisAgent._orchestrate_tool_request() for tool-based conversations
        - GenesisAgent.process_request() for simple conversations
        - Called multiple times in multi-turn conversations
        
        Args:
        ----
        messages: Conversation history in provider-specific format (from _format_messages)
        tools: Optional tool schemas in provider-specific format (from _get_tool_schemas)
        tool_choice: How LLM should use tools (from _get_tool_choice)
        
        Returns:
        -------
        Provider-specific response object (will be passed to _extract_* methods)
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
        ABSTRACT METHOD #4: Format conversation history in provider-specific message format.
        
        Purpose:
        --------
        Convert Genesis's universal conversation representation into your provider's
        expected message format.
        
        What This Does (for OpenAI):
        ----------------------------
        Converts to OpenAI's format:
        [
          {"role": "system", "content": "You are a helpful assistant..."},
          {"role": "user", "content": "Previous user message"},
          {"role": "assistant", "content": "Previous assistant response"},
          {"role": "user", "content": "Current user message"}
        ]
        
        What You Receive:
        ----------------
        user_message: str
            - Current message from user
            
        system_prompt: str
            - System prompt defining agent behavior
            - From self.function_based_system_prompt or self.general_system_prompt
            
        memory_items: List[Dict]
            - Retrieved conversation history from memory adapter
            - Format: [
                {
                  "item": "message content",
                  "metadata": {"role": "user"|"assistant"|"tool", ...}
                },
                ...
              ]
        
        What Other Providers Would Return:
        ----------------------------------
        Anthropic:
            - Separate system parameter from messages
            - Messages only contain user/assistant roles
            - Example:
              messages = [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
              ]
              # system_prompt passed separately to API call
        
        Google Gemini:
            - Uses Content objects with parts
            - System instructions separate
            - Example:
              [
                Content(role="user", parts=["..."]),
                Content(role="model", parts=["..."])  # Note: "model" not "assistant"
              ]
        
        Local LLMs:
            - Often use OpenAI format (most common)
            - Some may have custom formats
        
        Important Implementation Notes:
        ------------------------------
        1. **Role Handling**:
           - Map Genesis roles to provider roles
           - OpenAI: "user", "assistant", "system", "tool"
           - Anthropic: "user", "assistant"
           - Google: "user", "model"
        
        2. **Tool Message Filtering**:
           - Tool messages require complex context (tool_calls from previous assistant message)
           - Safer to filter them out when reconstructing from memory
           - Multi-turn conversations handle tool messages differently
        
        3. **Conversation Ordering**:
           - Maintain chronological order
           - Some providers require alternating user/assistant
           - Handle consecutive same-role messages appropriately
        
        4. **System Prompt Placement**:
           - OpenAI: First message with role="system"
           - Anthropic: Separate system parameter
           - Google: Separate system_instruction parameter
        
        Called By:
        ---------
        - GenesisAgent._orchestrate_tool_request() at start of conversation
        - GenesisAgent.process_request() for simple (non-tool) conversations
        
        Args:
        ----
        user_message: Current message from user
        system_prompt: System instructions for agent behavior
        memory_items: Retrieved conversation history
        
        Returns:
        -------
        List of messages in provider-specific format
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
        ABSTRACT METHOD #5: Extract tool calls from provider's response.
        
        Purpose:
        --------
        Parse the provider's response to detect if the LLM wants to call tools.
        This determines whether we execute tools or return the text response.
        
        What This Does (for OpenAI):
        ----------------------------
        Checks if response contains tool_calls and extracts them into standard format:
        [
          {
            'id': 'call_abc123',
            'name': 'add',
            'arguments': {'x': 5, 'y': 3}
          },
          ...
        ]
        
        What You Receive:
        ----------------
        response: Provider-specific response object
            - OpenAI: ChatCompletion object
            - Anthropic: Message object
            - Google: GenerateContentResponse object
        
        What Other Providers Would Do:
        ------------------------------
        Anthropic:
            # Anthropic uses "content blocks" with type="tool_use"
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        'id': block.id,
                        'name': block.name,
                        'arguments': block.input  # Already a dict
                    })
            return tool_calls if tool_calls else None
        
        Google Gemini:
            # Google uses function_calls in candidates
            if not response.candidates[0].content.parts:
                return None
            tool_calls = []
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    tool_calls.append({
                        'id': str(uuid.uuid4()),  # Google doesn't provide IDs
                        'name': part.function_call.name,
                        'arguments': dict(part.function_call.args)
                    })
            return tool_calls if tool_calls else None
        
        Standard Format:
        ---------------
        Always return tool calls in this standard format (or None):
        [
          {
            'id': str,        # Unique identifier (generate if provider doesn't provide)
            'name': str,      # Tool name (function/agent/internal tool)
            'arguments': dict # Tool arguments as a dictionary
          }
        ]
        
        This standard format allows the parent class to route tool calls without
        knowing anything about your provider!
        
        Important Notes:
        ---------------
        1. **Return None if no tool calls** - Don't return empty list
        2. **Arguments must be dict** - Parse JSON strings if needed
        3. **ID should be unique** - Generate UUID if provider doesn't provide
        4. **Multiple tool calls** - LLMs can call multiple tools in parallel
        
        Called By:
        ---------
        - GenesisAgent._orchestrate_tool_request() after each LLM call
        - Used to decide: execute tools or extract text response
        
        Args:
        ----
        response: Provider-specific response object
        
        Returns:
        -------
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
        ABSTRACT METHOD #6: Extract text response from provider's response.
        
        Purpose:
        --------
        Extract the LLM's text response to return to the user.
        Called when LLM doesn't call tools or after all tool calls are processed.
        
        What This Does (for OpenAI):
        ----------------------------
        Extracts content from: response.choices[0].message.content
        
        What You Receive:
        ----------------
        response: Provider-specific response object
            - Same object returned by _call_llm()
        
        What Other Providers Would Do:
        ------------------------------
        Anthropic:
            # Anthropic uses content blocks with type="text"
            text_blocks = [
                block.text 
                for block in response.content 
                if block.type == "text"
            ]
            return " ".join(text_blocks)
        
        Google Gemini:
            # Google uses parts in candidates
            return response.candidates[0].content.parts[0].text
        
        Local LLMs (OpenAI-compatible):
            # Usually identical to OpenAI
            return response.choices[0].message.content
        
        Important Notes:
        ---------------
        1. **Handle None gracefully** - Some responses may have no text content
        2. **Multiple text blocks** - Some providers split text into blocks
        3. **Combine appropriately** - Join with spaces or newlines as needed
        4. **Strip/clean** - Remove extra whitespace if needed
        
        Edge Cases:
        ----------
        - Tool-only responses (no text): Return empty string or placeholder
        - Multiple choices: Usually take first choice (choices[0])
        - Streaming responses: This method is for complete responses only
        
        Called By:
        ---------
        - GenesisAgent._orchestrate_tool_request() when no tool calls detected
        - GenesisAgent.process_request() for simple (non-tool) conversations
        - Final step in multi-turn conversations
        
        Args:
        ----
        response: Provider-specific response object
        
        Returns:
        -------
        Extracted text content as string
        """
        # OpenAI stores text in message.content
        # For Anthropic: filter content blocks by type="text"
        # For Google: access candidates[0].content.parts[0].text
        return response.choices[0].message.content

    def _create_assistant_message(self, response: Any) -> Dict:
        """
        ABSTRACT METHOD #7: Create assistant message dict from provider's response.
        
        Purpose:
        --------
        Convert provider's response into a message dict that can be added to
        conversation history for multi-turn conversations.
        
        Why This Matters:
        ----------------
        In multi-turn tool conversations:
        1. User: "What's 2+2?"
        2. Assistant: [calls add function]  ← This response
        3. Tool: "4"
        4. Assistant: "The result is 4"
        
        Between steps 2-3, we need to add the assistant's message (with tool_calls)
        to the conversation so the LLM knows context when we send the tool results.
        
        What This Does (for OpenAI):
        ----------------------------
        Creates an OpenAI-compatible assistant message:
        {
          "role": "assistant",
          "content": "...",
          "tool_calls": [...]  # If present
        }
        
        What You Receive:
        ----------------
        response: Provider-specific response object
            - Same object returned by _call_llm()
        
        What Other Providers Would Return:
        ----------------------------------
        Anthropic:
            {
              "role": "assistant",
              "content": response.content  # Already in correct format (list of blocks)
            }
            # Note: Anthropic's content includes tool_use blocks
        
        Google Gemini:
            {
              "role": "model",  # Note: Google uses "model" not "assistant"
              "parts": [response.candidates[0].content.parts]
            }
        
        Important Notes:
        ---------------
        1. **Include tool_calls if present** - Critical for OpenAI/compatible providers
           Without tool_calls, you'll get error: "tool messages must follow tool_calls"
        
        2. **Handle empty content** - Some responses have tool_calls but no text
           OpenAI allows empty string, some providers require null or omission
        
        3. **Preserve provider structure** - Return message in format that can be
           sent back to your provider's API in the next turn
        
        4. **Don't parse/transform** - This is for raw conversation history,
           not for Genesis processing (that's what _extract_* methods do)
        
        Used In Multi-Turn Flow:
        -----------------------
        messages = [...]
        response = await self._call_llm(messages, tools)
        
        # Check for tool calls
        tool_calls = self._extract_tool_calls(response)
        if tool_calls:
            # Add assistant message with tool_calls
            assistant_msg = self._create_assistant_message(response)
            messages.append(assistant_msg)  # ← HERE
            
            # Execute tools and add results
            for tool_call in tool_calls:
                result = await self._route_tool_call(...)
                messages.append({"role": "tool", "content": result, ...})
            
            # Continue conversation with tool results
            response = await self._call_llm(messages, tools)
        
        Called By:
        ---------
        - GenesisAgent._orchestrate_tool_request() before adding tool responses
        - Called every time LLM makes tool calls in multi-turn conversations
        
        Args:
        ----
        response: Provider-specific response object
        
        Returns:
        -------
        Message dict in provider's format, ready to add to conversation history
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
        
        Provider Implementation Guide:
        ------------------------------
        Override this method to clean up any provider-specific resources:
        - Close API clients
        - Cancel pending requests
        - Clear caches
        - Release file handles
        
        Always call super().close() to clean up parent class resources:
        - DDS participant
        - RPC service
        - Monitoring publishers
        - Memory adapter
        
        Called By:
        ---------
        - User code when shutting down agent
        - Test cleanup
        - Signal handlers (Ctrl+C)
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
        
        Provider Implementation Guide:
        ------------------------------
        This is an optional convenience method. Not required for provider implementation.
        
        Purpose:
        -------
        Simplifies calling the agent programmatically (not via RPC):
        
        Instead of:
            response = await agent.process_request({"message": "Hello"})
            text = response.get("message")
        
        Just do:
            text = await agent.process_message("Hello")
        
        Useful for:
        ----------
        - Testing
        - Direct embedding in applications
        - Simple chatbot interfaces
        
        Not needed for:
        --------------
        - RPC-based agents (Interface→Agent communication)
        - Production deployments
        - Agent-to-agent communication
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
