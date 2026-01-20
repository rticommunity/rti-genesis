# Copyright (c) 2025, RTI & Jason Upchurch
#!/usr/bin/env python3
# --------------------------------------------------------------------------- #
# LetterCounterService: Original Method for Genesis Service Function Definition
#
# This service demonstrates the original approach to defining and registering
# functions within the Genesis framework. Unlike newer services that might
# leverage decorators (e.g., @genesis_function with Pydantic models),
# this service explicitly uses `self.register_enhanced_function` during its
# initialization phase.
#
# Key characteristics of this approach:
#   - Direct Schema Definition: Function parameter schemas are defined as
#     Python dictionaries (resembling JSON Schema) directly within the
#     `__init__` method.
#   - Explicit Registration: Each function is manually registered using
#     `self.register_enhanced_function`, providing the function, its
#     description, schema, operation type, and common patterns.
#
# This method offers precise control over the schema and metadata provided
# for function calling by large language models.
# --------------------------------------------------------------------------- #

import logging
import asyncio
import json
from typing import Dict, Any, List
import re
from genesis_lib.monitored_service import MonitoredService
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("letter_counter_service")

class LetterCounterService(MonitoredService):
    """Implementation of the letter counter service using Genesis RPC framework"""
    
    def __init__(self, domain_id=0):
        """Initialize the letter counter service"""
        # Initialize the enhanced base class with service name and capabilities
        super().__init__(
            service_name="LetterCounterService",
            capabilities=["letter_counter", "text_analysis"],
            domain_id=domain_id
        )
        
        # Get types from XML for monitoring
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        
        # Define schemas inline
        text_schema = {
            "type": "string",
            "description": "Text to analyze"
        }
        letter_schema = {
            "type": "string", 
            "description": "Letter to count",
            "pattern": "^[a-zA-Z]$"
        }
        
        # Register letter counter functions with OpenAI-style schemas
        self.register_enhanced_function(
            self.count_letter,
            "Count occurrences of a letter in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy(),
                    "letter": letter_schema.copy()
                },
                "required": ["text", "letter"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1},
                "letter": {"type": "letter"}
            }
        )
        
        self.register_enhanced_function(
            self.count_multiple_letters,
            "Count occurrences of multiple letters in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy(),
                    "letters": {
                        "type": "array",
                        "items": letter_schema.copy(),
                        "minItems": 1,
                        "maxItems": 26,
                        "description": "Letters to count"
                    }
                },
                "required": ["text", "letters"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1}
            }
        )
        
        self.register_enhanced_function(
            self.get_letter_frequency,
            "Get frequency distribution of letters in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy()
                },
                "required": ["text"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1}
            }
        )
        
        # Advertise functions
        self._advertise_functions()
    
    def validate_text_input(self, text: str, min_length: int = 0, max_length: int = None, pattern: str = None):
        """Validate text input"""
        if not text or len(text) < min_length:
            raise ValueError(f"Text must be at least {min_length} characters")
        if max_length and len(text) > max_length:
            raise ValueError(f"Text must be at most {max_length} characters")
        if pattern and not re.match(pattern, text):
            raise ValueError(f"Text must match pattern: {pattern}")
    
    def format_response(self, inputs: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """Format response with inputs and result"""
        return {"inputs": inputs, "result": result}
    
    def count_letter(self, text: str, letter: str, request_info=None) -> Dict[str, Any]:
        """
        Count occurrences of a letter in text
        
        Args:
            text: Text to analyze
            letter: Letter to count
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters and count
            
        Raises:
            ValueError: If text is empty or letter is not a single alphabetic character
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "count_letter",
                {"text": text, "letter": letter},
                request_info
            )
            
            logger.debug(f"SERVICE: count_letter called with text='{text}', letter='{letter}'")
            
            # Validate inputs
            self.validate_text_input(text, min_length=1)
            self.validate_text_input(letter, min_length=1, max_length=1, pattern="^[a-zA-Z]$")
            
            # Count occurrences (case insensitive)
            count = text.lower().count(letter.lower())
            
            # Log the result
            logger.info(f"==== LETTER COUNTER SERVICE: count_letter('{text}', '{letter}') = {count} ====")
            
            # Publish function result event
            self.publish_function_result_event(
                "count_letter",
                {"result": count},
                request_info
            )
            
            return self.format_response({"text": text, "letter": letter}, count)
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "count_letter",
                e,
                request_info
            )
            raise
    
    def count_multiple_letters(self, text: str, letters: List[str], request_info=None) -> Dict[str, Any]:
        """
        Count occurrences of multiple letters in text
        
        Args:
            text: Text to analyze
            letters: List of letters to count
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters and counts
            
        Raises:
            ValueError: If text is empty or any letter is invalid
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "count_multiple_letters",
                {"text": text, "letters": letters},
                request_info
            )
            
            logger.debug(f"SERVICE: count_multiple_letters called with text='{text}', letters={letters}")
            
            # Validate inputs
            self.validate_text_input(text, min_length=1)
            if not letters:
                raise ValueError("Letters list cannot be empty")
            if len(letters) > 26:
                raise ValueError("Cannot count more than 26 letters")
            
            # Validate each letter
            for letter in letters:
                self.validate_text_input(letter, min_length=1, max_length=1, pattern="^[a-zA-Z]$")
            
            # Count occurrences (case insensitive)
            counts = {}
            text_lower = text.lower()
            for letter in letters:
                counts[letter] = text_lower.count(letter.lower())
            
            # Publish function result event
            self.publish_function_result_event(
                "count_multiple_letters",
                {"result": counts},
                request_info
            )
            
            return self.format_response({"text": text, "letters": letters}, counts)
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "count_multiple_letters",
                e,
                request_info
            )
            raise
    
    def get_letter_frequency(self, text: str, request_info=None) -> Dict[str, Any]:
        """
        Get frequency distribution of letters in text
        
        Args:
            text: Text to analyze
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters, total count, and frequency distribution
            
        Raises:
            ValueError: If text is empty
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "get_letter_frequency",
                {"text": text},
                request_info
            )
            
            logger.debug(f"SERVICE: get_letter_frequency called with text='{text}'")
            
            # Validate input
            self.validate_text_input(text, min_length=1)
            
            # Count letter frequencies (case insensitive)
            text_lower = text.lower()
            letter_count = {}
            total_letters = 0
            
            for char in text_lower:
                if char.isalpha():
                    letter_count[char] = letter_count.get(char, 0) + 1
                    total_letters += 1
            
            # Calculate percentages
            frequencies = {}
            for letter, count in letter_count.items():
                frequencies[letter] = {
                    "count": count,
                    "percentage": round((count / total_letters) * 100, 1) if total_letters > 0 else 0
                }
            
            # Publish function result event
            self.publish_function_result_event(
                "get_letter_frequency",
                {"result": frequencies},
                request_info
            )
            
            return self.format_response({"text": text}, {"total_letters": total_letters, "frequencies": frequencies})
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "get_letter_frequency",
                e,
                request_info
            )
            raise

def main():
    """Main entry point"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='Letter Counter Service')
    parser.add_argument('--domain', type=int, default=None,
                       help='DDS domain ID (default: 0 or GENESIS_DOMAIN_ID env var)')
    args = parser.parse_args()
    
    # Priority: command line arg > env var > default (0)
    domain_id = args.domain if args.domain is not None else int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    logger.info(f"SERVICE: Starting letter counter service on domain {domain_id}")
    try:
        # Create and run the letter counter service
        service = LetterCounterService(domain_id=domain_id)
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: Shutting down letter counter service")
    except Exception as e:
        logger.error(f"SERVICE: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 