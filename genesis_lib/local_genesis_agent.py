#!/usr/bin/env python3
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
Local Genesis Agent - Ollama LLM Provider Implementation

This module provides the LocalGenesisAgent class, which implements Ollama integration
for the Genesis framework, enabling local LLM inference without API costs or cloud dependencies.

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

LocalGenesisAgent (THIS FILE - genesis_lib/local_genesis_agent.py)
└─ Ollama-Specific Implementation:
   ├─ ollama.chat() - Local Ollama API calls
   ├─ OpenAI-compatible message format: [{"role": "system"|"user"|"assistant", "content": "..."}]
   ├─ OpenAI-compatible tool format: {"type": "function", "function": {...}}
   └─ Implements 7 abstract methods (see detailed docs below)

=================================================================================================
WHAT YOU INHERIT FOR FREE - No Need to Implement
=================================================================================================

When you create a local agent, you automatically get ALL of this functionality:

1. **Tool Discovery** (from GenesisAgent)
2. **Tool Routing** (from GenesisAgent)
3. **Multi-Turn Orchestration** (from GenesisAgent)
4. **Memory Management** (from GenesisAgent)
5. **Monitoring & Observability** (from MonitoredAgent)
6. **Agent Communication** (from MonitoredAgent)
7. **RPC Infrastructure** (from MonitoredAgent via GenesisApp)
8. **User-Defined Capabilities** (from GenesisAgent)

See openai_genesis_agent.py for detailed documentation on inherited features.

=================================================================================================
OLLAMA-SPECIFIC FEATURES
=================================================================================================

Benefits of Local Inference:
- ✅ No API costs (completely free)
- ✅ Data privacy (everything runs locally)
- ✅ No rate limits
- ✅ No internet dependency
- ✅ Full control over model versions
- ⚠️  Slower than cloud APIs (depends on hardware)
- ⚠️  Requires local GPU for best performance

Recommended Models:
- Fast/Small: llama3.2:1b, llama3.2:3b (good for testing)
- Balanced: mistral:7b, llama3.1:8b (good general purpose)
- Advanced: llama3.3:70b, qwen2.5:32b (requires powerful GPU)

Setup:
1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh
2. Pull a model: ollama pull llama3.2:3b
3. (Optional) Set OLLAMA_HOST env var if not using default localhost:11434

=================================================================================================

"""

import os
import logging
import json
import asyncio
import traceback
import uuid
from typing import Dict, Any, List, Optional

try:
    import ollama
except ImportError:
    raise ImportError(
        "Ollama package not found. Install it with: pip install ollama\n"
        "Also ensure Ollama is installed and running: https://ollama.com/download"
    )

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.function_requester import FunctionRequester
from genesis_lib.schema_generators import get_schema_generator

logger = logging.getLogger("local_genesis_agent")

class LocalGenesisAgent(MonitoredAgent):
    """
    Ollama API implementation of GenesisAgent for local LLM inference.
    
    This class implements Ollama integration for the Genesis framework,
    enabling completely local LLM inference without API costs or cloud dependencies.
    """
    
    def __init__(self, model_name="llama3.2:3b", classifier_model_name="llama3.2:1b",
                 ollama_host: str = None,
                 domain_id: int = 0, agent_name: str = "LocalAgent", 
                 base_service_name: str = "LocalChat",
                 description: str = None, 
                 enable_tracing: bool = False,
                 enable_monitoring: bool = True,
                 enable_agent_communication: bool = True, 
                 memory_adapter=None,
                 auto_run: bool = True, 
                 service_instance_tag: str = ""):
        """
        Initialize Ollama-based Genesis agent for local inference.
        
        Args:
            model_name: Ollama model identifier (e.g., "llama3.2:3b", "mistral:7b")
            classifier_model_name: Model for function classification (usually smaller/faster)
            ollama_host: Ollama server URL (default: http://localhost:11434)
            domain_id: DDS domain ID (0-232) - network isolation boundary
            agent_name: Human-readable instance identifier
            base_service_name: Service capability type (e.g., "LocalChat", "WeatherService")
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
        
        logger.debug(f"LocalGenesisAgent __init__ called for {agent_name}")
        
        if self.enable_tracing:
            logger.debug(f"Initializing LocalGenesisAgent with model {model_name}")
        
        # Store provider-specific model configuration
        self.model_config = {
            "model_name": model_name,
            "classifier_model_name": classifier_model_name
        }
        
        # Initialize parent class (MonitoredAgent → GenesisAgent)
        # Note: We don't pass classifier_provider/model since Ollama isn't in LLMFactory yet
        # Function classification will be disabled (all tools exposed to LLM)
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="AGENT",
            description=description or f"A local Ollama-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            enable_monitoring=enable_monitoring,
            memory_adapter=memory_adapter,
            auto_run=auto_run,
            service_instance_tag=service_instance_tag,
            classifier_provider=None,  # Skip classifier for now (no token costs locally)
            classifier_model=None
        )
        
        # Get Ollama host from parameter or environment variable
        # Default to localhost:11434 if not specified
        self.ollama_host = ollama_host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        
        if self.enable_tracing:
            logger.debug(f"Using Ollama host: {self.ollama_host}")
        
        # Initialize Ollama client
        try:
            self.client = ollama.Client(host=self.ollama_host)
            
            # Test connection by listing models
            models = self.client.list()
            
            # Extract model names - handle both dict and object response formats
            available_model_names = []
            if hasattr(models, 'models'):
                # Object-style response
                for m in models.models:
                    if hasattr(m, 'model'):
                        available_model_names.append(m.model)
                    elif hasattr(m, 'name'):
                        available_model_names.append(m.name)
            elif isinstance(models, dict) and 'models' in models:
                # Dict-style response
                for m in models['models']:
                    if isinstance(m, dict):
                        available_model_names.append(m.get('model') or m.get('name', ''))
                    elif hasattr(m, 'model'):
                        available_model_names.append(m.model)
                    elif hasattr(m, 'name'):
                        available_model_names.append(m.name)
            
            if self.enable_tracing:
                logger.debug(f"Successfully connected to Ollama. Available models: {available_model_names}")
                
            # Check if requested model is available
            if available_model_names and model_name not in available_model_names:
                logger.warning(
                    f"Model '{model_name}' not found in Ollama. "
                    f"Available models: {available_model_names}\n"
                    f"Pull the model with: ollama pull {model_name}"
                )
                
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Ollama at {self.ollama_host}. "
                f"Ensure Ollama is installed and running.\n"
                f"Install: curl -fsSL https://ollama.com/install.sh | sh\n"
                f"Start: ollama serve\n"
                f"Error: {str(e)}"
            )
        
        # Initialize function requester for RPC calls (provider-agnostic)
        logger.debug(f"===== TRACING: Initializing FunctionRequester using agent app's DDSFunctionDiscovery: {id(self.app.function_discovery)} =====")
        self.function_requester = FunctionRequester(discovery=self.app.function_discovery)
        
        # Skip function classifier for now (no token costs with local models)
        # Can be added later if needed for performance optimization
        self.function_classifier = None
        
        # Define system prompts (same as OpenAI - work well for all LLMs)
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
        self.set_agent_capabilities(
            supported_tasks=["text_generation", "conversation", "local_inference"],
            additional_capabilities={
                **self.model_config,
                "provider": "ollama",
                "host": self.ollama_host
            }
        )
        
        if self.enable_tracing:
            logger.debug("LocalGenesisAgent initialized successfully")
    
    # =============================================================================================
    # TOOL SCHEMA GENERATION - Provider-Specific Format Conversion
    # =============================================================================================
    # Ollama uses OpenAI-compatible tool format, so we can reuse most of the logic
    
    def _convert_agents_to_tools(self):
        """
        Convert discovered agents to Ollama tool schema format (OpenAI-compatible).
        
        Returns:
            List of agent tools in Ollama/OpenAI format
        """
        if self.enable_tracing:
            logger.info("===== TRACING: Converting agent schemas to Ollama tool format =====")
        
        # Get universal agent schemas from parent (provider-agnostic)
        agent_schemas = self._get_agent_tool_schemas()
        if self.enable_tracing:
            logger.info(f"===== TRACING: Got {len(agent_schemas)} agent schemas from _get_agent_tool_schemas =====")
        
        # Log discovered agents for debugging
        available_agents = self._get_available_agent_tools()
        if self.enable_tracing:
            logger.info(f"===== TRACING: Available agent tools: {list(available_agents.keys())} =====")
        
        # Wrap in Ollama/OpenAI-compatible format
        ollama_tools = []
        for schema in agent_schemas:
            ollama_tools.append({
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
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Wrapped agent tool in Ollama format: {schema['name']} =====")
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generated {len(ollama_tools)} Ollama agent tools =====")
        return ollama_tools
    
    def _get_function_schemas_for_ollama(self, relevant_functions: Optional[List[str]] = None):
        """
        Convert discovered external functions to Ollama tool schema format (OpenAI-compatible).
        
        Args:
            relevant_functions: Optional list of function names to filter
            
        Returns:
            List of function schemas in Ollama/OpenAI format
        """
        if self.enable_tracing:
            logger.debug("===== TRACING: Converting function schemas for Ollama =======")
        function_schemas = []
        
        # Get all discovered functions from parent's registry
        available_functions = self._get_available_functions()
        
        for name, func_info in available_functions.items():
            # Optional filtering if relevant_functions is provided
            if relevant_functions is not None and name not in relevant_functions:
                continue
            
            # Wrap in Ollama/OpenAI tool format
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func_info["description"],
                    "parameters": func_info["schema"]  # Already JSON Schema
                }
            }
            function_schemas.append(schema)
            if self.enable_tracing:
                logger.debug(f"===== TRACING: Added schema for function: {name} =====")
        
        return function_schemas
    
    def _get_all_tool_schemas_for_ollama(self, relevant_functions: Optional[List[str]] = None):
        """
        Get ALL tool schemas in Ollama format: functions + agents + internal tools.
        
        Args:
            relevant_functions: Optional list of function names to filter
            
        Returns:
            Combined list of all tool schemas in Ollama/OpenAI format
        """
        if self.enable_tracing:
            logger.info("===== TRACING: Getting ALL tool schemas (functions + agents + internal tools) for Ollama =====")
        
        # Get each tool type in Ollama format
        function_tools = self._get_function_schemas_for_ollama(relevant_functions)
        agent_tools = self._convert_agents_to_tools()
        internal_tools = self._get_internal_tool_schemas_for_ollama()
        
        # Combine all tool types into one list
        all_tools = function_tools + agent_tools + internal_tools
        
        if self.enable_tracing:
            logger.info(f"===== TRACING: Combined {len(function_tools)} function tools + {len(agent_tools)} agent tools + {len(internal_tools)} internal tools = {len(all_tools)} total tools =====")
            if agent_tools:
                logger.info(f"===== TRACING: Agent tools exposed to LLM: {[t['function']['name'] for t in agent_tools]} =====")
        
        return all_tools

    def _get_internal_tool_schemas_for_ollama(self) -> List[Dict[str, Any]]:
        """
        Generate Ollama tool schemas for internal @genesis_tool decorated methods.
        
        Returns:
            List of internal tool schemas in Ollama/OpenAI format
        """
        # Return empty list if no internal tools discovered
        if not hasattr(self, 'internal_tools_cache') or not self.internal_tools_cache:
            return []
        
        if self.enable_tracing:
            logger.debug(f"===== TRACING: Generating Ollama schemas for {len(self.internal_tools_cache)} internal tools =====")
        
        internal_schemas = []
        
        # Get OpenAI schema generator (Ollama is compatible)
        schema_generator = get_schema_generator("openai")
        
        # Generate schema for each internal tool
        for tool_name, tool_info in self.internal_tools_cache.items():
            metadata = tool_info["metadata"]
            
            try:
                # Generate Ollama-compatible schema from universal metadata
                ollama_schema = schema_generator.generate_tool_schema(metadata)
                internal_schemas.append(ollama_schema)
                
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Generated schema for internal tool: {tool_name} =====")
                    
            except Exception as e:
                logger.error(f"Error generating schema for internal tool {tool_name}: {e}")
                
        return internal_schemas
    
    # =============================================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS - Required by GenesisAgent
    # =============================================================================================
    # These 7 methods are the ONLY provider-specific code you need to write!
    
    async def _get_tool_schemas(self) -> List[Dict]:
        """
        Get all tool schemas in provider-specific format.
        
        Note: Function classification is disabled for local models (no token costs).
        All available tools are exposed to the LLM.
        
        Returns:
            List of tool schemas in Ollama/OpenAI format
        """
        # No function classification for local models (no token costs)
        # Simply return all available tools
        return self._get_all_tool_schemas_for_ollama(relevant_functions=None)
    
    def _get_tool_choice(self) -> str:
        """
        Get provider-specific tool choice setting.
        
        Ollama does not reliably support tool_choice parameter across all models.
        Always returns "auto" to indicate default behavior (model decides when to use tools).
        Tools are still fully functional - this only affects explicit control over strategy.
        
        Returns:
            Always "auto" (Ollama uses default tool selection behavior)
        """
        return "auto"
    
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None, 
                        tool_choice: str = "auto") -> Any:
        """
        Call the Ollama API.
        
        Args:
            messages: Conversation history in Ollama/OpenAI format
            tools: Optional tool schemas in Ollama/OpenAI format
            tool_choice: How LLM should use tools
            
        Returns:
            Ollama response object (OpenAI-compatible structure)
        """
        # Build API call parameters
        kwargs = {
            "model": self.model_config['model_name'],
            "messages": messages
        }
        
        # Add tools if provided (for tool-based conversations)
        if tools:
            kwargs["tools"] = tools
            # Note: tool_choice parameter is not passed to Ollama as support varies by model
            # The model will use default behavior (auto - decides when to call tools)
            # Tools remain fully functional without explicit tool_choice control
        
        # Make the API call
        # Ollama's chat() returns an OpenAI-compatible response structure
        try:
            response = self.client.chat(**kwargs)
            return response
        except Exception as e:
            logger.error(f"Ollama API call failed: {str(e)}")
            logger.error(f"Request: model={kwargs['model']}, tools={'present' if tools else 'none'}")
            raise

    def _format_messages(self, user_message: str, system_prompt: str, 
                         memory_items: List[Dict]) -> List[Dict]:
        """
        Format conversation history in provider-specific message format.
        
        Ollama uses the same format as OpenAI, so this is identical.
        
        Args:
            user_message: Current message from user
            system_prompt: System instructions for agent behavior
            memory_items: Retrieved conversation history
            
        Returns:
            List of messages in Ollama/OpenAI format
        """
        # Start with system message
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history from memory
        for entry in memory_items:
            item = entry["item"]
            meta = entry.get("metadata", {})
            role = meta.get("role")
            
            # Filter out tool messages - they require full tool_calls context
            if role in ("tool", "assistant_tool"):
                continue
            
            # Validate role or infer from position
            if role not in ("user", "assistant"):
                idx = memory_items.index(entry)
                role = "user" if idx % 2 == 0 else "assistant"
            
            messages.append({"role": role, "content": str(item)})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict]]:
        """
        Extract tool calls from provider's response.
        
        Ollama returns OpenAI-compatible structure.
        
        Args:
            response: Ollama response object
            
        Returns:
            List of tool calls in standard format, or None if no tool calls
        """
        # Ollama response structure is OpenAI-compatible
        # Access message from response dict
        message = response.get('message', {})
        
        # Check if tool_calls exist
        tool_calls = message.get('tool_calls')
        if not tool_calls:
            return None
        
        # Convert to standard format
        result = []
        for tc in tool_calls:
            # Handle both dict and object-style access
            if isinstance(tc, dict):
                # Extract arguments and ensure it's a dict
                args = tc['function']['arguments']
                if isinstance(args, str):
                    args = json.loads(args)
                
                # Debug logging
                if self.enable_tracing:
                    logger.debug(f"===== TRACING: Extracted tool call: name={tc['function']['name']}, args={args} =====")
                
                # Clean up arguments - remove any metadata fields that shouldn't be passed
                # Sometimes Ollama includes 'function' or other metadata in arguments
                if isinstance(args, dict):
                    # Create a clean copy without metadata keys
                    clean_args = {k: v for k, v in args.items() if k not in ['function', 'name', 'id', 'type']}
                    if self.enable_tracing and args != clean_args:
                        logger.debug(f"===== TRACING: Cleaned arguments from {args} to {clean_args} =====")
                    args = clean_args
                
                result.append({
                    'id': tc.get('id', str(uuid.uuid4())),  # Generate ID if not provided
                    'name': tc['function']['name'],
                    'arguments': args
                })
            else:
                # Object-style access (if Ollama returns objects)
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                
                # Clean up arguments
                if isinstance(args, dict):
                    args = {k: v for k, v in args.items() if k not in ['function', 'name', 'id', 'type']}
                
                result.append({
                    'id': getattr(tc, 'id', str(uuid.uuid4())),
                    'name': tc.function.name,
                    'arguments': args
                })
        
        return result

    def _extract_text_response(self, response: Any) -> str:
        """
        Extract text response from provider's response.
        
        Ollama returns OpenAI-compatible structure.
        
        Args:
            response: Ollama response object
            
        Returns:
            Extracted text content as string
        """
        # Ollama response structure: {"message": {"content": "...", "role": "assistant"}}
        message = response.get('message', {})
        return message.get('content', '')

    def _create_assistant_message(self, response: Any) -> Dict:
        """
        Create assistant message dict from provider's response.
        
        Ollama returns OpenAI-compatible structure.
        
        Args:
            response: Ollama response object
            
        Returns:
            Message dict in Ollama/OpenAI format, ready to add to conversation history
        """
        # Extract message from Ollama response
        message = response.get('message', {})
        
        # Create base assistant message
        assistant_msg = {
            "role": "assistant",
            "content": message.get('content', '')
        }
        
        # Add tool_calls if present (CRITICAL for multi-turn tool usage)
        if 'tool_calls' in message and message['tool_calls']:
            assistant_msg["tool_calls"] = message['tool_calls']
        
        return assistant_msg
    
    # =============================================================================================
    # UTILITY METHODS - Optional but Helpful
    # =============================================================================================
    
    async def close(self):
        """
        Clean up provider-specific resources.
        """
        try:
            # Close Ollama-specific resources
            if hasattr(self, 'function_requester') and self.function_requester is not None:
                if asyncio.iscoroutinefunction(self.function_requester.close):
                    await self.function_requester.close()
                else:
                    self.function_requester.close()
            
            # Close base class resources (DDS, RPC, monitoring)
            await super().close()
            
            logger.debug(f"LocalGenesisAgent closed successfully")
        except Exception as e:
            logger.error(f"Error closing LocalGenesisAgent: {str(e)}")
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
