#!/usr/bin/env python3

import logging
import asyncio
from genesis_lib.rpc_client import GenesisRPCClient
from typing import Dict, Any, List
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_client")

class TextProcessorClient(GenesisRPCClient):
    """Client for the text processor service"""
    
    def __init__(self):
        """Initialize the text processor client"""
        super().__init__(service_name="TextProcessorService")
        logger.info("Initializing TextProcessorClient")
        
        # Add text processor specific validation patterns
        self.validation_patterns.update({
            "text": {
                "min_length": 1,
                "max_length": None,  # No maximum length limit
                "pattern": None  # No pattern restriction
            },
            "case": {
                "type": "enum",
                "values": ["upper", "lower", "title"]
            },
            "operation": {
                "type": "enum",
                "values": ["repeat", "pad"]
            },
            "count": {
                "type": "number",
                "minimum": 0,
                "maximum": 1000
            }
        })
    
    async def wait_for_service(self):
        """Wait for the service to be discovered and log available functions"""
        logger.info("Waiting for TextProcessorService to be discovered...")
        await super().wait_for_service()
        
        # Log discovered functions
        logger.info("Service discovered! Checking available functions...")
        try:
            # Try to call each expected function with minimal valid parameters
            expected_functions = {
                "transform_case": {"text": "test", "case": "upper"},
                "analyze_text": {"text": "test"},
                "generate_text": {"text": "test", "operation": "repeat", "count": 1},
                "count_words": {"text": "test"}
            }
            
            for func, params in expected_functions.items():
                try:
                    logger.info(f"Checking function: {func}")
                    # Try a quick call with minimal parameters
                    await self.call_function(func, **params)
                    logger.info(f"✓ Function {func} is available")
                except Exception as e:
                    logger.warning(f"✗ Function {func} is NOT available: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking functions: {str(e)}")
        
        logger.info("Service discovered successfully!")
    
    def validate_enum_value(self, value: str, pattern_type: str) -> None:
        """
        Validate that a value is one of the allowed enum values
        
        Args:
            value: Value to validate
            pattern_type: Type of pattern to use (e.g., 'case', 'operation')
            
        Raises:
            ValueError: If validation fails
        """
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        if pattern.get("type") != "enum":
            raise ValueError(f"Pattern type {pattern_type} is not an enum")
            
        if value not in pattern["values"]:
            raise ValueError(f"Value must be one of: {', '.join(pattern['values'])}")
    
    async def transform_case(self, text: str, case: str) -> Dict[str, Any]:
        """
        Transform text to specified case
        
        Args:
            text: Text to transform
            case: Target case (upper, lower, or title)
            
        Returns:
            Dictionary containing input parameters and transformed result
            
        Raises:
            ValueError: If text is empty or case is not supported
        """
        logger.debug(f"CLIENT: Calling transform_case with text='{text}', case='{case}'")
        
        # Validate inputs
        self.validate_text(text)
        self.validate_enum_value(case, pattern_type="case")
        
        return await self.call_function_with_validation("transform_case", text=text, case=case)
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze text and return detailed statistics
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary containing input parameters and various statistics including:
            - total_length: Total number of characters
            - alpha_count: Number of alphabetic characters
            - digit_count: Number of numeric digits
            - space_count: Number of whitespace characters
            - punctuation_count: Number of punctuation marks
            - word_count: Number of words
            - line_count: Number of lines
            - uppercase_count: Number of uppercase letters
            - lowercase_count: Number of lowercase letters
            
        Raises:
            ValueError: If text is empty
        """
        logger.debug(f"CLIENT: Calling analyze_text with text='{text}'")
        
        # Validate input
        self.validate_text(text)
        
        return await self.call_function_with_validation("analyze_text", text=text)
    
    async def generate_text(self, text: str, operation: str, count: int) -> Dict[str, Any]:
        """
        Generate text based on input text and specified operation
        
        Args:
            text: Base text for generation
            operation: Operation to perform (repeat or pad)
            count: Number of repetitions or padding length (0-1000)
            
        Returns:
            Dictionary containing:
            - text: Original input text
            - operation: Operation performed
            - count: Count parameter used
            - result: Generated text
            - result_length: Length of generated text
            
        Raises:
            ValueError: If text is empty, operation is invalid, or count is out of range
        """
        logger.debug(f"CLIENT: Calling generate_text with text='{text}', operation='{operation}', count={count}")
        
        # Validate inputs
        self.validate_text(text)
        self.validate_enum_value(operation, pattern_type="operation")
        self.validate_numeric(count, pattern_type="count")
        
        return await self.call_function_with_validation("generate_text", text=text, operation=operation, count=count)

async def run_text_processor_test():
    """Run a test of the text processor functions"""
    client = TextProcessorClient()
    
    try:
        # Wait for service discovery
        logger.info("Starting service discovery...")
        await client.wait_for_service()
        
        test_text = "Hello, World! 123"
        
        # Test transform_case
        try:
            logger.info("Testing transform_case function...")
            result = await client.transform_case(test_text, "upper")
            print(f"\nFunction 'transform_case({{'text': '{test_text}', 'case': 'upper'}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in transform_case test: {str(e)}")
            logger.error(f"transform_case test failed: {str(e)}", exc_info=True)
        
        # Test analyze_text
        try:
            logger.info("Testing analyze_text function...")
            result = await client.analyze_text(test_text)
            print(f"\nFunction 'analyze_text({{'text': '{test_text}'}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in analyze_text test: {str(e)}")
            logger.error(f"analyze_text test failed: {str(e)}", exc_info=True)
        
        # Test generate_text
        try:
            logger.info("Testing generate_text function...")
            result = await client.generate_text(test_text, "repeat", 2)
            print(f"\nFunction 'generate_text({{'text': '{test_text}', 'operation': 'repeat', 'count': 2}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in generate_text test: {str(e)}")
            logger.error(f"generate_text test failed: {str(e)}", exc_info=True)
        
        # Test error cases
        print("\nTesting error cases:")
        
        # Test empty text
        try:
            logger.info("Testing empty text error case...")
            await client.transform_case("", "upper")
            print("❌ Empty text should have raised an error")
            logger.error("Empty text did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test invalid case
        try:
            logger.info("Testing invalid case error case...")
            await client.transform_case(test_text, "invalid_case")
            print("❌ Invalid case should have raised an error")
            logger.error("Invalid case did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test invalid operation
        try:
            logger.info("Testing invalid operation error case...")
            await client.generate_text(test_text, "invalid_operation", 1)
            print("❌ Invalid operation should have raised an error")
            logger.error("Invalid operation did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test count out of range
        try:
            logger.info("Testing count out of range error case...")
            await client.generate_text(test_text, "repeat", 1001)
            print("❌ Count > 1000 should have raised an error")
            logger.error("Count > 1000 did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test unknown function
        try:
            logger.info("Testing unknown function error case...")
            await client.call_function("unknown_function", text="test")
            print("❌ Unknown function should have raised an error")
            logger.error("Unknown function did not raise an error")
        except RuntimeError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.info("CLIENT: Starting text processor client")
    try:
        asyncio.run(run_text_processor_test())
    except KeyboardInterrupt:
        logger.info("CLIENT: Shutting down text processor client")
    except Exception as e:
        logger.error(f"CLIENT: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 