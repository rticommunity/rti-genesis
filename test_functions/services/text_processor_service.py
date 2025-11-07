#!/usr/bin/env python3
# --------------------------------------------------------------------------- #
# TextProcessorService: Decorator-Based Function Definition with Pydantic
#
# This service showcases a modern approach to defining and registering functions
# within the Genesis framework, primarily utilizing the `@genesis_function`
# decorator in conjunction with Pydantic models.
#
# Key characteristics of this approach:
#   - Decorator-Driven Registration: Functions are defined as standard Python
#     methods and then "enhanced" or registered using the `@genesis_function`
#     decorator. This decorator likely handles the introspection and
#     registration with the underlying service base.
#   - Pydantic for Schema and Validation: Input arguments for service functions
#     are defined using Pydantic models (e.g., `TextArgs`, `TransformCaseArgs`).
#     Pydantic provides data validation, serialization, and automatically
#     generates a schema that can be used for function calling by LLMs.
#   - Metadata in Decorator: The decorator can take arguments like `description`,
#     `model` (referencing the Pydantic model), and `operation_type` to
#     provide rich metadata.
#
# Strengths:
#   - Python-idiomatic: Feels natural for Python developers.
#   - Declarative Validation: Pydantic models clearly define the expected
#     data structure and validation rules.
#   - Readability and Maintainability: Consolidates schema definition with
#     argument types.
#   - Automatic Schema Generation: Simplifies compatibility with systems
#     requiring structured function definitions (like OpenAI).
#
# Considerations:
#   - Learning Curve: Requires familiarity with Pydantic and decorator patterns,
#     which might introduce a slight learning curve for developers new to
#     these concepts.
# --------------------------------------------------------------------------- #

import logging
import asyncio
from typing import Dict, Any, List
import json
from pydantic import BaseModel, Field
from genesis_lib.monitored_service import MonitoredService
from genesis_lib.decorators import genesis_function

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_service")

# Pydantic models for function arguments
class TextArgs(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to process")

class TransformCaseArgs(TextArgs):
    case: str = Field(..., enum=["upper", "lower", "title"], description="Case to transform text to")

class GenerateTextArgs(TextArgs):
    operation: str = Field(..., enum=["repeat", "reverse"], description="Operation to perform on text")
    count: int = Field(..., ge=1, le=100, description="Number of times to perform operation")

class TextProcessorService(MonitoredService):
    """Implementation of the text processor service using Genesis RPC framework"""
    
    def __init__(self, domain_id=0):
        """Initialize the text processor service"""
        super().__init__(service_name="TextProcessorService", capabilities=["text_processor", "text_manipulation"], domain_id=domain_id)
        logger.info(f"TextProcessorService initialized on domain {domain_id}")
        # Everything is now auto-registered; just advertise
        self._advertise_functions()
        logger.info("Functions advertised")

    async def cleanup(self):
        """Clean up resources before shutdown"""
        logger.info("Cleaning up TextProcessorService resources...")
        await super().cleanup()
        logger.info("TextProcessorService cleanup complete")

    def close(self):
        """Clean up resources"""
        logger.info("Closing TextProcessorService...")
        super().close()
        logger.info("TextProcessorService closed")

    @genesis_function(description="Count the number of words in a text",
                     model=TextArgs,
                     operation_type="analysis")
    async def count_words(self, text: str, request_info=None) -> Dict[str, Any]:
        """Count the number of words in a text."""
        logger.info(f"Received count_words request: text='{text}'")
        self.publish_function_call_event("count_words", {"text": text}, request_info)
        
        # Split text into words and count
        words = text.split()
        word_count = len(words)
        
        result = {
            "text": text,
            "word_count": word_count,
            "words": words
        }
        
        self.publish_function_result_event("count_words", result, request_info)
        logger.info(f"Count words result: {result}")
        return result

    @genesis_function(description="Transform text to specified case",
                     model=TransformCaseArgs,
                     operation_type="transformation")
    async def transform_case(self, text: str, case: str, request_info=None) -> Dict[str, Any]:
        """Transform text to specified case."""
        logger.info(f"Received transform_case request: text='{text}', case={case}")
        self.publish_function_call_event("transform_case", {"text": text, "case": case}, request_info)
        
        # Transform text based on case
        if case == "upper":
            transformed = text.upper()
        elif case == "lower":
            transformed = text.lower()
        elif case == "title":
            transformed = text.title()
        else:
            raise ValueError(f"Invalid case: {case}")
        
        result = {
            "original_text": text,
            "transformed_text": transformed,
            "case": case
        }
        
        self.publish_function_result_event("transform_case", result, request_info)
        logger.info(f"Transform case result: {result}")
        return result

    @genesis_function(description="Analyze text for various metrics",
                     model=TextArgs,
                     operation_type="analysis")
    async def analyze_text(self, text: str, request_info=None) -> Dict[str, Any]:
        """Analyze text for various metrics."""
        logger.info(f"Received analyze_text request: text='{text}'")
        self.publish_function_call_event("analyze_text", {"text": text}, request_info)
        
        # Basic text analysis
        words = text.split()
        sentences = text.split('.')
        characters = len(text)
        word_count = len(words)
        sentence_count = len([s for s in sentences if s.strip()])
        
        result = {
            "text": text,
            "character_count": characters,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "average_word_length": sum(len(word) for word in words) / word_count if word_count > 0 else 0
        }
        
        self.publish_function_result_event("analyze_text", result, request_info)
        logger.info(f"Analyze text result: {result}")
        return result

    @genesis_function(description="Generate text based on operation and count",
                     model=GenerateTextArgs,
                     operation_type="generation")
    async def generate_text(self, text: str, operation: str, count: int, request_info=None) -> Dict[str, Any]:
        """Generate text based on operation and count."""
        logger.info(f"Received generate_text request: text='{text}', operation={operation}, count={count}")
        self.publish_function_call_event("generate_text", {"text": text, "operation": operation, "count": count}, request_info)
        
        # Generate text based on operation
        if operation == "repeat":
            generated = (text + " ") * count
        elif operation == "reverse":
            generated = text[::-1] * count
        else:
            raise ValueError(f"Invalid operation: {operation}")
        
        result = {
            "original_text": text,
            "generated_text": generated.strip(),
            "operation": operation,
            "count": count
        }
        
        self.publish_function_result_event("generate_text", result, request_info)
        logger.info(f"Generate text result: {result}")
        return result

def main():
    """Main entry point for the text processor service."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='Text Processor Service')
    parser.add_argument('--domain', type=int, default=None,
                       help='DDS domain ID (default: 0 or GENESIS_DOMAIN_ID env var)')
    args = parser.parse_args()
    
    # Priority: command line arg > env var > default (0)
    domain_id = args.domain if args.domain is not None else int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    logger.info(f"Starting text processor service on domain {domain_id}")
    try:
        service = TextProcessorService(domain_id=domain_id)
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Shutting down text processor service")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
    finally:
        # Ensure cleanup is called
        if 'service' in locals():
            asyncio.run(service.cleanup())

if __name__ == "__main__":
    main() 