#!/usr/bin/env python3
"""
OpenAI Genesis Agent - LLM Provider Implementation

This module defines the OpenAIGenesisAgent class, which extends the MonitoredAgent
to provide an agent implementation specifically utilizing the OpenAI API.
It integrates OpenAI's chat completion capabilities, including function calling,
with the Genesis framework's monitoring and function discovery features.

Architecture Layers:
  GenesisAgent (agent.py)
    - Provider-agnostic discovery (_get_available_functions, _get_available_agent_tools)
    - Tool routing (_call_function, _call_agent, _call_internal_tool)
    - Internal tool discovery (_ensure_internal_tools_discovered)
    
  MonitoredAgent (monitored_agent.py)
    - Monitoring wrapper (process_request with events)
    - Graph publishing helpers (_publish_classification_node, etc.)
    - Chain tracking (_publish_llm_call_start, _publish_llm_call_complete)
    - Agent communication monitoring (_publish_agent_chain_event)
    
  OpenAIGenesisAgent (this file)
    - OpenAI-specific API calls (client.chat.completions.create)
    - OpenAI message format and conversation management
    - OpenAI tool schema generation (_get_all_tool_schemas_for_openai)
    - Multi-turn tool conversation handling

Future Providers:
  - AnthropicGenesisAgent: Use AnthropicSchemaGenerator + messages.create API
  - GeminiGenesisAgent: Use GeminiSchemaGenerator + appropriate API
  - Custom/Local LLMs: Use LocalLLMSchemaGenerator + custom endpoints
  
All providers inherit the same discovery, routing, and monitoring from base classes,
only implementing provider-specific LLM API calls and schema formatting.

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
    
    def _convert_agents_to_tools(self):
        """
        Convert agent schemas to OpenAI tool format.
        
        Gets universal agent schemas from parent class and wraps them
        in OpenAI's tool format.
        """
        logger.debug("===== TRACING: Converting agent schemas to OpenAI tool format =====")
        
        # Get universal agent schemas from parent (provider-agnostic)
        agent_schemas = self._get_agent_tool_schemas()
        
        # Wrap in OpenAI-specific format
        openai_tools = []
        for schema in agent_schemas:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": {
                        "type": "object",
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
    
    # Implement abstract methods for LLM provider
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None, 
                        tool_choice: str = "auto") -> Any:
        """OpenAI-specific LLM call"""
        kwargs = {
            "model": self.model_config['model_name'],
            "messages": messages
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        
        return self.client.chat.completions.create(**kwargs)

    def _format_messages(self, user_message: str, system_prompt: str, 
                         memory_items: List[Dict]) -> List[Dict]:
        """Format in OpenAI message format"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history from memory
        # Filter out tool messages since they can't be reconstructed without tool_calls context
        for entry in memory_items:
            item = entry["item"]
            meta = entry.get("metadata", {})
            role = meta.get("role")
            
            # Skip tool/assistant_tool messages - they require full tool_calls context
            if role in ("tool", "assistant_tool"):
                continue
                
            if role not in ("user", "assistant"):
                # Fallback: alternate roles if metadata is missing
                idx = memory_items.index(entry)
                role = "user" if idx % 2 == 0 else "assistant"
            messages.append({"role": role, "content": str(item)})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        return messages

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict]]:
        """Extract tool calls from OpenAI response"""
        message = response.choices[0].message
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return None
        
        return [
            {
                'id': tc.id,
                'name': tc.function.name,
                'arguments': json.loads(tc.function.arguments)
            }
            for tc in message.tool_calls
        ]

    def _extract_text_response(self, response: Any) -> str:
        """Extract text from OpenAI response"""
        return response.choices[0].message.content

    def _create_assistant_message(self, response: Any) -> Dict:
        """Create assistant message dict from OpenAI response for conversation history"""
        message = response.choices[0].message
        assistant_msg = {
            "role": "assistant",
            "content": message.content if message.content is not None else ""
        }
        
        # Add tool_calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            assistant_msg["tool_calls"] = message.tool_calls
        
        return assistant_msg
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """OpenAI-specific request processing using inherited orchestration"""
        user_message = request.get("message", "")
        logger.debug(f"===== TRACING: Processing request: {user_message} =====")
        
        try:
            # Enhanced tracing: Discovery status before processing
            if self.enable_tracing:
                self._trace_discovery_status("BEFORE PROCESSING")
            
            # Ensure internal tools are discovered (@genesis_tool decorated methods)
            await self._ensure_internal_tools_discovered()
            
            # Check what tools are available
            available_functions = self._get_available_functions()
            agent_tools = self._get_available_agent_tools()
            
            # Select system prompt based on tool availability
            if not available_functions and not agent_tools:
                system_prompt = self.general_system_prompt
            else:
                system_prompt = self.function_based_system_prompt
            
            # Enhanced tracing: Discovery status after discovery
            if self.enable_tracing:
                self._trace_discovery_status("AFTER DISCOVERY")
            
            # Get tools in OpenAI format
            tools = self._get_all_tool_schemas_for_openai()
            
            if not tools:
                # Simple conversation (no tools available)
                logger.debug("===== TRACING: No tools available, using simple conversation =====")
                
                messages = self._format_messages(user_message, system_prompt, self.memory.retrieve(k=8))
                response = await self._call_llm(messages)
                text = self._extract_text_response(response)
                
                self.memory.write(user_message, metadata={"role": "user"})
                self.memory.write(text, metadata={"role": "assistant"})
                return {"message": text, "status": 0}
            
            # Tool-based conversation (orchestrated by parent class)
            logger.debug(f"===== TRACING: Using tool-based orchestration with {len(tools)} tools =====")
            
            result = await self._orchestrate_tool_request(
                user_message=user_message,
                tools=tools,
                system_prompt=system_prompt,
                tool_choice=self.openai_tool_choice
            )
            
            # Enhanced tracing: Final discovery status
            if self.enable_tracing:
                self._trace_discovery_status("AFTER PROCESSING")
            
            return result
                
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
