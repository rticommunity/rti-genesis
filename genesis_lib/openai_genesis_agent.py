#!/usr/bin/env python3
"""
OpenAI Genesis Agent Implementation

This module defines the OpenAIGenesisAgent class, which extends the MonitoredAgent
to provide an agent implementation specifically utilizing the OpenAI API.
It integrates OpenAI's chat completion capabilities, including function calling,
with the Genesis framework's monitoring and function discovery features.

Copyright (c) 2025, RTI & Jason Upchurch
"""

"""
OpenAI Genesis agent with function calling capabilities.
This agent provides a flexible and configurable interface for creating OpenAI-based agents
with support for function discovery, classification, and execution.
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

# Configure logging
# logging.basicConfig(  # REMOVE THIS BLOCK
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger("openai_genesis_agent")

class OpenAIGenesisAgent(MonitoredAgent):
    """An agent that uses OpenAI API with Genesis function calls"""
    
    def __init__(self, model_name="gpt-4o", classifier_model_name="gpt-4o-mini", 
                 domain_id: int = 0, agent_name: str = "OpenAIAgent", 
                 base_service_name: str = "OpenAIChat",
                 description: str = None, enable_tracing: bool = False, 
                 enable_agent_communication: bool = True, memory_adapter=None,
                 auto_run: bool = True, service_instance_tag: str = ""):
        """Initialize the agent with the specified models
        
        Args:
            model_name: OpenAI model to use (default: gpt-4o)
            classifier_model_name: Model to use for function classification (default: gpt-4o-mini)
            domain_id: DDS domain ID (default: 0)
            agent_name: Name of the agent (default: "OpenAIAgent")
            base_service_name: The fundamental type of service (default: "OpenAIChat")
            description: Optional description of the agent
            enable_tracing: Whether to enable detailed tracing logs (default: False)
            enable_agent_communication: Whether to enable agent-to-agent communication (default: True)
            memory_adapter: Optional custom memory adapter for conversation history
            auto_run: Whether to automatically start the agent's run loop (default: True)
            service_instance_tag: Optional tag for content filtering (e.g., "production", "staging", "v2")
        
        Understanding Key Parameters:
        
            agent_name vs base_service_name:
                - agent_name: The identity of this specific agent instance (e.g., "MyAssistant", 
                  "WeatherBot_Primary"). Used for display, logging, and human identification.
                - base_service_name: The service capability/type this agent provides (e.g., 
                  "OpenAIChat", "WeatherService"). Used for RPC service naming and discovery.
                - With RPC v2, multiple agents can share the same base_service_name and unified 
                  DDS topics. They are distinguished by their unique replier_guid, not separate topics.
                - Example: Two agents with base_service_name="OpenAIChat" both listen on 
                  rti/connext/genesis/rpc/OpenAIChatRequest (no topic proliferation).
            
            memory_adapter:
                - A plugin interface for conversation memory storage and retrieval.
                - If None (default), uses SimpleMemoryAdapter which stores conversation history 
                  in-memory (lost when agent stops).
                - The MemoryAdapter interface defines standard methods (write, retrieve, summarize, 
                  promote, prune) allowing you to plug in external memory systems.
                - Future-ready architecture designed to support: vector stores (Pinecone, Weaviate), 
                  graph databases (Neo4j), persistent storage (Redis, MongoDB), or specialized memory 
                  types (episodic, semantic, procedural).
                - Example: Pass a custom adapter to persist conversations across sessions or enable 
                  semantic search over historical interactions.
            
            auto_run:
                - When True (default): Agent automatically starts its run() loop if an event loop 
                  is already running, making it immediately discoverable and ready to handle requests.
                - When False: You must explicitly call await agent.run() to start the agent's main 
                  loop, giving you control over initialization timing.
                - Use False for: testing (calling process_request() directly), manual lifecycle 
                  control, embedded usage in larger applications, or when you need custom setup 
                  before the agent becomes discoverable.
        
        Design Note - Hardcoded agent_type="AGENT":
            OpenAIGenesisAgent is hardcoded as agent_type="AGENT" (PRIMARY_AGENT in monitoring)
            because it's designed as a general-purpose coordinator agent that orchestrates work
            by delegating to specialized agents and calling functions.
            
            The agent_type parameter serves ONLY monitoring/visualization purposes:
            - Affects graph topology labels (PRIMARY_AGENT vs SPECIALIZED_AGENT)
            - Changes node color/shape in monitoring UI
            - Used for topology validation in tests
            - Does NOT affect functional capabilities or behavior
            
            For specialized domain agents (e.g., WeatherAgent, FinanceAgent):
            - Extend MonitoredAgent directly with agent_type="SPECIALIZED_AGENT"
            - Or subclass OpenAIGenesisAgent and override the super().__init__() call
            
            This architectural distinction helps visualize the agent hierarchy:
            Interface → Primary Agents → Specialized Agents → Services → Functions
        """
        # Store tracing configuration
        self.enable_tracing = enable_tracing
        
        logger.debug(f"OpenAIGenesisAgent __init__ called for {agent_name}")
        
        if self.enable_tracing:
            logger.debug(f"Initializing OpenAIGenesisAgent with model {model_name}")
        
        # Store model configuration
        self.model_config = {
            "model_name": model_name,
            "classifier_model_name": classifier_model_name
        }
        
        # Initialize monitored agent base class with agent communication enabled
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            # Hardcoded as "AGENT" (PRIMARY_AGENT) - see "Design Note" in docstring above
            # This is for monitoring/visualization only, not functional behavior
            agent_type="AGENT",
            description=description or f"An OpenAI-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=memory_adapter,
            auto_run=auto_run,
            service_instance_tag=service_instance_tag
        )
        
        # Get API key from environment
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

        # OpenAI tool_choice configuration via GENESIS_TOOL_CHOICE environment variable
        # Controls whether OpenAI must/can/cannot call tools (functions, agents, internal tools)
        #
        # Values:
        #   "auto" (default) - OpenAI decides whether to call tools or respond directly
        #                      Best for production: natural, conversational, cost-effective
        #   
        #   "required"       - OpenAI MUST call a tool, cannot give free-form answers
        #                      Used in TESTS ONLY for deterministic behavior:
        #                      - Guarantees RPC paths are exercised (not bypassed)
        #                      - Ensures agent delegation happens (not answered directly)
        #                      - Makes tests reliable and non-flaky
        #                      - Enables opportunistic discovery (waits for tools/agents)
        #                      ⚠️ DO NOT USE IN PRODUCTION (slow, expensive, poor UX)
        #   
        #   "none"           - OpenAI cannot call tools (rarely used, for testing edge cases)
        #
        self.openai_tool_choice = os.getenv("GENESIS_TOOL_CHOICE", "auto")
        
        # Initialize generic client for function discovery, passing the agent's participant
        # self.generic_client = GenericFunctionClient(participant=self.app.participant)
        # Ensure GenericFunctionClient uses the SAME FunctionRegistry as the GenesisApp
        logger.debug(f"===== TRACING: Initializing GenericFunctionClient using agent app's FunctionRegistry: {id(self.app.function_registry)} =====")
        self.generic_client = GenericFunctionClient(function_registry=self.app.function_registry)
        
        # Initialize function classifier
        self.function_classifier = FunctionClassifier(llm_client=self.client)
        
        # Set system prompts for different scenarios
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

        # Start with general prompt, will switch to function-based if functions are discovered
        self.system_prompt = self.general_system_prompt
        
        # Set OpenAI-specific capabilities
        self.set_agent_capabilities(
            supported_tasks=["text_generation", "conversation"],
            additional_capabilities=self.model_config
        )
        
        if self.enable_tracing:
            logger.debug("OpenAIGenesisAgent initialized successfully")
    
    def _get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently available functions from FunctionRegistry via GenericFunctionClient.
        This is the single source of truth for function availability, querying DDS directly.
        
        Returns:
            Dict[str, Dict]: Dictionary keyed by function name, containing:
                - function_id: Unique identifier for the function
                - description: Human-readable description
                - schema: JSON schema for function parameters
                - provider_id: ID of the service providing this function
        """
        functions = self.generic_client.list_available_functions()
        result = {}
        for func_data in functions:
            func_name = func_data["name"]
            result[func_name] = {
                "function_id": func_data["function_id"],
                "description": func_data["description"],
                "schema": func_data["schema"],
                "provider_id": func_data.get("provider_id"),
            }
        return result
    
    def _get_available_agent_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently available agents as capability-based tools.
        Queries discovered_agents dynamically and transforms to tool format.
        This is the single source of truth queried from DDS via AgentCommunicationMixin.
        
        Returns:
            Dict[str, Dict]: Dictionary keyed by tool name, containing agent metadata
        """
        # Skip if agent communication is not enabled
        if not hasattr(self, 'agent_communication') or not self.agent_communication:
            return {}
        
        # Get discovered agents from the communication mixin (source of truth)
        discovered_agents = self.get_discovered_agents()
        
        if not discovered_agents:
            return {}
        
        agent_tools = {}
        
        for agent_id, agent_info in discovered_agents.items():
            # Skip self to avoid circular calls
            if agent_id == self.app.agent_id:
                continue
            
            # Extract capability information
            agent_name = agent_info.get('name', agent_id)
            agent_type = agent_info.get('agent_type', 'AGENT')
            service_name = agent_info.get('service_name', 'UnknownService')
            description = agent_info.get('description', f'Agent {agent_name}')
            capabilities = agent_info.get('capabilities', [])
            specializations = agent_info.get('specializations', [])
            
            # Generate capability-based tool names
            tool_names = self._generate_capability_based_tool_names(
                agent_info, capabilities, specializations, service_name
            )
            
            # Create tool entries for each capability/specialization
            for tool_name, tool_description in tool_names.items():
                agent_tools[tool_name] = {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "agent_type": agent_type,
                    "service_name": service_name,
                    "description": description,
                    "tool_description": tool_description,
                    "capabilities": capabilities,
                    "specializations": specializations,
                    "is_capability_based": True
                }
        
        return agent_tools
    
    def _generate_capability_based_tool_names(self, agent_info, capabilities, specializations, service_name):
        """
        Generate tool names based on agent capabilities and specializations instead of agent names.
        This ensures the LLM can discover functionality rather than needing to know agent names.
        """
        tool_names = {}
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generating tools for agent with capabilities: {capabilities}, specializations: {specializations} =====")
        
        # Generate tools based on specializations (most specific)
        for specialization in specializations:
            tool_name = f"get_{specialization.lower().replace(' ', '_').replace('-', '_')}_info"
            tool_description = f"Get information and assistance related to {specialization}. " + \
                             f"This tool connects to a specialized {specialization} agent."
            tool_names[tool_name] = tool_description
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Added specialization tool: {tool_name} =====")
        
        # Generate tools based on service type
        if service_name and service_name != 'UnknownService':
            # Create service-based tool name
            service_clean = service_name.lower().replace('service', '').replace(' ', '_').replace('-', '_')
            if service_clean:
                tool_name = f"use_{service_clean}_service"
                tool_description = f"Access {service_name} capabilities. " + \
                                 f"Description: {agent_info.get('description', 'Specialized service')}"
                tool_names[tool_name] = tool_description
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Added service tool: {tool_name} =====")
        
        # Generate tools based on capabilities
        for capability in capabilities:
            capability_clean = capability.lower().replace(' ', '_').replace('-', '_')
            tool_name = f"request_{capability_clean}"
            tool_description = f"Request {capability} functionality from a specialized agent. " + \
                             f"Service: {service_name}"
            tool_names[tool_name] = tool_description
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Added capability tool: {tool_name} =====")
        
        # Fallback: if no specific capabilities/specializations, create a generic tool
        if not tool_names:
            agent_type_clean = agent_info.get('agent_type', 'agent').lower().replace('_', '_')
            tool_name = f"consult_{agent_type_clean}"
            tool_description = f"Consult a {agent_info.get('agent_type', 'general')} agent. " + \
                             f"Service: {service_name}. " + \
                             f"Description: {agent_info.get('description', 'General purpose agent')}"
            tool_names[tool_name] = tool_description
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Added fallback tool: {tool_name} =====")
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generated {len(tool_names)} capability-based tools: {list(tool_names.keys())} =====")
        return tool_names
    
    def _convert_agents_to_tools(self):
        """
        Convert discovered agents into OpenAI tool schemas using UNIVERSAL AGENT SCHEMA.
        
        This implements the simplified agent-to-agent pattern where:
        1. ALL agents use the same universal schema: message -> response
        2. NO manual tool schema definition required in individual agents
        3. Genesis handles ALL tool execution automatically
        
        This eliminates the complexity of manual schema definition while maintaining
        capability-based tool names for LLM understanding.
        """
        logger.debug("===== TRACING: Converting agents to universal tool schemas =====")
        agent_tools = []
        
        available_agent_tools = self._get_available_agent_tools()
        for tool_name, agent_info in available_agent_tools.items():
            agent_name = agent_info.get('agent_name', 'Unknown Agent')
            capabilities = agent_info.get('capabilities', [])
            
            # Create capability-based description for the LLM
            if capabilities:
                capability_desc = f"Specialized agent for {', '.join(capabilities[:3])}"
                if len(capabilities) > 3:
                    capability_desc += f" and {len(capabilities)-3} more capabilities"
            else:
                capability_desc = f"General purpose agent ({agent_name})"
            
            # UNIVERSAL AGENT SCHEMA - Same for ALL agents
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": f"{capability_desc}. Send natural language queries and receive responses.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Natural language query or request to send to the agent"
                            }
                        },
                        "required": ["message"]
                    }
                }
            }
            agent_tools.append(tool_schema)
            logger.debug(f"===== TRACING: Added universal agent tool: {tool_name} =====")
        
        logger.debug(f"===== TRACING: Generated {len(agent_tools)} universal agent tools =====")
        return agent_tools
    
    def _get_function_schemas_for_openai(self, relevant_functions: Optional[List[str]] = None):
        """Convert discovered functions to OpenAI function schemas format"""
        logger.debug("===== TRACING: Converting function schemas for OpenAI =======")
        function_schemas = []
        
        available_functions = self._get_available_functions()
        for name, func_info in available_functions.items():
            # If relevant_functions is provided, only include those functions
            if relevant_functions is not None and name not in relevant_functions:
                continue
                
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func_info["description"],
                    "parameters": func_info["schema"]
                }
            }
            function_schemas.append(schema)
            logger.debug(f"===== TRACING: Added schema for function: {name} =====")
        
        return function_schemas
    
    def _get_all_tool_schemas_for_openai(self, relevant_functions: Optional[List[str]] = None):
        """
        Get ALL tool schemas for OpenAI - functions, agents, AND internal tools.
        This is the unified method that enables the complete tool ecosystem.
        """
        logger.debug("===== TRACING: Getting ALL tool schemas (functions + agents + internal tools) for OpenAI =====")
        
        # Get function tool schemas
        function_tools = self._get_function_schemas_for_openai(relevant_functions)
        
        # Get agent tool schemas
        agent_tools = self._convert_agents_to_tools()
        
        # Get internal tool schemas from @genesis_tool decorated methods
        internal_tools = self._get_internal_tool_schemas_for_openai()
        
        # Combine all tool types
        all_tools = function_tools + agent_tools + internal_tools
        
        logger.debug(f"===== TRACING: Combined {len(function_tools)} function tools + {len(agent_tools)} agent tools + {len(internal_tools)} internal tools = {len(all_tools)} total tools =====")
        
        return all_tools

    def _get_internal_tool_schemas_for_openai(self) -> List[Dict[str, Any]]:
        """
        Generate OpenAI tool schemas for internal @genesis_tool decorated methods.
        
        Returns:
            List of OpenAI-compatible tool schemas
        """
        if not hasattr(self, 'internal_tools_cache') or not self.internal_tools_cache:
            return []
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generating OpenAI schemas for {len(self.internal_tools_cache)} internal tools =====")
        
        internal_schemas = []
        schema_generator = get_schema_generator("openai")
        
        for tool_name, tool_info in self.internal_tools_cache.items():
            metadata = tool_info["metadata"]
            
            try:
                # Generate OpenAI schema from Genesis tool metadata
                openai_schema = schema_generator.generate_tool_schema(metadata)
                internal_schemas.append(openai_schema)
                
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Generated schema for internal tool: {tool_name} =====")
                    
            except Exception as e:
                logger.error(f"Error generating schema for internal tool {tool_name}: {e}")
                
        return internal_schemas
    
    async def _call_function(self, function_name: str, **kwargs) -> Any:
        """Call a function using the generic client"""
        logger.debug(f"===== TRACING: Calling function {function_name} =====")
        logger.debug(f"===== TRACING: Function arguments: {json.dumps(kwargs, indent=2)} =====")
        
        available_functions = self._get_available_functions()
        if function_name not in available_functions:
            error_msg = f"Function not found: {function_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        try:
            # Call the function through the generic client
            start_time = time.time()
            result = await self.generic_client.call_function(
                available_functions[function_name]["function_id"],
                **kwargs
            )
            end_time = time.time()
            
            logger.debug(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Function result: {result} =====")
            
            # Extract result value if in dict format
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise
    
    async def _call_agent(self, agent_tool_name: str, **kwargs) -> Any:
        """
        Call an agent using the UNIVERSAL AGENT SCHEMA.
        
        All agents now use the same simple interface:
        - Input: message (string)
        - Output: response (string)
        
        This eliminates the need for agents to handle custom tool schemas.
        """
        logger.debug(f"===== TRACING: Calling agent tool {agent_tool_name} =====")
        logger.debug(f"===== TRACING: Agent arguments: {json.dumps(kwargs, indent=2)} =====")
        
        available_agent_tools = self._get_available_agent_tools()
        if agent_tool_name not in available_agent_tools:
            error_msg = f"Agent tool not found: {agent_tool_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        agent_info = available_agent_tools[agent_tool_name]
        target_agent_id = agent_info["agent_id"]
        
        # Extract message from universal schema (simplified from query/context pattern)
        message = kwargs.get("message", "")
        if not message:
            # Fallback for backward compatibility with old query/context pattern
            query = kwargs.get("query", "")
            context = kwargs.get("context", "")
            message = f"{query} {context}".strip() if context else query
        
        if not message:
            raise ValueError("No message provided for agent call")
        
        try:
            # Use monitored agent communication if available
            if hasattr(self, 'send_agent_request_monitored'):
                logger.debug(f"===== TRACING: Using monitored agent communication =====")
                start_time = time.time()
                result = await self.send_agent_request_monitored(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=30.0
                )
                end_time = time.time()
            else:
                # Fallback to basic agent communication
                logger.debug(f"===== TRACING: Using basic agent communication =====")
                start_time = time.time()
                result = await self.send_agent_request(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=30.0
                )
                end_time = time.time()
            
            logger.debug(f"===== TRACING: Agent call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Agent result: {result} =====")
            
            # Extract result message if in dict format (universal response handling)
            if isinstance(result, dict):
                if "message" in result:
                    return result["message"]
                elif "response" in result:
                    return result["response"]
                else:
                    return str(result)
            return str(result)
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling agent {agent_tool_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        user_message = request.get("message", "")
        logger.debug(f"===== TRACING: Processing request: {user_message} =====")
        try:
            # Enhanced tracing: Discovery status before processing
            if self.enable_tracing:
                self._trace_discovery_status("BEFORE PROCESSING")
            
            # If tools are required, opportunistically block a short time for discovery
            # so tools are available on first request (useful for deterministic tests).
            if getattr(self, 'openai_tool_choice', 'auto') == 'required':
                try:
                    await self.generic_client.discover_functions(timeout_seconds=5)
                except Exception:
                    # Non-fatal; proceed to non-blocking cache population
                    pass

            # Check available functions and agents for system prompt switching
            available_functions = self._get_available_functions()
            agent_tools = self._get_available_agent_tools()
            if not available_functions and not agent_tools:
                self.system_prompt = self.general_system_prompt
            else:
                self.system_prompt = self.function_based_system_prompt
            
            # Fast-path: simple math (addition) via calculator function
            try:
                import re
                m = re.search(r"what\s+is\s+(\d+)\s+plus\s+(\d+)\??", user_message, re.IGNORECASE)
                if m and "add" in available_functions:
                    x = int(m.group(1))
                    y = int(m.group(2))
                    result = await self._call_function("add", x=x, y=y)
                    # Ensure result is numeric if dict
                    if isinstance(result, dict) and "result" in result:
                        result_val = result["result"]
                    else:
                        result_val = result
                    reply_text = f"{x} plus {y} equals {result_val}."
                    return {"message": reply_text, "status": 0}
            except Exception:
                # Fall back to normal flow on any error
                pass

            # Ensure agents are discovered (critical for agent-as-tool pattern)
            # If tools are required, give agent discovery a brief chance before proceeding
            if getattr(self, 'openai_tool_choice', 'auto') == 'required':
                try:
                    # Opportunistic short wait to let other agents announce
                    wait_deadline = time.time() + 5.0
                    lower_msg = (user_message or '').lower()
                    while time.time() < wait_deadline:
                        discovered_agents = self.get_discovered_agents() if hasattr(self, 'get_discovered_agents') else {}
                        if discovered_agents:
                            # If it's a weather-like query, bias for a discovered weather agent
                            if 'weather' in lower_msg:
                                found_weather = False
                                for info in discovered_agents.values():
                                    name = (info.get('name') or info.get('prefered_name') or '').lower()
                                    caps = [str(c).lower() for c in (info.get('capabilities') or [])]
                                    specs = [str(s).lower() for s in (info.get('specializations') or [])]
                                    if 'weather' in name or 'weather' in caps or 'weather' in specs:
                                        found_weather = True
                                        break
                                if found_weather:
                                    break
                            else:
                                break
                        await asyncio.sleep(0.2)
                except Exception:
                    pass
            # Heuristic delegation: route obvious weather queries to a discovered weather agent
            try:
                import re
                agent_tools_for_heuristic = self._get_available_agent_tools()
                logger.debug(f"Checking heuristic delegation - agent tools has {len(agent_tools_for_heuristic)} tools")
                if re.search(r"\bweather\b", user_message, re.IGNORECASE) and agent_tools_for_heuristic:
                    logger.debug(f"Weather query detected, searching for weather agent...")
                    # Prefer an agent whose name or capability mentions 'weather'
                    candidate_id = None
                    candidate_name = None
                    # Try discovered agents dict for richer metadata
                    discovered_agents = self.get_discovered_agents() if hasattr(self, 'get_discovered_agents') else {}
                    logger.debug(f"Searching {len(discovered_agents)} discovered agents...")
                    for aid, info in (discovered_agents or {}).items():
                        name = (info.get('name') or info.get('prefered_name') or '').lower()
                        caps = info.get('capabilities') or []
                        specs = info.get('specializations') or []
                        caps_l = [str(c).lower() for c in caps] if isinstance(caps, (list, tuple)) else []
                        specs_l = [str(s).lower() for s in specs] if isinstance(specs, (list, tuple)) else []
                        if 'weather' in name or 'weather' in caps_l or 'weather' in specs_l:
                            candidate_id = aid
                            candidate_name = info.get('name') or info.get('prefered_name') or aid
                            logger.debug(f"Found weather agent: {candidate_name} ({candidate_id})")
                            break
                    # If metadata scan failed, try agent tools
                    if not candidate_id:
                        logger.debug(f"No match in discovered agents, checking agent tools...")
                        for tool_name, ainfo in agent_tools_for_heuristic.items():
                            an = (ainfo.get('agent_name') or '').lower()
                            td = (ainfo.get('tool_description') or '').lower()
                            if 'weather' in tool_name.lower() or 'weather' in an or 'weather' in td:
                                candidate_id = ainfo.get('agent_id')
                                candidate_name = ainfo.get('agent_name') or tool_name
                                logger.debug(f"Found weather tool in cache: {tool_name}")
                                break
                    if candidate_id:
                        logger.debug(f"Delegating to {candidate_name} ({candidate_id})...")
                        # Route via monitored agent communication if available
                        if hasattr(self, 'send_agent_request_monitored'):
                            routed = await self.send_agent_request_monitored(
                                target_agent_id=candidate_id,
                                message=user_message,
                                conversation_id=None,
                                timeout_seconds=30.0
                            )
                        else:
                            routed = await self.send_agent_request(
                                target_agent_id=candidate_id,
                                message=user_message,
                                conversation_id=None,
                                timeout_seconds=30.0
                            )
                        logger.debug(f"Delegation returned: {routed}")
                        if isinstance(routed, dict) and routed.get('status') == 0:
                            return {"message": routed.get('message', ''), "status": 0}
                    else:
                        logger.debug(f"No weather agent candidate found")
                else:
                    logger.debug(f"Skipping heuristic delegation (weather={'weather' in user_message.lower()}, cache_size={len(agent_tools_for_heuristic)})")
            except Exception as e:
                # NEVER silently swallow exceptions - log them!
                logger.error(f"Error in heuristic delegation: {e}")
                logger.error(traceback.format_exc())
                # Fall through to normal flow
                pass
            
            # Ensure internal tools are discovered (@genesis_tool decorated methods)
            await self._ensure_internal_tools_discovered()
            
            # Enhanced tracing: Discovery status after discovery
            if self.enable_tracing:
                self._trace_discovery_status("AFTER DISCOVERY")
            
            # Generate chain and call IDs for tracking
            chain_id = str(uuid.uuid4())
            call_id = str(uuid.uuid4())
            
            # If no functions are available, proceed with basic response
            available_functions_for_check = self._get_available_functions()
            if not available_functions_for_check:
                logger.debug("===== TRACING: No external functions available, checking for internal tools or agents =====")
                
                # Check if we have internal tools or agents available
                has_internal_tools = hasattr(self, 'internal_tools_cache') and self.internal_tools_cache
                agent_tools_for_check = self._get_available_agent_tools()
                has_agents = bool(agent_tools_for_check)
                
                if not has_internal_tools and not has_agents:
                    logger.debug("===== TRACING: No tools or agents available, using general conversation =====")
                    
                    # Create chain event for LLM call start
                    self._publish_llm_call_start(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # Enhanced tracing: OpenAI API call details
                    if self.enable_tracing:
                        self._trace_openai_call("General conversation (no tools)", [], user_message)
                    
                    # Process with general conversation - FIX MEMORY INTEGRATION
                    
                    # Retrieve memory and format for OpenAI
                    N = 8
                    memory_items = self.memory.retrieve(k=N)
                    messages = [{"role": "system", "content": self.general_system_prompt}]
                    
                    # Add conversation history from memory
                    for entry in memory_items:
                        item = entry["item"]
                        meta = entry.get("metadata", {})
                        role = meta.get("role")
                        if role not in ("user", "assistant"):
                            # Fallback: alternate roles if metadata is missing
                            idx = memory_items.index(entry)
                            role = "user" if idx % 2 == 0 else "assistant"
                        messages.append({"role": role, "content": str(item)})
                    
                    # Add current user message
                    messages.append({"role": "user", "content": user_message})
                    
                    response = self.client.chat.completions.create(
                        model=self.model_config['model_name'],
                        messages=messages
                    )
                    
                    # Enhanced tracing: OpenAI response analysis
                    if self.enable_tracing:
                        self._trace_openai_response(response)
                    
                    # Create chain event for LLM call completion
                    self._publish_llm_call_complete(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # Write user and agent messages to memory
                    self.memory.write(user_message, metadata={"role": "user"})
                    agent_response = response.choices[0].message.content
                    self.memory.write(agent_response, metadata={"role": "assistant"})
                    return {"message": agent_response, "status": 0}
                else:
                    logger.debug(f"===== TRACING: No external functions but have internal tools ({has_internal_tools}) or agents ({has_agents}), proceeding with tool processing =====")
                    # Continue to tool processing - we have internal tools or agents to offer
            
            # Phase 1: Function Classification (or tool selection if no external functions)
            # Create chain event for classification LLM call start
            self._publish_llm_call_start(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['classifier_model_name']}.classifier"
            )
            
            # Get available functions for classification
            functions_dict = self._get_available_functions()
            available_functions = [
                {
                    "name": name,
                    "description": info["description"],
                    "schema": info["schema"]
                }
                for name, info in functions_dict.items()
            ]
            
            # Enhanced tracing: Function classification details
            if self.enable_tracing:
                logger.debug(f"🧠 TRACE: Available external functions for classification: {[f['name'] for f in available_functions]}")
            
            if available_functions:
                # Classify functions based on user query (only if we have external functions)
                relevant_functions = self.function_classifier.classify_functions(
                    user_message,
                    available_functions,
                    self.model_config['classifier_model_name']
                )
                
                # Enhanced tracing: Classification results
                if self.enable_tracing:
                    logger.debug(f"🧠 TRACE: Classifier returned: {[f['name'] for f in relevant_functions]}")
                
                # Get function schemas for relevant functions
                relevant_function_names = [func["name"] for func in relevant_functions]
            else:
                # No external functions to classify
                if self.enable_tracing:
                    logger.debug(f"🧠 TRACE: No external functions to classify, using all available tools")
                relevant_functions = []
                relevant_function_names = []
            
            # Create chain event for classification LLM call completion
            self._publish_llm_call_complete(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['classifier_model_name']}.classifier"
            )
            
            # Publish classification results for each relevant function
            functions_for_classification = self._get_available_functions()
            for func in relevant_functions:
                # Create chain event for classification result
                self._publish_classification_result(
                    chain_id=chain_id,
                    call_id=call_id,
                    classified_function_name=func["name"],
                    classified_function_id=functions_for_classification[func["name"]]["function_id"]
                )
                
                # Create component lifecycle event for function classification
                self.graph.publish_node(
                    component_id=self.app.agent_id,
                    component_type=1,  # AGENT_PRIMARY
                    state=2,  # READY
                    attrs={
                        "function_name": func["name"],
                        "description": func["description"],
                        "reason": f"CLASSIFICATION.RELEVANT: Function '{func['name']}' for query: {user_message[:100]}"
                    }
                )
            
            # Get ALL tool schemas (external functions + internal tools + agents)
            function_schemas = self._get_all_tool_schemas_for_openai(relevant_function_names)
            
            # Enhanced tracing: Tool schema generation
            if self.enable_tracing:
                logger.debug(f"🛠️ TRACE: Generated {len(function_schemas)} total tool schemas")
                for i, tool in enumerate(function_schemas):
                    tool_name = tool.get('function', {}).get('name', 'Unknown')
                    logger.debug(f"🛠️ TRACE: Tool {i+1}: {tool_name}")
            
            if not function_schemas:
                logger.warning("===== TRACING: No relevant functions found, processing without functions =====")
                
                # Create chain event for LLM call start
                self._publish_llm_call_start(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                # Enhanced tracing: OpenAI API call details
                if self.enable_tracing:
                    self._trace_openai_call("No relevant functions", [], user_message)
                
                # Process without functions - FIX MEMORY INTEGRATION
                
                # Retrieve memory and format for OpenAI
                N = 8
                memory_items = self.memory.retrieve(k=N)
                messages = [{"role": "system", "content": self.system_prompt}]
                
                # Add conversation history from memory
                for entry in memory_items:
                    item = entry["item"]
                    meta = entry.get("metadata", {})
                    role = meta.get("role")
                    if role not in ("user", "assistant"):
                        # Fallback: alternate roles if metadata is missing
                        idx = memory_items.index(entry)
                        role = "user" if idx % 2 == 0 else "assistant"
                    messages.append({"role": role, "content": str(item)})
                
                # Add current user message
                messages.append({"role": "user", "content": user_message})
                
                response = self.client.chat.completions.create(
                    model=self.model_config['model_name'],
                    messages=messages
                )
                
                # Enhanced tracing: OpenAI response analysis
                if self.enable_tracing:
                    self._trace_openai_response(response)
                
                # Create chain event for LLM call completion
                self._publish_llm_call_complete(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                # Write user and agent messages to memory
                self.memory.write(user_message, metadata={"role": "user"})
                agent_response = response.choices[0].message.content
                self.memory.write(agent_response, metadata={"role": "assistant"})
                return {"message": agent_response, "status": 0}
            
            # Phase 2: Function Execution with proper memory integration
            logger.debug("===== TRACING: Calling OpenAI API with function schemas =====")
            
            # Create chain event for LLM call start
            self._publish_llm_call_start(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['model_name']}"
            )
            
            # Enhanced tracing: OpenAI API call details
            if self.enable_tracing:
                self._trace_openai_call("Function execution", function_schemas, user_message)
            
            # Retrieve memory and format for OpenAI
            N = 8
            memory_items = self.memory.retrieve(k=N)
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history from memory
            for entry in memory_items:
                item = entry["item"]
                meta = entry.get("metadata", {})
                role = meta.get("role")
                if role not in ("user", "assistant"):
                    # Fallback: alternate roles if metadata is missing
                    idx = memory_items.index(entry)
                    role = "user" if idx % 2 == 0 else "assistant"
                messages.append({"role": role, "content": str(item)})
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.chat.completions.create(
                model=self.model_config['model_name'],
                messages=messages,
                tools=function_schemas,
                tool_choice=self.openai_tool_choice
            )

            logger.debug(f"=====!!!!! TRACING: OpenAI response: {response} !!!!!=====")
            
            # Enhanced tracing: OpenAI response analysis
            if self.enable_tracing:
                self._trace_openai_response(response)
            
            # Create chain event for LLM call completion
            self._publish_llm_call_complete(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['model_name']}"
            )
            
            # Extract the response
            message = response.choices[0].message

            # DEBUG: Log tool calls returned by the primary LLM
            try:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    debug_tools = []
                    for tc in message.tool_calls:
                        try:
                            debug_tools.append({
                                "name": getattr(tc.function, 'name', 'unknown'),
                                "arguments": getattr(tc.function, 'arguments', '')
                            })
                        except Exception:
                            pass
                    logger.info(f"LLM_TOOL_SELECTION primary: chain={chain_id[:8]} call={call_id[:8]} tools={debug_tools}")
            except Exception:
                pass
            
            # Check if the model wants to call a function
            if message.tool_calls:
                logger.debug(f"===== TRACING: Model requested function call(s): {len(message.tool_calls)} =======")
                logger.debug(f"Model tool calls: {message.tool_calls}")
                # Process each tool call (function or agent)
                tool_responses = []
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.debug(f"===== TRACING: Processing tool call: {tool_name} =====")
                    
                    # Determine if this is a function call, agent call, or internal tool call
                    available_functions_for_tool = self._get_available_functions()
                    available_agent_tools_for_tool = self._get_available_agent_tools()
                    is_function_call = tool_name in available_functions_for_tool
                    is_agent_call = tool_name in available_agent_tools_for_tool
                    is_internal_tool_call = hasattr(self, 'internal_tools_cache') and tool_name in self.internal_tools_cache

                    # DEBUG: Decision record for this tool call
                    try:
                        logger.info(
                            f"TOOL_CALL_DECISION chain={chain_id[:8]} call={call_id[:8]} name={tool_name} "
                            f"is_agent={is_agent_call} is_function={is_function_call} is_internal={is_internal_tool_call} "
                            f"args={tool_args}"
                        )
                    except Exception:
                        pass
                    
                    try:
                        if is_function_call:
                            logger.debug(f"===== TRACING: Tool {tool_name} is a FUNCTION call =====")
                            
                            # Delegate monitoring and execution to base class helper
                            start_time = time.time()
                            tool_result = await self.execute_function_with_monitoring(
                                function_name=tool_name,
                                function_id=available_functions_for_tool[tool_name]["function_id"],
                                provider_id=available_functions_for_tool[tool_name].get("provider_id"),
                                tool_args=tool_args,
                                chain_id=chain_id,
                                call_id=call_id,
                            )
                            end_time = time.time()
                            
                            logger.debug(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
                            
                        elif is_internal_tool_call:
                            logger.debug(f"===== TRACING: Tool {tool_name} is an INTERNAL TOOL call =====")
                            
                            # Call the internal tool directly
                            start_time = time.time()
                            tool_result = await self._call_internal_tool(tool_name, **tool_args)
                            end_time = time.time()
                            
                            logger.debug(f"===== TRACING: Internal tool call completed in {end_time - start_time:.2f} seconds =====")
                            
                        elif is_agent_call:
                            logger.debug(f"===== TRACING: Tool {tool_name} is an AGENT call =====")
                            
                            # Create chain event for agent call start
                            agent_info = available_agent_tools_for_tool[tool_name]
                            try:
                                logger.info(
                                    f"AGENT_TOOL_SELECTED primary: chain={chain_id[:8]} call={call_id[:8]} tool={tool_name} "
                                    f"target_agent_id={agent_info.get('agent_id','')}"
                                )
                            except Exception:
                                pass
                            # Log the outbound agent request payload for traceability
                            try:
                                logger.info(
                                    f"AGENT_REQUEST_START payload: chain={chain_id[:8]} call={call_id[:8]} "
                                    f"from={self.app.agent_id} to={agent_info.get('agent_id','')} message={tool_args.get('message','')}"
                                )
                            except Exception:
                                pass
                            self._publish_agent_chain_event(
                                chain_id=chain_id,
                                call_id=call_id,
                                event_type="AGENT_REQUEST_START",
                                source_id=self.app.agent_id,
                                target_id=agent_info["agent_id"]
                            )
                            
                            # Call the agent through the agent communication system
                            start_time = time.time()
                            tool_result = await self._call_agent(tool_name, **tool_args)
                            end_time = time.time()
                            
                            # Create chain event for agent call completion
                            self._publish_agent_chain_event(
                                chain_id=chain_id,
                                call_id=call_id,
                                event_type="AGENT_RESPONSE_RECEIVED",
                                source_id=agent_info["agent_id"],
                                target_id=self.app.agent_id
                            )
                            
                            logger.debug(f"===== TRACING: Agent call completed in {end_time - start_time:.2f} seconds =====")
                            
                        else:
                            logger.error(f"===== TRACING: Tool {tool_name} not found in function cache, agent cache, or internal tools cache =====")
                            raise ValueError(f"Tool not found: {tool_name}")
                        
                        logger.debug(f"===== TRACING: Tool result: {tool_result} =====")
                        
                        # Extract result value if in dict format
                        if isinstance(tool_result, dict) and "result" in tool_result:
                            tool_result = tool_result["result"]
                            
                        tool_responses.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": str(tool_result)
                        })
                        logger.debug(f"===== TRACING: Tool {tool_name} returned: {tool_result} =====")
                        
                    except Exception as e:
                        logger.error(f"===== TRACING: Error calling tool {tool_name}: {str(e)} =====")
                        tool_responses.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": f"Error: {str(e)}"
                        })
                
                # CRITICAL: OpenAI may request MULTIPLE rounds of tool calls.
                # Loop until we get a text response instead of more tool calls.
                logger.debug(f"Starting multi-turn tool conversation loop with {len(tool_responses)} initial tool responses")
                
                # Build initial conversation for tool response processing
                N = 8
                memory_items = self.memory.retrieve(k=N)
                messages = [{"role": "system", "content": self.system_prompt}]
                
                # Add conversation history from memory
                for entry in memory_items:
                    item = entry["item"]
                    meta = entry.get("metadata", {})
                    role = meta.get("role")
                    if role not in ("user", "assistant"):
                        # Fallback: alternate roles if metadata is missing
                        idx = memory_items.index(entry)
                        role = "user" if idx % 2 == 0 else "assistant"
                    messages.append({"role": role, "content": str(item)})
                
                # Add current user message
                messages.append({"role": "user", "content": user_message})
                
                # Add assistant message with tool calls
                assistant_content = message.content if message.content is not None else ""
                messages.append({"role": "assistant", "content": assistant_content, "tool_calls": message.tool_calls})
                
                # Add initial tool responses
                messages.extend(tool_responses)
                
                # Multi-turn tool conversation loop
                max_turns = 5  # Prevent infinite loops
                turn_count = 0
                final_message = None
                
                while turn_count < max_turns:
                    turn_count += 1
                    logger.debug(f"Tool conversation turn {turn_count}/{max_turns}, making OpenAI call with {len(messages)} messages...")
                    
                    # Create chain event for LLM call start
                    self._publish_llm_call_start(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # CRITICAL: Always use 'auto' for multi-turn tool conversations.
                    # If we use 'required', OpenAI is FORCED to always call a tool, creating an infinite loop.
                    # With 'auto', OpenAI intelligently decides when to call tools vs return text.
                    logger.debug(f"Turn {turn_count} using tool_choice='auto'")
                    
                    # Call OpenAI with current conversation state
                    response = self.client.chat.completions.create(
                        model=self.model_config['model_name'],
                        messages=messages,
                        tools=function_schemas,
                        tool_choice='auto'  # Always auto for multi-turn conversations
                    )
                    
                    # Create chain event for LLM call completion
                    self._publish_llm_call_complete(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    response_message = response.choices[0].message
                    logger.debug(f"Turn {turn_count} response: content={response_message.content is not None}, tool_calls={len(response_message.tool_calls) if response_message.tool_calls else 0}")
                    
                    # Check if OpenAI returned text content (final response)
                    if response_message.content and not response_message.tool_calls:
                        final_message = response_message.content
                        logger.debug(f"Turn {turn_count} returned final text response!")
                        break
                    
                    # OpenAI wants to make MORE tool calls
                    if response_message.tool_calls:
                        logger.debug(f"Turn {turn_count} has {len(response_message.tool_calls)} more tool calls to execute")
                        
                        # Add assistant message with tool calls to conversation
                        assistant_content = response_message.content if response_message.content is not None else ""
                        messages.append({"role": "assistant", "content": assistant_content, "tool_calls": response_message.tool_calls})
                        
                        # Execute the additional tool calls
                        new_tool_responses = []
                        for tool_call in response_message.tool_calls:
                            tool_name = tool_call.function.name
                            tool_args = json.loads(tool_call.function.arguments)
                            logger.debug(f"Turn {turn_count} executing tool: {tool_name}")
                            
                            try:
                                # Determine tool type and execute
                                available_functions_for_multiturn = self._get_available_functions()
                                available_agent_tools_for_multiturn = self._get_available_agent_tools()
                                if tool_name in available_functions_for_multiturn:
                                    tool_result = await self.execute_function_with_monitoring(
                                        function_name=tool_name,
                                        function_id=available_functions_for_multiturn[tool_name]["function_id"],
                                        provider_id=available_functions_for_multiturn[tool_name].get("provider_id"),
                                        tool_args=tool_args,
                                        chain_id=chain_id,
                                        call_id=call_id,
                                    )
                                elif hasattr(self, 'internal_tools_cache') and tool_name in self.internal_tools_cache:
                                    tool_result = await self._call_internal_tool(tool_name, **tool_args)
                                elif tool_name in available_agent_tools_for_multiturn:
                                    tool_result = await self._call_agent(tool_name, **tool_args)
                                else:
                                    raise ValueError(f"Tool not found: {tool_name}")
                                
                                # Extract result value if in dict format
                                if isinstance(tool_result, dict) and "result" in tool_result:
                                    tool_result = tool_result["result"]
                                
                                new_tool_responses.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": str(tool_result)
                                })
                                logger.debug(f"Turn {turn_count} tool {tool_name} returned: {str(tool_result)[:100]}")
                                
                            except Exception as e:
                                logger.error(f"Error executing tool {tool_name} in turn {turn_count}: {e}")
                                new_tool_responses.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": f"Error: {str(e)}"
                                })
                        
                        # Add tool responses to conversation
                        messages.extend(new_tool_responses)
                        logger.debug(f"Turn {turn_count} added {len(new_tool_responses)} tool responses, continuing loop...")
                    else:
                        # No tool calls and no content - shouldn't happen but handle it
                        logger.debug(f"Turn {turn_count} has neither content nor tool_calls - breaking")
                        final_message = "No response generated"
                        break
                
                if turn_count >= max_turns:
                    logger.debug(f"Reached max turns ({max_turns}), stopping loop")
                    final_message = "Response processing exceeded maximum turns"
                
                logger.debug(f"Multi-turn loop completed after {turn_count} turns, final_message: {final_message[:100] if final_message else 'None'}")
                
                # Write user and agent messages to memory
                self.memory.write(user_message, metadata={"role": "user"})
                if final_message:
                    self.memory.write(final_message, metadata={"role": "assistant"})
                
                return {"message": final_message, "status": 0}
            
            # If no tool call, just return the response
            text_response = message.content
            logger.debug(f"===== TRACING: Response (no tool call): {text_response} =====")
            
            # Enhanced tracing: Final discovery status
            if self.enable_tracing:
                self._trace_discovery_status("AFTER PROCESSING")
            
            # Write user and agent messages to memory
            self.memory.write(user_message, metadata={"role": "user"})
            self.memory.write(text_response, metadata={"role": "assistant"})
            return {"message": text_response, "status": 0}
                
        except Exception as e:
            logger.error(f"===== TRACING: Error processing request: {str(e)} =======")
            logger.error(traceback.format_exc())
            return {"message": f"Error: {str(e)}", "status": 1}
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent (agent-to-agent communication).
        
        This method is called when another agent sends a request to this agent.
        It delegates to the standard process_request method to handle the actual processing.
        
        Args:
            request: Dictionary containing the request data with keys:
                    - message: The request message
                    - conversation_id: Optional conversation ID for tracking
                    
        Returns:
            Dictionary containing the response data with keys:
                    - message: The response message
                    - status: Status code (0 for success, non-zero for error)
                    - conversation_id: The conversation ID from the request
        """
        if self.enable_tracing:
            logger.debug(f"🔍 TRACE: OpenAIGenesisAgent.process_agent_request() called with: {request}")
        
        try:
            # Extract message and conversation ID from agent request
            message = request.get("message", "")
            conversation_id = request.get("conversation_id", "")
            
            if self.enable_tracing:
                logger.debug(f"🔍 TRACE: Agent request - message: {message}")
                logger.debug(f"🔍 TRACE: Agent request - conversation_id: {conversation_id}")
            
            # Process the request using our standard OpenAI processing
            logger.debug(f"process_agent_request() calling process_request() with message: {message}")
            response = await self.process_request({"message": message})
            logger.debug(f"process_agent_request() got response from process_request(): {response}")
            
            # Format response for agent-to-agent communication
            agent_response = {
                "message": response.get("message", "No response generated"),
                "status": response.get("status", 0),
                "conversation_id": conversation_id
            }
            logger.debug(f"process_agent_request() formatted agent_response: {agent_response}")
            
            if self.enable_tracing:
                logger.debug(f"🔍 TRACE: OpenAIGenesisAgent agent response: {agent_response}")
            
            return agent_response
            
        except Exception as e:
            if self.enable_tracing:
                logger.error(f"❌ TRACE: Error in OpenAIGenesisAgent.process_agent_request: {e}")
                logger.error(f"❌ TRACE: Traceback: {traceback.format_exc()}")
            
            return {
                "message": f"Agent processing error: {str(e)}",
                "status": -1,
                "conversation_id": request.get("conversation_id", "")
            }
    
    def _trace_discovery_status(self, phase: str):
        """Enhanced tracing: Discovery status at different phases"""
        logger.debug(f"🔍 TRACE: === Discovery Status: {phase} ===")
        available_functions_for_trace = self._get_available_functions()
        logger.debug(f"🔧 TRACE: Available functions: {len(available_functions_for_trace)} functions")
        for name, info in available_functions_for_trace.items():
            logger.debug(f"🔧 TRACE: - {name}: {info.get('description', 'No description')}")
        
        agent_tools_for_trace = self._get_available_agent_tools()
        logger.debug(f"🤝 TRACE: Available agent tools: {len(agent_tools_for_trace)} agent tools")
        for name, info in agent_tools_for_trace.items():
            logger.debug(f"🤝 TRACE: - {name}: {info.get('agent_name', 'Unknown agent')}")
        
        # Add internal tools tracing
        internal_tools_count = len(getattr(self, 'internal_tools_cache', {}))
        logger.debug(f"🛠️ TRACE: Internal tools cache: {internal_tools_count} internal tools")
        if hasattr(self, 'internal_tools_cache'):
            for name, info in self.internal_tools_cache.items():
                func_name = info.get('function_name', name)
                logger.debug(f"🛠️ TRACE: - {name}: {func_name}")
        
        if hasattr(self, 'agent_communication') and self.agent_communication:
            discovered = self.get_discovered_agents()
            logger.debug(f"🌐 TRACE: Raw discovered agents: {len(discovered)}")
            for agent_id, agent_info in discovered.items():
                logger.debug(f"🌐 TRACE: - {agent_id}: {agent_info.get('prefered_name', 'Unknown')}")
        
        logger.debug(f"🔍 TRACE: === End Discovery Status ===")

    def _trace_openai_call(self, context: str, tools: list, user_message: str, tool_responses: list = None):
        """Enhanced tracing: OpenAI API call details"""
        logger.debug(f"🚀 TRACE: === CALLING OPENAI API: {context} ===")
        logger.debug(f"🚀 TRACE: User message: {user_message}")
        
        if tools:
            logger.debug(f"🚀 TRACE: OpenAI tools provided: {len(tools)} tools")
            for i, tool in enumerate(tools):
                tool_name = tool.get('function', {}).get('name', 'Unknown')
                logger.debug(f"🚀 TRACE: Tool {i+1}: {tool_name}")
        else:
            logger.debug(f"🚀 TRACE: NO TOOLS PROVIDED TO OPENAI!")
        
        if tool_responses:
            logger.debug(f"🚀 TRACE: Tool responses included: {len(tool_responses)} responses")
            for i, response in enumerate(tool_responses):
                tool_name = response.get('name', 'Unknown')
                logger.debug(f"🚀 TRACE: Tool response {i+1}: {tool_name}")

    def _trace_openai_response(self, response):
        """Enhanced tracing: OpenAI response analysis"""
        logger.debug(f"🎯 TRACE: === OPENAI RESPONSE RECEIVED ===")
        logger.debug(f"🎯 TRACE: Response type: {type(response)}")
        
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
            logger.debug(f"🎯 TRACE: Response message type: {type(message)}")
            
            content = getattr(message, 'content', None)
            if content:
                logger.debug(f"🎯 TRACE: Response content length: {len(content)} characters")
                logger.debug(f"🎯 TRACE: Response content preview: {content[:100]}{'...' if len(content) > 100 else ''}")
            else:
                logger.debug(f"🎯 TRACE: No content in response")
            
            if hasattr(message, 'tool_calls') and message.tool_calls:
                logger.debug(f"🎯 TRACE: *** TOOL CALLS DETECTED: {len(message.tool_calls)} ***")
                for i, tool_call in enumerate(message.tool_calls):
                    logger.debug(f"🎯 TRACE: Tool call {i+1}: {tool_call.function.name}")
                    logger.debug(f"🎯 TRACE: Tool call args: {tool_call.function.arguments}")
            else:
                logger.debug(f"🎯 TRACE: *** NO TOOL CALLS - DIRECT RESPONSE ***")

    async def close(self):
        """Clean up resources"""
        try:
            # Close OpenAI-specific resources
            if hasattr(self, 'generic_client') and self.generic_client is not None:
                if asyncio.iscoroutinefunction(self.generic_client.close):
                    await self.generic_client.close()
                else:
                    self.generic_client.close()
            
            # Close base class resources
            await super().close()
            
            logger.debug(f"OpenAIGenesisAgent closed successfully")
        except Exception as e:
            logger.error(f"Error closing OpenAIGenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    async def process_message(self, message: str) -> str:
        """
        Process a message using OpenAI and return the response.
        This method is monitored by the Genesis framework.
        
        Args:
            message: The message to process
            
        Returns:
            The agent's response to the message
        """
        try:
            # Process the message using OpenAI's process_request method
            response = await self.process_request({"message": message})
            
            # Publish a monitoring event for the successful response
            self.publish_monitoring_event(
                event_type="AGENT_RESPONSE",
                result_data={"response": response}
            )
            
            return response.get("message", "No response generated")
            
        except Exception as e:
            # Publish a monitoring event for the error
            self.publish_monitoring_event(
                event_type="AGENT_STATUS",
                status_data={"error": str(e)}
            )
            raise

    async def _ensure_internal_tools_discovered(self):
        """
        Discover and register internal methods decorated with @genesis_tool.
        
        This method automatically scans the agent for methods decorated with @genesis_tool,
        generates appropriate tool schemas, and stores them for automatic injection
        into OpenAI (or other LLM) clients.
        """
        if self.enable_tracing:
            logger.debug("===== TRACING: Discovering internal @genesis_tool methods =====")
        
        # Initialize internal tools cache if not exists
        if not hasattr(self, 'internal_tools_cache'):
            self.internal_tools_cache = {}
        
        # Scan all methods for @genesis_tool decorator
        tool_methods = []
        for attr_name in dir(self):
            if attr_name.startswith('_'):  # Skip private methods
                continue
                
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, '__is_genesis_tool__'):
                tool_meta = getattr(attr, '__genesis_tool_meta__', {})
                if tool_meta:
                    tool_methods.append((attr_name, attr, tool_meta))
                    if self.enable_tracing:
                        logger.debug(f"===== TRACING: Found @genesis_tool method: {attr_name} =====")
        
        if not tool_methods:
            if self.enable_tracing:
                logger.debug("===== TRACING: No @genesis_tool methods found =====")
            return
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Processing {len(tool_methods)} @genesis_tool methods =====")
        
        # Generate tool schemas for discovered methods
        for method_name, method, tool_meta in tool_methods:
            # Store method reference and metadata
            self.internal_tools_cache[method_name] = {
                "method": method,
                "metadata": tool_meta,
                "function_name": tool_meta.get("function_name", method_name)
            }
            
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Registered internal tool: {method_name} =====")
                logger.debug(f"===== TRACING: Tool metadata: {tool_meta} =====")
        
        # Update system prompt to include internal tools
        if self.internal_tools_cache:
            if self.enable_tracing:
                logger.debug("===== TRACING: Internal tools available, ensuring function-based prompt =====")
            self.system_prompt = self.function_based_system_prompt

    async def _call_internal_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call an internal @genesis_tool decorated method.
        
        Args:
            tool_name: Name of the internal tool/method to call
            **kwargs: Arguments to pass to the method
            
        Returns:
            Result from the internal method
        """
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Calling internal tool {tool_name} =====")
            logger.debug(f"===== TRACING: Tool arguments: {json.dumps(kwargs, indent=2)} =====")
        
        if not hasattr(self, 'internal_tools_cache') or tool_name not in self.internal_tools_cache:
            error_msg = f"Internal tool not found: {tool_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        tool_info = self.internal_tools_cache[tool_name]
        method = tool_info["method"]
        
        try:
            start_time = time.time()
            
            # Call the internal method
            if asyncio.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = method(**kwargs)
                
            end_time = time.time()
            
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Internal tool call completed in {end_time - start_time:.2f} seconds =====")
                logger.debug(f"===== TRACING: Internal tool result: {result} =====")
            
            return result
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling internal tool {tool_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise

async def run_test():
    """Test the OpenAIGenesisAgent"""
    agent = None
    try:
        # Create agent
        agent = OpenAIGenesisAgent()
        
        # Test with a single request to test the calculator service
        test_message = "What is 31337 multiplied by 424242?"
        
        logger.info(f"\n===== Testing agent with message: {test_message} =====")
        
        # Process request
        result = await agent.process_request({"message": test_message})
        
        # Print result
        if 'status' in result:
            logger.info(f"Result status: {result['status']}")
        logger.info(f"Response: {result['message']}")
        logger.info("=" * 50)
        
        return 0
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
        return 1
    finally:
        # Clean up
        if agent:
            await agent.close()

def main():
    """Main entry point"""
    try:
        return asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted")
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
