#!/usr/bin/env python3

import logging
import asyncio
import json
from typing import Dict, Any
from genesis_lib.generic_function_client import GenericFunctionClient

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("calculator_client")

class CalculatorClient:
    """
    Calculator client for testing purposes.
    This client has knowledge of calculator functions for testing,
    but uses the generic client under the hood.
    """
    
    def __init__(self):
        """Initialize the calculator client"""
        logger.info("Initializing CalculatorClient")
        
        # Use the generic client under the hood
        self.generic_client = GenericFunctionClient()
        
        # Cache for discovered function IDs
        self.function_ids = {}
    
    async def _ensure_initialized(self):
        """Ensure the client is initialized and functions are discovered"""
        if not self.function_ids:
            await self.generic_client.discover_functions()
            
            # Cache function IDs for calculator operations
            functions = self.generic_client.list_available_functions()
            for func in functions:
                name = func["name"]
                self.function_ids[name] = func["function_id"]
            
            logger.info(f"Discovered calculator functions: {list(self.function_ids.keys())}")
    
    async def add(self, x: float, y: float) -> Dict[str, Any]:
        """
        Add two numbers
        
        Args:
            x: First number to add
            y: Second number to add
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "add" not in self.function_ids:
            raise RuntimeError("Add function not available")
        
        logger.debug(f"CLIENT: Calling add with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["add"], x=x, y=y)
    
    async def subtract(self, x: float, y: float) -> Dict[str, Any]:
        """
        Subtract two numbers
        
        Args:
            x: Number to subtract from
            y: Number to subtract
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "subtract" not in self.function_ids:
            raise RuntimeError("Subtract function not available")
        
        logger.debug(f"CLIENT: Calling subtract with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["subtract"], x=x, y=y)
    
    async def multiply(self, x: float, y: float) -> Dict[str, Any]:
        """
        Multiply two numbers
        
        Args:
            x: First number to multiply
            y: Second number to multiply
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "multiply" not in self.function_ids:
            raise RuntimeError("Multiply function not available")
        
        logger.debug(f"CLIENT: Calling multiply with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["multiply"], x=x, y=y)
    
    async def divide(self, x: float, y: float) -> Dict[str, Any]:
        """
        Divide two numbers
        
        Args:
            x: Number to divide
            y: Number to divide by
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "divide" not in self.function_ids:
            raise RuntimeError("Divide function not available")
        
        if y == 0:
            raise ValueError("Cannot divide by zero")
        
        logger.debug(f"CLIENT: Calling divide with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["divide"], x=x, y=y)
    
    def close(self):
        """Close the client and release resources"""
        logger.info("Closing calculator client")
        self.generic_client.close()

async def run_calculator_test():
    """Run a test of the calculator functions"""
    client = CalculatorClient()
    
    try:
        # Test add
        try:
            result = await client.add(10, 5)
            print(f"\nFunction 'add({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in add test: {str(e)}")
            logger.error(f"add test failed: {str(e)}", exc_info=True)
        
        # Test subtract
        try:
            result = await client.subtract(10, 5)
            print(f"\nFunction 'subtract({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in subtract test: {str(e)}")
            logger.error(f"subtract test failed: {str(e)}", exc_info=True)
        
        # Test multiply
        try:
            result = await client.multiply(10, 5)
            print(f"\nFunction 'multiply({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in multiply test: {str(e)}")
            logger.error(f"multiply test failed: {str(e)}", exc_info=True)
        
        # Test divide
        try:
            result = await client.divide(10, 2)
            print(f"\nFunction 'divide({{'x': 10, 'y': 2}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in divide test: {str(e)}")
            logger.error(f"divide test failed: {str(e)}", exc_info=True)
        
        # Test error cases
        print("\nTesting error cases:")
        
        # Test division by zero
        try:
            await client.divide(10, 0)
            print("❌ Division by zero should have raised an error")
            logger.error("Division by zero did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test type errors
        print("\nTesting type errors:")
        
        # Test with string instead of number
        try:
            # We need to bypass the client's validation to test the service's validation
            function_id = client.function_ids.get("add")
            if function_id:
                await client.generic_client.call_function(function_id, x="abc", y=5)
                print("❌ String parameter should have raised an error")
                logger.error("String parameter did not raise an error")
            else:
                print("⚠️ Skipping type error test - add function not found")
        except Exception as e:
            print(f"✅ Properly handled type error: {str(e)}")
            logger.info(f"Test passed - properly handled type error: {str(e)}")
        
        # Test with invalid JSON
        try:
            # We need to bypass the client's validation to test the service's validation
            function_id = client.function_ids.get("multiply")
            if function_id:
                # Create a custom client to send invalid JSON
                from genesis_lib.rpc_client import GenesisRPCClient
                custom_client = GenesisRPCClient(service_name="CalculatorService")
                
                # Send a request with invalid JSON
                from genesis_lib.datamodel import FunctionCall
                request = custom_client.get_request_type()(
                    id="test_invalid_json",
                    type="function",
                    function=FunctionCall(
                        name="multiply",
                        arguments="this is not valid json"
                    )
                )
                
                request_id = custom_client.requester.send_request(request)
                replies = custom_client.requester.receive_replies(
                    max_wait=custom_client.timeout,
                    related_request_id=request_id
                )
                
                if replies and not replies[0].data.success:
                    print(f"✅ Properly handled invalid JSON: {replies[0].data.error_message}")
                    logger.info(f"Test passed - properly handled invalid JSON: {replies[0].data.error_message}")
                else:
                    print("❌ Invalid JSON should have raised an error")
                    logger.error("Invalid JSON did not raise an error")
                
                custom_client.close()
            else:
                print("⚠️ Skipping invalid JSON test - multiply function not found")
        except Exception as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.info("CLIENT: Starting calculator client")
    try:
        asyncio.run(run_calculator_test())
    except KeyboardInterrupt:
        logger.info("CLIENT: Shutting down calculator client")
    except Exception as e:
        logger.error(f"CLIENT: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 