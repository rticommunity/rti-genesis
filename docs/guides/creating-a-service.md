# Genesis Function Service Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Creating a New Service](#creating-a-new-service)
5. [Creating a New Client](#creating-a-new-client)
6. [Common Schemas and Validation](#common-schemas-and-validation)
7. [Error Handling](#error-handling)
8. [Testing](#testing)
9. [Common Issues and Solutions](#common-issues-and-solutions)
10. [Best Practices](#best-practices)

## Overview

The Genesis Function Service system provides a distributed RPC (Remote Procedure Call) framework built on RTI Connext DDS. It enables creation of robust, type-safe services with automatic validation, error handling, and consistent patterns for both service and client implementations.

### Key Features
- OpenAI-style function schemas
- Built-in input validation
- Consistent error handling
- Automatic service discovery
- Asynchronous communication
- Comprehensive logging
- Resource cleanup

## Architecture

### Communication Flow
1. Client initializes and waits for service discovery
2. Service registers functions with schemas
3. Client calls function with parameters
4. Service validates inputs and processes request
5. Service returns formatted response
6. Client receives and processes response

### DDS Integration
- Uses RTI Connext DDS for communication
- Domain-based service discovery
- Quality of Service (QoS) profiles
- Reliable message delivery
- Publisher/Subscriber pattern

## Components

### GenesisRPCService
Base class for all services providing:
- Function registration
- Schema validation
- Request handling
- Response formatting
- Resource management

### GenesisRPCClient
Base class for all clients providing:
- Service discovery
- Function calling
- Input validation
- Error handling
- Resource management

## Creating a New Service

### 1. Create Service Class
```python
class YourService(GenesisRPCService):
    def __init__(self):
        super().__init__(service_name="YourServiceName")
        
        # Get common schemas
        text_schema = self.get_common_schema("text")
        number_schema = self.get_common_schema("number")
        
        # Register functions
        self.register_function(
            self.your_function,
            "Function description",
            {
                "type": "object",
                "properties": {
                    "param1": text_schema.copy(),
                    "param2": number_schema.copy()
                },
                "required": ["param1"],
                "additionalProperties": False
            },
            operation_type="your_operation_type",
            common_patterns={
                "param1": {"type": "text", "min_length": 1},
                "param2": {"type": "number", "minimum": 0}
            }
        )
```

### 2. Implement Service Functions
```python
def your_function(self, param1: str, param2: Optional[float] = None) -> Dict[str, Any]:
    # Log function call
    logger.debug(f"SERVICE: your_function called with param1='{param1}', param2={param2}")
    
    # Validate inputs
    self.validate_text_input(param1, min_length=1)
    if param2 is not None:
        self.validate_numeric_input(param2, minimum=0)
    
    # Process request
    result = {
        "processed": f"{param1}-{param2}"
    }
    
    # Return formatted response
    return self.format_response(
        {"param1": param1, "param2": param2},
        result
    )
```

## Creating a New Client

### 1. Create Client Class
```python
class YourClient(GenesisRPCClient):
    def __init__(self):
        super().__init__(service_name="YourServiceName")
        
        # Add validation patterns
        self.validation_patterns.update({
            "custom_text": {
                "min_length": 1,
                "max_length": 100
            },
            "custom_number": {
                "minimum": 0,
                "maximum": 100
            }
        })
```

### 2. Implement Client Functions
```python
async def your_function(self, param1: str, param2: Optional[float] = None) -> Dict[str, Any]:
    # Log function call
    logger.debug(f"CLIENT: Calling your_function with param1='{param1}', param2={param2}")
    
    # Validate inputs
    self.validate_text(param1, pattern_type="custom_text")
    if param2 is not None:
        self.validate_numeric(param2, pattern_type="custom_number")
    
    # Call service function
    return await self.call_function_with_validation(
        "your_function",
        param1=param1,
        param2=param2
    )
```

## Common Schemas and Validation

### Available Common Schemas
1. **text**
   - min_length: Minimum text length
   - max_length: Maximum text length (optional)
   - pattern: Regex pattern (optional)

2. **number**
   - minimum: Minimum value
   - maximum: Maximum value
   - type: "integer" or "number"

3. **letter**
   - min_length: 1
   - max_length: 1
   - pattern: "^[a-zA-Z]$"

4. **count**
   - minimum: 0
   - type: "integer"

### Validation Methods

#### Service-side Validation
```python
# Text validation
self.validate_text_input(text, min_length=1, max_length=None, pattern=None)

# Numeric validation
self.validate_numeric_input(value, minimum=None, maximum=None)
```

#### Client-side Validation
```python
# Text validation
self.validate_text(text, pattern_type="custom_text")

# Numeric validation
self.validate_numeric(value, pattern_type="custom_number")

# Enum validation
self.validate_enum_value(value, pattern_type="custom_enum")
```

## Error Handling

### Common Error Types
1. **ValueError**
   - Invalid input values
   - Failed validation
   - Out of range values

2. **RuntimeError**
   - Service communication errors
   - Unknown functions
   - Processing errors

3. **TimeoutError**
   - Service discovery timeout
   - Function call timeout

### Error Handling Patterns
```python
try:
    result = await client.your_function("test", 50)
except ValueError as e:
    # Handle validation errors
    logger.error(f"Validation error: {str(e)}")
except TimeoutError as e:
    # Handle timeouts
    logger.error(f"Timeout error: {str(e)}")
except RuntimeError as e:
    # Handle service errors
    logger.error(f"Service error: {str(e)}")
except Exception as e:
    # Handle unexpected errors
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
```

## Testing

### Service Testing
1. Start service in background
2. Wait for initialization
3. Run client tests
4. Clean up resources

Example test script:
```bash
#!/bin/bash

# Start service
python3 your_service.py &
SERVICE_PID=$!

# Wait for service startup
sleep 5

# Run client tests
python3 your_client.py

# Cleanup
kill $SERVICE_PID
wait $SERVICE_PID 2>/dev/null
```

### Client Testing
1. Test successful cases
2. Test validation errors
3. Test service errors
4. Test timeouts
5. Test resource cleanup

## Common Issues and Solutions

### 1. Service Discovery Timeout
**Issue**: Client cannot discover service
**Solutions**:
- Ensure service is running
- Check domain_id matches
- Increase discovery timeout
- Verify network connectivity

### 2. Validation Errors
**Issue**: Function calls fail validation
**Solutions**:
- Check input values match schemas
- Verify validation patterns match between client and service
- Enable debug logging to see validation details

### 3. Resource Cleanup
**Issue**: Resources not properly released
**Solutions**:
- Use try/finally blocks
- Call client.close() after use
- Handle KeyboardInterrupt
- Use context managers when possible

### 4. Schema Mismatches
**Issue**: Service rejects client calls
**Solutions**:
- Ensure schemas match exactly
- Copy schemas instead of reusing
- Check required vs optional parameters
- Verify parameter types

## Best Practices

### Service Implementation
1. Always validate inputs
2. Use descriptive error messages
3. Log all function calls
4. Include original inputs in responses
5. Clean up resources properly
6. Use type hints
7. Document all functions

### Client Implementation
1. Validate before calling service
2. Handle all error cases
3. Use appropriate timeouts
4. Clean up resources
5. Log service calls
6. Include comprehensive tests

### General Guidelines
1. Use common schemas when possible
2. Follow consistent naming patterns
3. Document error conditions
4. Test edge cases
5. Handle interruptions gracefully
6. Use async/await properly
7. Keep functions focused and simple

## Example Implementations

See the template files for complete examples:
- `templates/service_template.py`
- `templates/client_template.py`

These templates provide working examples of all patterns and practices described in this guide. 
---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
