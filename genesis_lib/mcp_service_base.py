#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch

"""
GENESIS MCP Service Base - Export MCP Tools as Genesis Functions

This module provides a base class that connects to an MCP server and exports any
available MCP tools as `genesis_function`s on a monitored Genesis service. The
result: any MCP tool can be invoked as a Genesis RPC function with monitoring and
discovery integrated automatically.

=================================================================================================
ARCHITECTURE OVERVIEW - Components
=================================================================================================

1) MCPServiceBase (This class)
   - Creates a dynamic subclass of MonitoredService to host exported tools
   - Manages the MCP client session lifecycle
   - Generates Python coroutine methods for each MCP tool (decorated with
     `@genesis_function`) and binds them to the dynamic service class
   - Delegates run/advertise calls to the monitored service instance

2) MonitoredService (from genesis_lib.monitored_service)
   - Provides monitoring, topology publishing, and eventing for functions
   - Ensures exported tools are visible in the graph and traced via events

3) MCP Client Integration
   - Uses `mcp.client.streamable_http.streamablehttp_client` and `mcp.ClientSession`
   - Discovers available tools via `list_tools()`

=================================================================================================
CURRENT RUNTIME USAGE - Typical Flow
=================================================================================================

1) connect_to_mcp_server(server_url)
   - Open streamable HTTP connection and create ClientSession
   - Initialize session; list tools; generate/bind decorated methods for each tool
   - Create a monitored service instance to host exported functions

2) _advertise_functions()
   - Delegate to monitored service to publish function advertisements

3) run()
   - Delegate to monitored service to start handling requests

Call Chain (simplified):
```
connect_to_mcp_server → list_tools → add_tool_method (per tool)
                      → create MonitoredService instance with bound functions
                      → advertise → run
```

=================================================================================================
STATUS & TODO - Implemented vs Future Enhancements
=================================================================================================

Implemented:
- Dynamic function generation for MCP tools
- Monitoring integration via MonitoredService
- Discovery/advertising via FunctionRegistry

TODO (not blocking current usage):
- Input validation & type coercion for tool parameters (based on schemas)
- Standardize return format for tools (e.g., {"message": str, "status": int})
- Streaming/tool output variants (non-text content, multiple parts)
- Timeouts, retries, and richer error classification
- Secure auth/session management for MCP servers

=================================================================================================
EXTENSION POINTS - How to Customize
=================================================================================================

1) Override add_tool_method() to customize codegen behavior and return shapes
2) Provide a custom MonitoredService subclass (if you need additional hooks)
3) Wrap/transform tool schemas before generation to enforce typing policies

=================================================================================================
DESIGN RATIONALE - Why Dynamic Generation
=================================================================================================

Dynamic code generation avoids hand-writing wrappers for each tool and ensures
new tools appear automatically after `list_tools()`. Decorating with
`@genesis_function` integrates discovery and monitoring with minimal glue code.
"""

import logging
import textwrap
from genesis_lib.monitored_service import MonitoredService
from genesis_lib.function_discovery import InternalFunctionRegistry
from genesis_lib.decorators import genesis_function
from typing import List, Optional

from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client  



# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enhanced_service_base")

class MCPServiceBase():
    """
    Base class that connects to an MCP server and exposes its tools as Genesis
    functions on a monitored service.

    Responsibilities:
    - Manage MCP session lifecycle (connect, initialize, list tools)
    - Generate and bind `@genesis_function` methods for each tool
    - Delegate advertise/run to a dynamic MonitoredService subclass instance

    Call Sequence:
    - connect_to_mcp_server() → generate functions → create monitored service instance
    - _advertise_functions() → advertise
    - run() → serve requests
    """

    def __init__(self, service_name: str, capabilities: List[str], participant=None, domain_id=0, registry: InternalFunctionRegistry = None):
        """
        Initialize the MCP service with a name and capabilities.
        
        Args:
            service_name: Name of the service
            capabilities: List of capabilities provided by the service
            participant: Optional participant information
            domain_id: Domain ID for the service
            registry: Function registry for managing functions
        """
        self.my_enhanced_service_MCP_Class = type(
            f"{service_name}_my_enhanced_service_MCP_Class",
            (MonitoredService,),
            {
                "__doc__": "A dynamic subclass of EnhancedServiceBase.",
            }
        )
        self.my_enhanced_service_MCP_Instance = None
        self.service_name = service_name
        self.capabilities = capabilities
        self.participant = participant
        self.domain_id = domain_id
        self.registry = registry or InternalFunctionRegistry()
        self.mcp_session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
    def _advertise_functions(self):
        """
        Advertise the available functions to the Genesis network.
        
        This method makes the functions discoverable by other services.
        """
        logger.info("Advertising functions")
        if self.my_enhanced_service_MCP_Instance:
            self.my_enhanced_service_MCP_Instance._advertise_functions()
        else:
            logger.error("MCP service instance is not initialized. Cannot advertise functions.")

    async def run(self):
        """
        Run the MCP service.
        
        This method sets up the service and starts listening for requests.
        """
        if self.my_enhanced_service_MCP_Instance:
            await self.my_enhanced_service_MCP_Instance.run()
        else:
            logger.error("MCP service instance is not initialized. Cannot run the service.")

    async def connect_to_mcp_server(self, server_url: str):
        """
        Connect to the MCP server, discover tools, and generate exported functions.

        Steps:
        1. Open streamable HTTP connection and create ClientSession
        2. Initialize session and list available tools
        3. For each tool, generate a coroutine method decorated with @genesis_function
        4. Create a monitored service instance to host the exported functions

        TODO: Add timeouts/retries and richer error handling (classification).
        TODO: Support non-text/streaming tool results and standardized return shapes.
        """
        logger.info("Connecting to MCP server")
        read_stream, write_stream, _ = await self.exit_stack.enter_async_context(streamablehttp_client(server_url))
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        logger.info("Connected to MCP server")
        await self.mcp_session.initialize()
        # List available tools on the server
        response = await self.mcp_session.list_tools()
        for tool in response.tools:
            self.add_tool_method(tool)
            logger.info(f"Tool: {tool}")
        logger.info(f"list_tools() response: {response}")
        tools = response.tools
        logger.info(f"Available tools: {tools}")
        self.my_enhanced_service_MCP_Instance = self.my_enhanced_service_MCP_Class(
            self.service_name,
            capabilities=self.capabilities,
            participant=self.participant,
            domain_id=self.domain_id,
            registry=self.registry
        )
        self.my_enhanced_service_MCP_Instance.mcp_session = self.mcp_session

        

    def add_tool_method(self, tool):
        """
        Dynamically generate and bind a `@genesis_function` method for an MCP tool.

        Behavior:
        - Builds a coroutine with a signature derived from the tool's input schema
        - Calls `self.mcp_session.call_tool(tool.name, tool_args)`
        - Returns the first text element of the MCP response (exact return type: str)

        TODO: Validate and coerce parameter types per schema; handle required/optional.
        TODO: Consider a standardized return format (e.g., {"message": str, "status": int}).
        """
        # Extract parameter names and types from the tool's inputSchema
        params = tool.inputSchema["properties"]
        required = tool.inputSchema.get("required", [])
        param_list = []
        doc_params = []
        for name, prop in params.items():
            typ = "float" if prop.get("type") == "number" else "str"
            param_list.append(f"{name}: {typ}")
            doc_params.append(f"    {name}: {prop.get('title', name)} ({typ})")
        param_sig = ", ".join(param_list)
        param_names = ", ".join(params.keys())

        # Build the function source code as a string
        func_src = f"""
@genesis_function()
async def {tool.name}(self, {param_sig}, request_info=None) -> str:
    \"\"\"{tool.description}
    Args:
{chr(10).join(doc_params)}
        request_info: Optional request metadata
    Returns:
        str: first text item from MCP tool result (exact)
    \"\"\"
    try:
        tool_args = {{{', '.join([f"'{k}': {k}" for k in params.keys()])}}}
        result = await self.mcp_session.call_tool('{tool.name}', tool_args)
        return result.content[0].text
    except Exception as e:
        logger.error(f"Error in {tool.name} operation: {{str(e)}}")
        raise
"""
        func_src = textwrap.dedent(func_src)
        # Prepare a namespace for exec
        ns = dict(genesis_function=genesis_function, logger=logger)
        exec(func_src, ns)
        func = ns[tool.name]
        # Bind the function to the instance
        setattr(self.my_enhanced_service_MCP_Class, tool.name, func)
    



    
   