# Quick Start

## Prerequisites

Before setting up Genesis LIB, ensure you have:

1. **Python 3.10**
2. **RTI Connext DDS 7.3.0 or greater**
    - make sure to have the license file
    - set this in your environment:
    ```bash
    export NDDSHOME=/path/to/rti_connext_dds-7.3.0/
    ```
3. **API Keys**
   - OpenAI API Key (for GPT models)
   - Anthropic API Key (for Claude models)
   - Set (at least one of) these in your environment :
     ```bash
     export OPENAI_API_KEY="your_openai_api_key"
     export ANTHROPIC_API_KEY="your_anthropic_api_key"
     ```

## Install Genesis

Create virtual env

```
mkdir hellogenesis
cd hellogenesis
python3.10 -m venv venv
source venv/bin/activate
```

Get Genesis (and its dependencies)

```
pip install  git+https://github.com/sploithunter/Genesis_LIB@main
```

## Create a simple interactive agent (based on openai)

Create a file called `interactive.py` with this content:

```py
#!/usr/bin/env python3

"""
HelloWorldAgent - A simple example of a Genesis agent that uses OpenAI capabilities
to interact with a calculator service.
"""

import logging
import asyncio
import sys
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_world_agent")

class HelloWorldAgent(OpenAIGenesisAgent):
    """A simple agent that can use the calculator service."""
    
    def __init__(self):
        """Initialize the HelloWorldAgent."""
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="HelloWorldAgent",
            description="A simple agent that can perform basic arithmetic operations",
            enable_tracing=True
        )
        logger.info("HelloWorldAgent initialized")

async def main():
    """Run the HelloWorldAgent with interactive question handling."""
    try:
        # Create and start agent
        agent = HelloWorldAgent()
        logger.info("Agent started successfully")
        
        # Give some time for initialization
        await asyncio.sleep(2)
        
        print("Hello! You can ask me questions. Type 'exit' to quit.")
        
        while True:
            # Prompt user for input
            message = input("Your question: ")
            
            # Exit if the user types 'exit'
            if message.lower() == "exit":
                print("Goodbye!")
                break
            
            # Process the message
            try:
                response = await agent.process_message(message)
                print(f"Agent response: {response}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                print("An error occurred. Please try again.")
        
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```


Run it:

```
python interactive.py
```

You should get a prompt 

```
Your question:
```

Ask your questions. 

### MCP
If you want your agent to be MCP enabled you can do it this way:

```py
agent.enable_mcp(8000)
```

You will need ``threading`` and ``fastmcp``


## Add a service. 
In another shell add a new file called `calc_service.py`

```py
#!/usr/bin/env python3

"""
A simple calculator service that demonstrates basic Genesis service functionality.
Provides basic arithmetic operations: add and multiply.
"""

import logging
import asyncio
from typing import Dict, Any
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

# Configure logging to show INFO level messages
# This helps with debugging and monitoring service operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_calculator")

class HelloCalculator(EnhancedServiceBase):
    """A simple calculator service demonstrating Genesis functionality."""
    
    def __init__(self):
        """Initialize the calculator service."""
        # Initialize the base service with a name and capabilities
        # The capabilities list helps other services discover what this service can do
        super().__init__(
            "HelloCalculator",
            capabilities=["calculator", "math"]
        )
        logger.info("HelloCalculator service initialized")
        # Advertise the available functions to the Genesis network
        # This makes the functions discoverable by other services
        self._advertise_functions()
        logger.info("Functions advertised")

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number to add
            y: Second number to add
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the addition
            
        Examples:
            >>> await add(5, 3)
            {'result': 8}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received add request: x={x}, y={y}")
        
        try:
            # Perform the addition operation
            result = x + y
            # Log the result for debugging
            logger.info(f"Add result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in add operation: {str(e)}")
            raise

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x: First number to multiply
            y: Second number to multiply
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the multiplication
            
        Examples:
            >>> await multiply(5, 3)
            {'result': 15}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received multiply request: x={x}, y={y}")
        
        try:
            # Perform the multiplication operation
            result = x * y
            # Log the result for debugging
            logger.info(f"Multiply result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in multiply operation: {str(e)}")
            raise

def main():
    """Run the calculator service."""
    # Initialize and start the service
    logger.info("Starting HelloCalculator service")
    try:
        # Create an instance of the calculator service
        service = HelloCalculator()
        # Run the service using asyncio
        asyncio.run(service.run())
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("Shutting down HelloCalculator service")

if __name__ == "__main__":
    main() 
```

Now services are discovered by original agent and you can ask to do simple math and it will call the service
