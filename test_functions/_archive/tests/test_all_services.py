#!/usr/bin/env python3

import asyncio
import logging
import json
import time
import sys
import os
import random
from typing import Dict, Any, List

# Import the generic function client from genesis_lib
from genesis_lib.generic_function_client import GenericFunctionClient

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set default level to WARNING to reduce verbosity
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_all_services")
logger.setLevel(logging.INFO)  # Keep INFO level for test progress and results

class AllServicesTest:
    """Test class for testing all Genesis services together"""
    
    def __init__(self):
        """Initialize the test class"""
        logger.info("Initializing test for all services")
        self.client = GenericFunctionClient()
        self.test_results = []
    
    async def discover_functions(self):
        """Discover all available functions"""
        logger.info("Discovering functions...")
        await self.client.discover_functions(timeout_seconds=15)
        functions = self.client.list_available_functions()
        
        # Group functions by service
        services = {}
        for func in functions:
            service_name = func.get("service_name", "UnknownService")
            if service_name not in services:
                services[service_name] = []
            services[service_name].append(func)
        
        # Print discovered functions by service
        logger.info(f"Discovered {len(functions)} functions across {len(services)} services")
        for service_name, funcs in services.items():
            logger.info(f"Service: {service_name} - {len(funcs)} functions")
            for func in funcs:
                logger.info(f"  - {func['name']}: {func['description']}")
        
        return functions
    
    async def test_calculator_service(self):
        """Test the calculator service"""
        logger.info("===== Testing Calculator Service =====")
        
        # Test add function
        try:
            logger.info("Testing add function...")
            result = await self.client.call_function_by_name("add", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "add",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing add function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "add",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test subtract function
        try:
            logger.info("Testing subtract function...")
            result = await self.client.call_function_by_name("subtract", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "subtract",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing subtract function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "subtract",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test multiply function
        try:
            logger.info("Testing multiply function...")
            result = await self.client.call_function_by_name("multiply", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "multiply",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing multiply function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "multiply",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test divide function
        try:
            logger.info("Testing divide function...")
            result = await self.client.call_function_by_name("divide", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "divide",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing divide function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "divide",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
    
    async def test_calculator_performance(self):
        """Test calculator service performance and accuracy with rapid requests"""
        logger.info("===== Testing Calculator Service Performance =====")
        
        operations = ["add", "subtract", "multiply", "divide"]
        total_tests = 100
        successful_tests = 0
        total_time = 0
        
        logger.info(f"Running {total_tests} rapid calculator operations...")
        
        for i in range(total_tests):
            # Generate random numbers (avoiding 0 for division)
            x = random.uniform(1, 100)
            y = random.uniform(1, 100)
            
            # Select random operation
            operation = random.choice(operations)
            
            # Calculate expected result locally
            if operation == "add":
                expected = x + y
            elif operation == "subtract":
                expected = x - y
            elif operation == "multiply":
                expected = x * y
            else:  # divide
                expected = x / y
            
            try:
                start_time = time.time()
                result_dict = await self.client.call_function_by_name(operation, x=x, y=y)
                end_time = time.time()
                
                # Calculate request time
                request_time = end_time - start_time
                total_time += request_time
                
                # Extract the numeric result from the dictionary response
                if isinstance(result_dict, dict):
                    result = result_dict.get('result', None)
                    if result is None:
                        logger.error(f"Test {i+1}: No 'result' field in response: {result_dict}")
                        continue
                else:
                    result = result_dict  # In case the service returns the number directly
                
                # Verify result (using small epsilon for floating point comparison)
                if abs(float(result) - expected) < 1e-10:
                    successful_tests += 1
                else:
                    logger.error(f"Test {i+1}: Result mismatch for {operation}({x}, {y})")
                    logger.error(f"Expected: {expected}, Got: {result}")
                    logger.error(f"Full response: {result_dict}")
                
                # Log progress every 10 tests
                if (i + 1) % 10 == 0:
                    logger.info(f"Completed {i+1}/{total_tests} tests. Current success rate: {(successful_tests/(i+1))*100:.2f}%")
                
                # Minimal delay to prevent overwhelming the service
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in test {i+1}: {str(e)}")
                logger.error(f"Operation: {operation}, x={x}, y={y}")
                self.test_results.append({
                    "service": "CalculatorService",
                    "function": operation,
                    "args": {"x": x, "y": y},
                    "error": str(e),
                    "success": False
                })
        
        # Log performance metrics
        avg_time = total_time / total_tests
        success_rate = (successful_tests / total_tests) * 100
        
        logger.info("===== Performance Test Results =====")
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful tests: {successful_tests}")
        logger.info(f"Success rate: {success_rate:.2f}%")
        logger.info(f"Total time: {total_time:.2f} seconds")
        logger.info(f"Average request time: {avg_time:.4f} seconds")
        
        self.test_results.append({
            "service": "CalculatorService",
            "function": "performance_test",
            "metrics": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": success_rate,
                "total_time": total_time,
                "average_request_time": avg_time
            },
            "success": successful_tests == total_tests
        })
    
    async def test_letter_counter_service(self):
        """Test the letter counter service"""
        logger.info("===== Testing Letter Counter Service =====")
        
        # Test count_letter function
        try:
            logger.info("Testing count_letter function...")
            result = await self.client.call_function_by_name("count_letter", text="lollapalooza", letter="l")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_letter",
                "args": {"text": "lollapalooza", "letter": "l"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing count_letter function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_letter",
                "args": {"text": "lollapalooza", "letter": "l"},
                "error": str(e),
                "success": False
            })
        
        # Test count_multiple_letters function
        try:
            logger.info("Testing count_multiple_letters function...")
            result = await self.client.call_function_by_name("count_multiple_letters", text="mississippi", letters=["m", "i", "s", "p"])
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_multiple_letters",
                "args": {"text": "mississippi", "letters": ["m", "i", "s", "p"]},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing count_multiple_letters function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_multiple_letters",
                "args": {"text": "mississippi", "letters": ["m", "i", "s", "p"]},
                "error": str(e),
                "success": False
            })
        
        # Test get_letter_frequency function
        try:
            logger.info("Testing get_letter_frequency function...")
            result = await self.client.call_function_by_name("get_letter_frequency", text="mississippi")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "get_letter_frequency",
                "args": {"text": "mississippi"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing get_letter_frequency function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "get_letter_frequency",
                "args": {"text": "mississippi"},
                "error": str(e),
                "success": False
            })
    
    async def test_text_processor_service(self):
        """Test the text processor service"""
        logger.info("===== Testing Text Processor Service =====")
        
        # Test transform_case function
        try:
            logger.info("Testing transform_case function...")
            result = await self.client.call_function_by_name("transform_case", text="Hello World", case="upper")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "transform_case",
                "args": {"text": "Hello World", "case": "upper"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing transform_case function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "transform_case",
                "args": {"text": "Hello World", "case": "upper"},
                "error": str(e),
                "success": False
            })
        
        # Test analyze_text function
        try:
            logger.info("Testing analyze_text function...")
            result = await self.client.call_function_by_name("analyze_text", text="The quick brown fox jumps over the lazy dog.")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "analyze_text",
                "args": {"text": "The quick brown fox jumps over the lazy dog."},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing analyze_text function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "analyze_text",
                "args": {"text": "The quick brown fox jumps over the lazy dog."},
                "error": str(e),
                "success": False
            })
        
        # Test generate_text function
        try:
            logger.info("Testing generate_text function...")
            result = await self.client.call_function_by_name("generate_text", text="Hello", operation="repeat", count=3)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "generate_text",
                "args": {"text": "Hello", "operation": "repeat", "count": 3},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing generate_text function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "generate_text",
                "args": {"text": "Hello", "operation": "repeat", "count": 3},
                "error": str(e),
                "success": False
            })
    
    def print_results(self):
        """Print the test results"""
        logger.info("===== Test Results =====")
        
        # Group results by service
        services = {}
        for result in self.test_results:
            service_name = result.get("service", "UnknownService")
            if service_name not in services:
                services[service_name] = {"total": 0, "success": 0, "failure": 0}
            
            services[service_name]["total"] += 1
            if result.get("success", False):
                services[service_name]["success"] += 1
            else:
                services[service_name]["failure"] += 1
        
        # Print results by service
        total_tests = len(self.test_results)
        total_success = sum(1 for result in self.test_results if result.get("success", False))
        total_failure = total_tests - total_success
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful tests: {total_success}")
        logger.info(f"Failed tests: {total_failure}")
        logger.info(f"Success rate: {total_success / total_tests * 100:.2f}%")
        
        for service_name, stats in services.items():
            logger.info(f"Service: {service_name}")
            logger.info(f"  Total tests: {stats['total']}")
            logger.info(f"  Successful tests: {stats['success']}")
            logger.info(f"  Failed tests: {stats['failure']}")
            logger.info(f"  Success rate: {stats['success'] / stats['total'] * 100:.2f}%")
        
        # Print failed tests
        if total_failure > 0:
            logger.info("Failed tests:")
            for result in self.test_results:
                if not result.get("success", False):
                    logger.info(f"  Service: {result.get('service', 'UnknownService')}")
                    logger.info(f"  Function: {result.get('function', 'UnknownFunction')}")
                    logger.info(f"  Args: {result.get('args', {})}")
                    logger.info(f"  Error: {result.get('error', 'Unknown error')}")
                    logger.info("")
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Running all tests...")
        
        # Discover functions
        await self.discover_functions()
        
        # Add call_function_by_name method to the client
        self.client.call_function_by_name = self._call_function_by_name
        
        # Run tests for each service
        await self.test_calculator_service()
        await self.test_calculator_performance()
        await self.test_letter_counter_service()
        await self.test_text_processor_service()
        
        # Print results
        self.print_results()
    
    async def _call_function_by_name(self, function_name, **kwargs):
        """
        Call a function by name.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
        """
        # Find the function ID by name
        function_id = None
        for func in self.client.list_available_functions():
            if func["name"] == function_name:
                function_id = func["function_id"]
                break
        
        if not function_id:
            raise ValueError(f"Function not found: {function_name}")
        
        # Call the function
        return await self.client.call_function(function_id, **kwargs)
    
    def close(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        self.client.close()

async def main():
    """Main entry point"""
    logger.info("Starting test for all services")
    test = None
    try:
        # Create and run the test
        test = AllServicesTest()
        await test.run_all_tests()
        
        # Check if any tests failed
        if test.test_results and any(not result.get('success', False) for result in test.test_results):
            logger.error("Some tests failed - see above for details")
            return 1
            
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return 1
    finally:
        # Clean up
        if test:
            test.close()

if __name__ == "__main__":
    # Run the main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 