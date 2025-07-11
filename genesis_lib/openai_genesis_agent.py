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
                 base_service_name: str = "OpenAIChat", service_instance_tag: Optional[str] = None, 
                 description: str = None, enable_tracing: bool = False, 
                 enable_agent_communication: bool = True, memory_adapter=None):
        print(f"OpenAIGenesisAgent __init__ called for {agent_name}")
        """Initialize the agent with the specified models
        
        Args:
            model_name: OpenAI model to use (default: gpt-4o)
            classifier_model_name: Model to use for function classification (default: gpt-4o-mini)
            domain_id: DDS domain ID (default: 0)
            agent_name: Name of the agent (default: "OpenAIAgent")
            base_service_name: The fundamental type of service (default: "OpenAIChat")
            service_instance_tag: Optional tag for unique RPC service name instance
            description: Optional description of the agent
            enable_tracing: Whether to enable detailed tracing logs (default: False)
            enable_agent_communication: Whether to enable agent-to-agent communication (default: True)
        """
        # Store tracing configuration
        self.enable_tracing = enable_tracing
        
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
            service_instance_tag=service_instance_tag,
            agent_type="AGENT",  # This is a primary agent
            description=description or f"An OpenAI-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=memory_adapter
        )
        
        # Get API key from environment
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize generic client for function discovery, passing the agent's participant
        # self.generic_client = GenericFunctionClient(participant=self.app.participant)
        # Ensure GenericFunctionClient uses the SAME FunctionRegistry as the GenesisApp
        logger.debug(f"===== TRACING: Initializing GenericFunctionClient using agent app's FunctionRegistry: {id(self.app.function_registry)} =====")
        self.generic_client = GenericFunctionClient(function_registry=self.app.function_registry)
        self.function_cache = {}  # Cache for discovered functions
        
        # Initialize agent cache for agent-as-tool pattern
        self.agent_cache = {}  # Cache for discovered agents that can be called as tools
        
        # Register discovery callback with the function registry for asynchronous edge discovery
        self.app.function_registry.add_discovery_callback(self._on_function_discovered)
        
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
    
    def _on_function_discovered(self, function_id: str, function_info: dict):
        """
        Callback method called when a function is discovered asynchronously.
        This publishes edge discovery events immediately when functions become available.
        
        Args:
            function_id: ID of the discovered function
            function_info: Dictionary containing function information
        """
        try:
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Function discovered callback: {function_info.get('name', 'unknown')} ({function_id}) =====")
            
            provider_id = function_info.get('provider_id', '')
            function_name = function_info.get('name', 'unknown')
            
            if provider_id:
                # Only publish AGENT_TO_SERVICE edge discovery event
                # The service will handle SERVICE_TO_FUNCTION edges
                reason = f"provider={provider_id} client={self.app.agent_id} function={function_id} name={function_name}"
                if self.enable_tracing:
                    logger.debug(f"Publishing AGENT_TO_SERVICE edge discovery event with reason: {reason}")

                self.graph.publish_edge(
                    source_id=self.app.agent_id,
                    target_id=provider_id,
                    edge_type="AGENT_TO_SERVICE",
                    attrs={
                        "agent_type": self.agent_type,
                        "service": self.base_service_name,
                        "edge_type": "agent_to_service",
                        "provider_id": provider_id,
                        "client_id": self.app.agent_id,
                        "function_id": function_id,
                        "function_name": function_name,
                        "reason": reason
                    },
                    component_type=1  # AGENT_PRIMARY
                )
                if self.enable_tracing:
                    logger.debug("Published AGENT_TO_SERVICE edge discovery event")

                # NOTE: Removed direct FUNCTION_CONNECTION edge to function UUID
                # The service provider will handle SERVICE_TO_FUNCTION edges
                    
        except Exception as e:
            logger.error(f"Error in function discovery callback: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _ensure_functions_discovered(self):
        """Ensure functions are discovered before use. Relies on GenericFunctionClient to asynchronously update its list.
        This method populates the agent's function_cache based on the current list from GenericFunctionClient ON EVERY CALL.
        """
        logger.debug("===== TRACING: Attempting to populate function cache from GenericFunctionClient... =====")
        
        functions = self.generic_client.list_available_functions()
        
        # Track which functions are newly discovered
        previously_cached_functions = set(self.function_cache.keys())
        
        # Reset function cache for fresh population
        self.function_cache = {}

        if not functions:
            logger.debug("===== TRACING: No functions currently listed by GenericFunctionClient. =====")
            # Only use general prompt if BOTH functions and agents are unavailable
            if not self.agent_cache:
                logger.debug("===== TRACING: No functions or agents available. General prompt will be used. =====")
                self.system_prompt = self.general_system_prompt
            else:
                logger.debug("===== TRACING: No functions but agents are available. Function-based prompt maintained. =====")
            return
        
        logger.debug(f"===== TRACING: {len(functions)} functions listed by GenericFunctionClient. Populating cache. System prompt set to function-based. =====")
        self.system_prompt = self.function_based_system_prompt

        newly_discovered_functions = []
        
        for func_data in functions: # Iterate over list of dicts
            # func_data should be a dictionary from the list returned by GenericFunctionClient
            # It has keys like 'name', 'description', 'schema', 'function_id'
            func_id = func_data["function_id"]
            func_name = func_data["name"]
            
            self.function_cache[func_name] = {
                "function_id": func_id,
                "description": func_data["description"],
                "schema": func_data["schema"],
                "provider_id": func_data.get("provider_id"),
                "classification": { # Default classification, can be overridden if func_data has it
                    "entity_type": "function",
                    "domain": ["unknown"],
                    "operation_type": func_data.get("operation_type", "unknown"),
                    "io_types": {
                        "input": ["unknown"],
                        "output": ["unknown"]
                    },
                    "performance": {
                        "latency": "unknown",
                        "throughput": "unknown"
                    },
                    "security": {
                        "level": "public",
                        "authentication": "none"
                    }
                }
            }
            # If func_data itself contains a 'classification' field, merge it or use it
            if "classification" in func_data and isinstance(func_data["classification"], dict):
                self.function_cache[func_name]["classification"].update(func_data["classification"])

            # Check if this is a newly discovered function
            if func_name not in previously_cached_functions:
                newly_discovered_functions.append(func_data)
            
            logger.debug("===== TRACING: Processing discovered function for cache =====")
            logger.debug(f"Name: {func_data['name']}")
            logger.debug(f"ID: {func_id}")
            logger.debug(f"Description: {func_data['description']}")
            logger.debug(f"Schema: {json.dumps(func_data['schema'], indent=2)}")
            logger.debug("=" * 80)
            
            # Publish discovery event (consider if this is too noisy here - it's already done by FunctionRegistry)
            # For now, let's keep it to see if OpenAIGenesisAgent "sees" them
            self.publish_monitoring_event(
                "AGENT_DISCOVERY", # This event type might need review for semantic correctness here
                metadata={
                    "function_id": func_id,
                    "function_name": func_data["name"],
                    "provider_id": func_data.get("provider_id"),
                    "source": "OpenAIGenesisAgent._ensure_functions_discovered"
                }
            )
        
        # Publish edge discovery events for newly discovered functions (asynchronously discovered)
        if newly_discovered_functions:
            logger.debug(f"===== TRACING: Publishing edge discovery events for {len(newly_discovered_functions)} newly discovered functions =====")
            
            for func_data in newly_discovered_functions:
                provider_id = func_data.get('provider_id', '')
                function_name = func_data.get('name', 'unknown')
                function_id = func_data.get('function_id', '')
                
                if provider_id:
                    # Only publish AGENT_TO_SERVICE edge discovery event
                    # The service will handle SERVICE_TO_FUNCTION edges
                    reason = f"provider={provider_id} client={self.app.agent_id} function={function_id} name={function_name}"
                    logger.debug(f"Publishing AGENT_TO_SERVICE edge discovery event with reason: {reason}")

                    self.publish_component_lifecycle_event(
                        category="EDGE_DISCOVERY",
                        reason=reason,
                        previous_state="DISCOVERING",
                        new_state="DISCOVERING",
                        capabilities=json.dumps({
                            "agent_type": self.agent_type,
                            "service": self.base_service_name,
                            "edge_type": "agent_to_service",
                            "provider_id": provider_id,
                            "client_id": self.app.agent_id,
                            "function_id": function_id,
                            "function_name": function_name
                        }),
                        source_id=self.app.agent_id,
                        target_id=provider_id,
                        connection_type="AGENT_TO_SERVICE"
                    )
                    logger.debug("Published AGENT_TO_SERVICE edge discovery event")

                    # NOTE: Removed direct FUNCTION_CONNECTION edge to function UUID
                    # The service provider will handle SERVICE_TO_FUNCTION edges
    
    async def _ensure_agents_discovered(self):
        """
        Ensure agents are discovered and available as tools based on their capabilities.
        This method populates the agent_cache with discovered agents that can be called as tools
        based on their advertised functionality, NOT their names.
        """
        if self.enable_tracing:
            logger.debug("===== TRACING: Ensuring agents are discovered for capability-based agent-as-tool pattern =====")
        
        # Skip if agent communication is not enabled
        if not hasattr(self, 'agent_communication') or not self.agent_communication:
            if self.enable_tracing:
                logger.debug("===== TRACING: Agent communication not enabled, skipping agent discovery =====")
            return
        
        # Get discovered agents from the communication mixin
        discovered_agents = self.get_discovered_agents()
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Raw discovered agents from get_discovered_agents(): {discovered_agents} =====")
        
        # Track which agents are newly discovered
        previously_cached_agents = set(self.agent_cache.keys())
        
        # Reset agent cache for fresh population
        self.agent_cache = {}
        
        if not discovered_agents:
            if self.enable_tracing:
                logger.debug("===== TRACING: No agents currently discovered. Agent tools will not be available. =====")
            return
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: {len(discovered_agents)} agents discovered. Creating capability-based tools. =====")
        
        # Switch to function-based system prompt when agents are available as tools
        # This ensures the LLM knows it has specialized agents available
        if self.enable_tracing:
            logger.debug("===== TRACING: Agents discovered - switching to function-based system prompt =====")
        self.system_prompt = self.function_based_system_prompt
        
        newly_discovered_agents = []
        
        for agent_id, agent_info in discovered_agents.items():
            # Skip self to avoid circular calls
            if agent_id == self.app.agent_id:
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Skipping self agent {agent_id} =====")
                continue
            
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Processing discovered agent {agent_id}: {agent_info} =====")
            
            # Extract capability information
            agent_name = agent_info.get('name', agent_id)
            agent_type = agent_info.get('agent_type', 'AGENT')
            service_name = agent_info.get('service_name', 'UnknownService')
            description = agent_info.get('description', f'Agent {agent_name}')
            capabilities = agent_info.get('capabilities', [])
            specializations = agent_info.get('specializations', [])
            
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Agent {agent_name} capabilities: {capabilities}, specializations: {specializations} =====")
            
            # Create capability-based tool names instead of name-based ones
            tool_names = self._generate_capability_based_tool_names(
                agent_info, capabilities, specializations, service_name
            )
            
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Generated {len(tool_names)} tools for agent {agent_name}: {list(tool_names.keys())} =====")
            
            # Create tool entries for each capability/specialization
            for tool_name, tool_description in tool_names.items():
                self.agent_cache[tool_name] = {
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
                
                # Check if this is a newly discovered tool
                if tool_name not in previously_cached_agents:
                    newly_discovered_agents.append({
                        "tool_name": tool_name,
                        "agent_id": agent_id,
                        "agent_info": agent_info,
                        "capability_description": tool_description
                    })
                
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Created capability-based tool: {tool_name} -> {agent_id} =====")
        
        # Publish edge discovery events for newly discovered agent tools
        if newly_discovered_agents:
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Publishing capability-based agent tool discovery events for {len(newly_discovered_agents)} tools =====")
            
            for tool_data in newly_discovered_agents:
                self.graph.publish_edge(
                    source_id=self.app.agent_id,
                    target_id=tool_data['agent_id'],
                    edge_type="CAPABILITY_BASED_TOOL",
                    attrs={
                        "agent_type": self.agent_type,
                        "service": self.base_service_name,
                        "edge_type": "capability_based_agent_tool",
                        "target_agent_id": tool_data['agent_id'],
                        "client_id": self.app.agent_id,
                        "tool_name": tool_data['tool_name'],
                        "capability_description": tool_data['capability_description'],
                        "reason": f"capability_tool={tool_data['tool_name']} agent={tool_data['agent_id']} client={self.app.agent_id}"
                    },
                    component_type=1  # AGENT_PRIMARY
                )
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Agent cache populated with {len(self.agent_cache)} capability-based agent tools =====")
            for tool_name, tool_info in self.agent_cache.items():
                logger.debug(f"===== TRACING: Tool '{tool_name}' -> Agent {tool_info['agent_id']} ({tool_info['agent_name']}) =====")
    
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
        
        for tool_name, agent_info in self.agent_cache.items():
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
        
        for name, func_info in self.function_cache.items():
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
        
        if function_name not in self.function_cache:
            error_msg = f"Function not found: {function_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        try:
            # Call the function through the generic client
            start_time = time.time()
            result = await self.generic_client.call_function(
                self.function_cache[function_name]["function_id"],
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
        
        if agent_tool_name not in self.agent_cache:
            error_msg = f"Agent tool not found: {agent_tool_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        agent_info = self.agent_cache[agent_tool_name]
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
            
            # Ensure functions are discovered
            await self._ensure_functions_discovered()
            
            # Ensure agents are discovered (critical for agent-as-tool pattern)
            await self._ensure_agents_discovered()
            
            # Ensure internal tools are discovered (@genesis_tool decorated methods)
            await self._ensure_internal_tools_discovered()
            
            # Enhanced tracing: Discovery status after discovery
            if self.enable_tracing:
                self._trace_discovery_status("AFTER DISCOVERY")
            
            # Generate chain and call IDs for tracking
            chain_id = str(uuid.uuid4())
            call_id = str(uuid.uuid4())
            
            # If no functions are available, proceed with basic response
            if not self.function_cache:
                logger.debug("===== TRACING: No external functions available, checking for internal tools or agents =====")
                
                # Check if we have internal tools or agents available
                has_internal_tools = hasattr(self, 'internal_tools_cache') and self.internal_tools_cache
                has_agents = bool(self.agent_cache)
                
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
            available_functions = [
                {
                    "name": name,
                    "description": info["description"],
                    "schema": info["schema"],
                    "classification": info.get("classification", {})
                }
                for name, info in self.function_cache.items()
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
            for func in relevant_functions:
                # Create chain event for classification result
                self._publish_classification_result(
                    chain_id=chain_id,
                    call_id=call_id,
                    classified_function_name=func["name"],
                    classified_function_id=self.function_cache[func["name"]]["function_id"]
                )
                
                # Create component lifecycle event for function classification
                self.graph.publish_node(
                    component_id=self.app.agent_id,
                    component_type=1,  # AGENT_PRIMARY
                    state=2,  # READY
                    attrs={
                        "function_name": func["name"],
                        "description": func["description"],
                        "classification": func["classification"],
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
                tool_choice="auto"
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
            
            # Check if the model wants to call a function
            if message.tool_calls:
                logger.debug(f"===== TRACING: Model requested function call(s): {len(message.tool_calls)} =======")
                
                # Process each tool call (function or agent)
                tool_responses = []
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.debug(f"===== TRACING: Processing tool call: {tool_name} =====")
                    
                    # Determine if this is a function call, agent call, or internal tool call
                    is_function_call = tool_name in self.function_cache
                    is_agent_call = tool_name in self.agent_cache
                    is_internal_tool_call = hasattr(self, 'internal_tools_cache') and tool_name in self.internal_tools_cache
                    
                    try:
                        if is_function_call:
                            logger.debug(f"===== TRACING: Tool {tool_name} is a FUNCTION call =====")
                            
                            # Create chain event for function call start
                            self._publish_function_call_start(
                                chain_id=chain_id,
                                call_id=call_id,
                                function_name=tool_name,
                                function_id=self.function_cache[tool_name]["function_id"],
                                target_provider_id=self.function_cache[tool_name].get("provider_id")
                            )
                            
                            # Call the function through the generic client
                            start_time = time.time()
                            tool_result = await self._call_function(tool_name, **tool_args)
                            end_time = time.time()
                            
                            # Create chain event for function call completion
                            self._publish_function_call_complete(
                                chain_id=chain_id,
                                call_id=call_id,
                                function_name=tool_name,
                                function_id=self.function_cache[tool_name]["function_id"],
                                source_provider_id=self.function_cache[tool_name].get("provider_id")
                            )
                            
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
                            agent_info = self.agent_cache[tool_name]
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
                
                # If we have tool responses, send them back to the model
                if tool_responses:
                    # Create a new conversation with the tool responses
                    logger.debug("===== TRACING: Sending tool responses back to OpenAI =====")
                    
                    # Create chain event for second LLM call start
                    self._publish_llm_call_start(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # Enhanced tracing: Second OpenAI API call details
                    if self.enable_tracing:
                        self._trace_openai_call("Tool response processing", [], user_message, tool_responses)
                    
                    # Retrieve memory and format for OpenAI (second call)
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
                    messages.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})
                    
                    # Add tool responses
                    messages.extend(tool_responses)
                    
                    second_response = self.client.chat.completions.create(
                        model=self.model_config['model_name'],
                        messages=messages,
                        tools=function_schemas,
                        tool_choice="auto"
                    )
                    
                    # Enhanced tracing: Second OpenAI response analysis
                    if self.enable_tracing:
                        self._trace_openai_response(second_response)
                    
                    # Create chain event for second LLM call completion
                    self._publish_llm_call_complete(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # Extract the final response
                    final_message = second_response.choices[0].message.content
                    logger.debug(f"===== TRACING: Final response: {final_message} =====")
                    
                    # Enhanced tracing: Final discovery status
                    if self.enable_tracing:
                        self._trace_discovery_status("AFTER PROCESSING")
                    
                    # Write user and agent messages to memory
                    self.memory.write(user_message, metadata={"role": "user"})
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
            response = await self.process_request({"message": message})
            
            # Format response for agent-to-agent communication
            agent_response = {
                "message": response.get("message", "No response generated"),
                "status": response.get("status", 0),
                "conversation_id": conversation_id
            }
            
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
        logger.debug(f"🔧 TRACE: Function cache: {len(self.function_cache)} functions")
        for name, info in self.function_cache.items():
            logger.debug(f"🔧 TRACE: - {name}: {info.get('description', 'No description')}")
        
        logger.debug(f"🤝 TRACE: Agent cache: {len(self.agent_cache)} agent tools")
        for name, info in self.agent_cache.items():
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
            # Remove discovery callback
            if hasattr(self, 'app') and hasattr(self.app, 'function_registry'):
                self.app.function_registry.remove_discovery_callback(self._on_function_discovered)
            
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
