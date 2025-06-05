#!/usr/bin/env python3
"""
GENESIS MCP Service Base

This module provides an extension to the EnhancedServiceBase, adding basic functionality 
to export any MCP tool offered by an MCP server using streamale http as a 
genesis_function. The result is that any MCP tool can be used as a genesis function,
allowing for easy integration with the GENESIS framework.

This means that any MCP tool offered via an extension of this class will:
- have function registration and discovery
- come with Monitoring event publication
- have error handling
- have resource management
"""

import logging
import textwrap
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.function_discovery import FunctionRegistry
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
    Base class for MCP services
    """

    def __init__(self, service_name: str, capabilities: List[str], participant=None, domain_id=0, registry: FunctionRegistry = None):
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
            (EnhancedServiceBase,),
            {
                "__doc__": "A dynamic subclass of EnhancedServiceBase.",
            }
        )
        self.my_enhanced_service_MCP_Instance = None
        self.service_name = service_name
        self.capabilities = capabilities
        self.participant = participant
        self.domain_id = domain_id
        self.registry = registry or FunctionRegistry()
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
        Connect to the MCP server and process all the tools.

        This method establishes a connection to the MCP server,
        sets up communication channels, and registers available tools.
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
async def {tool.name}(self, {param_sig}, request_info=None) -> dict:
    \"\"\"{tool.description}
    Args:
{chr(10).join(doc_params)}
        request_info: Optional request metadata
    Returns:
        dict: result from MCP call
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
    



    
   