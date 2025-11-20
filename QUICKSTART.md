# Quick Start

## Prerequisites

Before setting up Genesis LIB, ensure you have:

1. **Python 3.10**
2. **RTI Connext DDS 7.3.0 or greater**
    - Make sure to have the license file
    - Set this in your environment:
    ```bash
    export NDDSHOME=/path/to/rti_connext_dds-7.3.0/
    ```
3. **API Keys**
   - OpenAI API Key (for GPT models)
   - Anthropic API Key (for Claude models)
   - Set (at least one of) these in your environment:
     ```bash
     export OPENAI_API_KEY="your_openai_api_key"
     export ANTHROPIC_API_KEY="your_anthropic_api_key"
     ```

## Install Genesis

### Option 1: Install from Local Source

If you have the Genesis_LIB repository cloned or downloaded locally:

```bash
cd /path/to/Genesis_rc1/Genesis_LIB
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
```

Verify installation:
```bash
python -c "import genesis_lib; print('Genesis installed:', genesis_lib.__file__)"
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

### Optional: Enable MCP (Model Context Protocol)

If you want your agent to be MCP enabled, add this after creating the agent:

```py
import threading

# In your main() function, after creating the agent:
agent.enable_mcp(8000)
```

**Note:** MCP support requires the `mcp` package (included in Genesis dependencies)


## Add a Service

In another shell, create a new file called `calc_service.py`:

```py
#!/usr/bin/env python3

"""
A simple calculator service that demonstrates basic Genesis service functionality.
Provides basic arithmetic operations: add and multiply.
"""

import logging
import asyncio
import os
from typing import Dict, Any
from genesis_lib.monitored_service import MonitoredService
from genesis_lib.decorators import genesis_function

# Configure logging to show INFO level messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_calculator")

class HelloCalculator(MonitoredService):
    """A simple calculator service demonstrating Genesis functionality."""
    
    def __init__(self, domain_id=0):
        """Initialize the calculator service.
        
        Args:
            domain_id: DDS domain ID for network isolation (default: 0)
        """
        # Initialize the base service with a name and capabilities
        # The capabilities list helps other services discover what this service can do
        super().__init__(
            "HelloCalculator",
            capabilities=["calculator", "math"],
            domain_id=domain_id
        )
        logger.info(f"HelloCalculator service initialized on domain {domain_id}")
        
        # Advertise the available functions to the Genesis network
        # This makes the functions discoverable by other services
        self._advertise_functions()
        logger.info("Functions advertised")

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
        logger.info(f"Received add request: x={x}, y={y}")
        
        try:
            result = x + y
            logger.info(f"Add result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in add operation: {str(e)}")
            raise

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
        logger.info(f"Received multiply request: x={x}, y={y}")
        
        try:
            result = x * y
            logger.info(f"Multiply result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in multiply operation: {str(e)}")
            raise

def main():
    """Run the calculator service."""
    # Support domain isolation via GENESIS_DOMAIN_ID environment variable
    domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    logger.info(f"Starting HelloCalculator service on domain {domain_id}")
    try:
        service = HelloCalculator(domain_id=domain_id)
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Shutting down HelloCalculator service")

if __name__ == "__main__":
    main() 
```

Run the service in a separate terminal (keep your agent running):

```bash
python calc_service.py
```

Now services are discovered by the original agent and you can ask it to do simple math - it will call the service automatically!

## Advanced Features

### Domain Isolation
Run agents and services on different DDS domains for network isolation:
```bash
export GENESIS_DOMAIN_ID=5
python interactive.py
```

### Enable Debugging
Enable detailed tracing in your agent:
```py
agent = HelloWorldAgent()
agent.enable_tracing = True  # Or pass enable_tracing=True to __init__
```

### Monitoring & Visualization
Genesis includes built-in monitoring and graph visualization:
```bash
# Terminal 1: Run the graph viewer
genesis-graph-viewer

# Terminal 2: Run your agents/services
# Their topology will appear in the viewer at http://localhost:5000
```

## Next Steps

- **More Examples**: Check the `examples/` directory for advanced patterns
- **Multi-Agent Systems**: See `examples/MultiAgent/` for agent-to-agent communication
- **Full Testing**: Run the test suite with `cd tests && ./run_all_tests_parallel.sh`
- **Architecture Docs**: Read `docs/architecture/` for implementation details
- **User Guides**: See `docs/user-guides/` for detailed guides
- **Provider Guide**: See `docs/architecture/NEW_PROVIDER_GUIDE.md` to add support for new LLM providers
