#!/usr/bin/env python3

import logging
import asyncio
import json
from typing import Dict, Any, List
from genesis_lib.function_requester import FunctionRequester

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("schema_test")

# Expected schemas for calculator functions
EXPECTED_CALCULATOR_SCHEMAS = {
    "add": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "subtract": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "multiply": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "divide": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    }
}

# Expected schemas for letter counter functions
EXPECTED_LETTER_COUNTER_SCHEMAS = {
    "count_letter": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "letter": {
                "type": "string",
                "description": "Single letter input"
            }
        },
        "required": ["text", "letter"]
    },
    "count_multiple_letters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "letters": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of letters to count"
            }
        },
        "required": ["text", "letters"]
    },
    "get_letter_frequency": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            }
        },
        "required": ["text"]
    }
}

# Expected schemas for text processor functions
EXPECTED_TEXT_PROCESSOR_SCHEMAS = {
    "transform_case": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "case": {
                "type": "string",
                "description": "Target case transformation to apply",
                "enum": ["upper", "lower", "title"]
            }
        },
        "required": ["text", "case"]
    },
    "analyze_text": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            }
        },
        "required": ["text"]
    },
    "generate_text": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "operation": {
                "type": "string",
                "description": "Operation to perform on the text",
                "enum": ["repeat", "pad"]
            },
            "count": {
                "type": "integer",
                "description": "For 'repeat': number of times to repeat the text. For 'pad': length of padding on each side",
                "minimum": 0,
                "maximum": 1000
            }
        },
        "required": ["text", "operation", "count"]
    }
}

async def verify_function_schemas():
    """
    Verify that the discovered function schemas match our expectations.
    """
    requester = FunctionRequester()
    
    try:
        # Discover available functions with a longer timeout
        print("Waiting for function discovery (10 seconds)...")
        await requester.discover_functions(timeout_seconds=10)
        
        # List available functions
        functions = requester.list_available_functions()
        print("\nDiscovered Functions:")
        for func in functions:
            print(f"  - {func['function_id']}: {func['name']} - {func['description']}")
        
        # Verify calculator schemas
        print("\nVerifying Calculator Schemas:")
        calculator_functions = [f for f in functions if f['name'] in EXPECTED_CALCULATOR_SCHEMAS]
        
        if not calculator_functions:
            print("❌ No calculator functions discovered")
        else:
            for func in calculator_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_CALCULATOR_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for calculator function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
        # Verify letter counter schemas
        print("\nVerifying Letter Counter Schemas:")
        letter_counter_functions = [f for f in functions if f['name'] in EXPECTED_LETTER_COUNTER_SCHEMAS]
        
        if not letter_counter_functions:
            print("❌ No letter counter functions discovered")
        else:
            for func in letter_counter_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_LETTER_COUNTER_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for letter counter function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
        # Verify text processor schemas
        print("\nVerifying Text Processor Schemas:")
        text_processor_functions = [f for f in functions if f['name'] in EXPECTED_TEXT_PROCESSOR_SCHEMAS]
        
        if not text_processor_functions:
            print("❌ No text processor functions discovered")
        else:
            for func in text_processor_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_TEXT_PROCESSOR_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for text processor function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error during schema verification: {str(e)}", exc_info=True)
    finally:
        requester.close()

def compare_schemas(schema1: Dict[str, Any], schema2: Dict[str, Any]) -> bool:
    """
    Compare two schemas to see if they match.
    This is a simplified comparison that checks:
    1. Same type
    2. Same properties
    3. Same required fields
    
    Args:
        schema1: First schema to compare
        schema2: Second schema to compare
        
    Returns:
        True if schemas match, False otherwise
    """
    # Check type
    if schema1.get('type') != schema2.get('type'):
        return False
    
    # Check properties
    props1 = schema1.get('properties', {})
    props2 = schema2.get('properties', {})
    
    if set(props1.keys()) != set(props2.keys()):
        return False
    
    # Check property types
    for prop_name in props1:
        if props1[prop_name].get('type') != props2[prop_name].get('type'):
            return False
    
    # Check required fields
    req1 = set(schema1.get('required', []))
    req2 = set(schema2.get('required', []))
    
    if req1 != req2:
        return False
    
    return True

def main():
    """Main entry point"""
    logger.info("Starting schema verification test")
    try:
        asyncio.run(verify_function_schemas())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 