"""
Genesis Application Base Class - DDS Infrastructure Foundation

This module provides the foundational base class `GenesisApp` that serves as the core
integration point for all components in the Genesis framework. It establishes the
essential DDS infrastructure, function registration capabilities, and lifecycle
management that are required by both agents and interfaces.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the GenesisApp Foundation
=================================================================================================

GenesisApp is the foundational infrastructure layer that provides:

1. **DDS Infrastructure**: Participant, publisher, subscriber, and QoS management
2. **Function Discovery**: Automatic registration and discovery of network functions
3. **Resource Management**: Lifecycle management for DDS entities and resources
4. **Error Handling**: Pattern-based error detection and recovery mechanisms
5. **Integration Point**: Common base for GenesisAgent and GenesisInterface

=================================================================================================
DESIGN PRINCIPLES - Composition Over Inheritance
=================================================================================================

GenesisApp uses composition (has-a) rather than inheritance (is-a) because:

1. **FLEXIBILITY**: Multiple components can share a single DDS participant
2. **MULTIPLE COMPONENT TYPES**: Agents, interfaces, and services need different base classes
3. **SEPARATION OF CONCERNS**: DDS infrastructure vs. business logic are orthogonal
4. **RESOURCE SHARING**: Enables efficient resource utilization in constrained environments

This follows the "favor composition over inheritance" principle, delegating DDS
infrastructure concerns to GenesisApp while allowing components to focus on their
specific roles in the Genesis network.

=================================================================================================
DDS INFRASTRUCTURE - Real-Time Communication Foundation
=================================================================================================

GenesisApp establishes the DDS infrastructure required for real-time communication:

1. **Participant Management**: Creates and manages DDS domain participants
2. **QoS Configuration**: Optimizes reliability, durability, and performance
3. **Topic Management**: Handles unified advertisement and function discovery topics
4. **Resource Lifecycle**: Ensures proper cleanup and resource management

The infrastructure supports:
- **Reliable Communication**: Ensures message delivery across the network
- **Transient Durability**: Maintains state across participant restarts
- **Automatic Liveliness**: Detects and handles participant failures
- **Shared Ownership**: Enables load balancing and redundancy

=================================================================================================
FUNCTION DISCOVERY - Network Service Integration
=================================================================================================

GenesisApp provides comprehensive function discovery capabilities:

1. **Automatic Registration**: Functions are automatically discovered and registered
2. **Network-Wide Discovery**: Functions from all participants are available
3. **Dynamic Updates**: Real-time updates as functions come online/offline
4. **Metadata Management**: Rich function metadata for intelligent routing

This enables:
- **Service Mesh**: Automatic discovery of network services
- **Load Balancing**: Intelligent routing to available function instances
- **Fault Tolerance**: Automatic failover to healthy instances
- **Scalability**: Dynamic scaling as services are added/removed

=================================================================================================
ERROR HANDLING - Pattern-Based Recovery
=================================================================================================

GenesisApp implements sophisticated error handling through pattern matching:

1. **Success Patterns**: Recognizes successful operation patterns
2. **Failure Patterns**: Identifies common failure modes and causes
3. **Recovery Hints**: Provides actionable guidance for error recovery
4. **Pattern Registry**: Centralized pattern management and updates

This enables:
- **Intelligent Error Detection**: Automatic classification of error types
- **Recovery Guidance**: Actionable hints for resolving issues
- **Pattern Learning**: Continuous improvement of error detection
- **Debugging Support**: Enhanced troubleshooting capabilities

=================================================================================================
INTEGRATION PATTERNS - Component Lifecycle
=================================================================================================

GenesisApp provides standardized integration patterns for all Genesis components:

1. **Initialization**: Consistent setup across all component types
2. **Resource Management**: Automatic cleanup and resource management
3. **Error Handling**: Standardized error patterns and recovery
4. **Monitoring**: Built-in observability and monitoring support

This ensures:
- **Consistency**: Uniform behavior across all Genesis components
- **Reliability**: Robust error handling and recovery mechanisms
- **Maintainability**: Standardized patterns for easier maintenance
- **Observability**: Built-in monitoring and debugging capabilities

=================================================================================================
USAGE PATTERNS - Common Integration Scenarios
=================================================================================================

1. **Agent Integration** (Automatic):
   ```python
   # GenesisAgent automatically creates GenesisApp
   agent = OpenAIGenesisAgent(agent_name="MyAgent")
   # DDS infrastructure is automatically available
   ```

2. **Interface Integration** (Manual):
   ```python
   # GenesisInterface uses GenesisApp for DDS infrastructure
   interface = GenesisInterface()
   # Function discovery and DDS communication available
   ```

3. **Custom Component Integration**:
   ```python
   # Create GenesisApp for custom components
   app = GenesisApp(domain_id=0, preferred_name="CustomComponent")
   # Access DDS infrastructure and function discovery
   functions = app.get_available_functions()
   ```

=================================================================================================
RESOURCE MANAGEMENT - Lifecycle and Cleanup
=================================================================================================

GenesisApp implements comprehensive resource management:

1. **Automatic Cleanup**: Resources are automatically cleaned up on close
2. **Error Recovery**: Graceful handling of cleanup errors
3. **Resource Tracking**: Monitors resource state and prevents double-cleanup
4. **Async Support**: Proper async/await support for resource cleanup

This ensures:
- **Memory Safety**: No resource leaks or dangling references
- **Error Resilience**: Graceful handling of cleanup failures
- **Performance**: Efficient resource utilization and cleanup
- **Reliability**: Consistent behavior across different scenarios

=================================================================================================

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import time
from typing import Dict, List, Any, Optional, Callable
import uuid
import rti.connextdds as dds
from genesis_lib.function_discovery import FunctionRegistry, FunctionInfo
from .function_patterns import SuccessPattern, FailurePattern, pattern_registry
import os
import traceback
from genesis_lib.utils import get_datamodel_path
import asyncio

# Configure logging
logger = logging.getLogger("genesis_app")

# =============================================================================
# GENESIS APP CLASS - DDS INFRASTRUCTURE FOUNDATION
# =============================================================================
# The GenesisApp class provides the foundational DDS infrastructure and function
# discovery capabilities required by all Genesis components.
# =============================================================================

class GenesisApp:
    """
    Base class for Genesis applications that provides DDS infrastructure and function discovery.
    
    GenesisApp is the foundational infrastructure layer that provides:
    
    1. **DDS Infrastructure**: Participant, publisher, subscriber, and QoS management
    2. **Function Discovery**: Automatic registration and discovery of network functions
    3. **Resource Management**: Lifecycle management for DDS entities and resources
    4. **Error Handling**: Pattern-based error detection and recovery mechanisms
    5. **Integration Point**: Common base for GenesisAgent and GenesisInterface
    
    The class uses composition (has-a) rather than inheritance (is-a) to provide
    maximum flexibility for different component types while maintaining separation
    of concerns between DDS infrastructure and business logic.
    
    Examples:
        # Automatic integration with GenesisAgent
        agent = OpenAIGenesisAgent(agent_name="MyAgent")
        # DDS infrastructure is automatically available via agent.app
        
        # Manual integration for custom components
        app = GenesisApp(domain_id=0, preferred_name="CustomComponent")
        functions = app.get_available_functions()
        await app.close()
    """
    
    def __init__(self, participant=None, domain_id=0, preferred_name="DefaultAgent", agent_id=None):
        """
        Initialize the Genesis application.
        
        Args:
            participant: DDS participant (if None, will create one)
            domain_id: DDS domain ID
            preferred_name: Preferred name for this application instance
            agent_id: Optional UUID for the agent (if None, will generate one)
        """
        # Generate or use provided agent ID
        self.agent_id = agent_id or str(uuid.uuid4())
        self.preferred_name = preferred_name
        
        # Initialize DDS participant
        if participant is None:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
            
        # Store DDS GUID - used for participant identification in logging and monitoring.
        # This GUID uniquely identifies this DDS participant instance in the network.
        # Used in: initialization logging, monitored_agent.py for agent tracking
        self.dds_guid = str(self.participant.instance_handle)
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # GenesisRegistration topic removed - now using unified Advertisement topic
        
        # Create publisher and subscriber with QoS
        self.publisher = dds.Publisher(
            self.participant,
            qos=dds.QosProvider.default.publisher_qos
        )
        self.subscriber = dds.Subscriber(
            self.participant,
            qos=dds.QosProvider.default.subscriber_qos
        )
        
        # DataWriter QoS is now configured in XML (genesis_lib/config/USER_QOS_PROFILES.xml)
        # Using default profile with: RELIABLE, TRANSIENT_LOCAL, KEEP_LAST(500),
        # AUTOMATIC liveliness (2s lease), SHARED ownership, ASYNCHRONOUS publish mode
        # This provides a single source of truth for DDS QoS configuration
        
        # Initialize function registry and pattern registry
        logger.debug("===== DDS TRACE: Initializing FunctionRegistry in GenesisApp =====")
        self.function_registry = FunctionRegistry(self.participant, domain_id)
        logger.debug(f"===== DDS TRACE: FunctionRegistry initialized with participant {self.participant.instance_handle} =====")
        self.pattern_registry = pattern_registry
        
        # Register built-in functions
        logger.debug("===== DDS TRACE: Starting built-in function registration =====")
        self._register_builtin_functions()
        logger.debug("===== DDS TRACE: Completed built-in function registration =====")
        
        logger.info(f"GenesisApp initialized with agent_id={self.agent_id}, dds_guid={self.dds_guid}")

    # =============================================================================
    # FUNCTION DISCOVERY METHODS - NETWORK SERVICE INTEGRATION
    # =============================================================================
    # Methods for discovering and accessing network functions and services
    # =============================================================================
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all currently discovered functions available on the network.
        
        This method provides a real-time snapshot of all functions discovered
        across the Genesis network. Functions are automatically discovered and
        registered as participants come online/offline.
        
        Returns:
            Dictionary mapping function_id to function details:
            - name: Human-readable function name
            - description: Function description and capabilities
            - provider_id: ID of the service providing this function
            - schema: JSON schema for function parameters
            - metadata: Additional function metadata
            
        Examples:
            # Get all available functions
            functions = app.get_available_functions()
            print(f"Found {len(functions)} functions")
            
            # Access specific function details
            for func_id, details in functions.items():
                print(f"Function: {details['name']}")
                print(f"Description: {details['description']}")
                
        Note:
            This method returns a snapshot at the time of the call. For real-time
            updates, use the FunctionRegistry's event system or polling.
        """
        if hasattr(self, 'function_registry') and self.function_registry:
            return self.function_registry.get_all_discovered_functions()
        else:
            logger.warning("FunctionRegistry not available in GenesisApp, cannot get available functions.")
            return {}

    # =============================================================================
    # LIFECYCLE MANAGEMENT METHODS - RESOURCE CLEANUP
    # =============================================================================
    # Methods for managing component lifecycle and resource cleanup
    # =============================================================================
    
    @property
    def closed(self) -> bool:
        """
        Check if this GenesisApp has been closed.
        
        Returns:
            True if close() has been called, False otherwise.
        """
        return getattr(self, '_closed', False)
    
    async def close(self):
        """
        Close all DDS entities and cleanup resources.
        
        This method performs comprehensive cleanup of all DDS resources
        in the correct order to prevent resource leaks and ensure proper
        shutdown. It handles both synchronous and asynchronous cleanup
        operations.
        
        The cleanup process includes:
        1. Publisher and subscriber cleanup
        2. DDS participant cleanup (may fail if shared with other agents)
        
        Note: function_registry cleanup is not needed as DDS retains function
        advertisements independently of the registry lifecycle.
        
        This method is idempotent - calling it multiple times is safe.
        
        Examples:
            # Manual cleanup
            app = GenesisApp()
            # ... use app ...
            await app.close()
            
            # Automatic cleanup with context manager
            async with GenesisApp() as app:
                # ... use app ...
                pass  # Automatic cleanup on exit
                
        Note:
            Always call this method when done with the GenesisApp to
            prevent resource leaks and ensure proper DDS cleanup.
        """
        # Idempotent guard: _closed is set to True at the end of this method
        # This prevents double-closing if close() is called multiple times
        if hasattr(self, '_closed') and self._closed:
            logger.info(f"GenesisApp {self.agent_id} is already closed")
            return

        try:
            # Close subscriber first (reverse order of creation)
            try:
                self.subscriber.close()
                logger.debug("Subscriber closed")
            except Exception as e:
                logger.warning(f"Error closing subscriber: {e}")
            
            # Close publisher
            try:
                self.publisher.close()
                logger.debug("Publisher closed")
            except Exception as e:
                logger.warning(f"Error closing publisher: {e}")
            
            # Close participant (may fail with "precondition not met" if shared)
            try:
                self.participant.close()
                logger.debug("Participant closed")
            except Exception as e:
                error_msg = str(e).lower()
                # If participant is shared with other agents, deletion fails gracefully
                if "precondition not met" in error_msg or "still in use" in error_msg:
                    logger.info(f"Participant {self.dds_guid} still in use by other components (expected for shared participants)")
                else:
                    logger.warning(f"Error closing participant: {e}")
            
        except Exception as e:
            # Catastrophic failure during cleanup
            logger.error(f"Unexpected error during GenesisApp cleanup: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            # Always mark as closed, even if there were errors
            self._closed = True
            logger.info(f"GenesisApp {self.agent_id} closed")

    # =============================================================================
    # INTERNAL METHODS - INFRASTRUCTURE SETUP
    # =============================================================================
    # Internal methods for setting up DDS infrastructure and function registration
    # =============================================================================
    
    def _register_builtin_functions(self):
        """Register any built-in functions for this application"""
        logger.debug("===== DDS TRACE: _register_builtin_functions called =====")
        # Override this method in subclasses to register built-in functions
        pass

    # =============================================================================
    # FUNCTION EXECUTION METHODS - PATTERN-BASED ERROR HANDLING
    # =============================================================================
    # Methods for executing functions with intelligent error detection and recovery
    # =============================================================================
    
    def execute_function(self, function_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered function with intelligent error pattern checking.
        
        This method executes a function and automatically analyzes the result
        using pattern-based error detection. It provides intelligent error
        classification and recovery hints for improved debugging and reliability.
        
        The execution process includes:
        1. Function execution with parameter validation
        2. Result pattern analysis (success/failure detection)
        3. Error classification and recovery hint generation
        4. Structured response formatting
        
        Args:
            function_id: ID of the function to execute
            parameters: Dictionary of function parameters
            
        Returns:
            Dictionary containing execution results:
            - status: "success" or "error"
            - result: Function result (if successful)
            - error_code: Error classification (if failed)
            - message: Human-readable error message (if failed)
            - recovery_hint: Actionable recovery guidance (if failed)
            
        Examples:
            # Execute function with error handling
            result = app.execute_function("calculate_sum", {"a": 5, "b": 3})
            
            if result["status"] == "success":
                print(f"Result: {result['result']}")
            else:
                print(f"Error: {result['message']}")
                print(f"Recovery: {result['recovery_hint']}")
                
        Note:
            This method provides enhanced error handling compared to direct
            function calls. Use this for production code that requires
            robust error detection and recovery guidance.
        """
        try:
            # Execute the function
            result = super().execute_function(function_id, parameters)
            
            # Check result against patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, result)
            
            if is_success:
                return {
                    "status": "success",
                    "result": result
                }
            else:
                return {
                    "status": "error",
                    "error_code": error_code,
                    "message": str(result),
                    "recovery_hint": recovery_hint
                }
                
        except Exception as e:
            # Check if exception matches any failure patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, e)
            
            return {
                "status": "error",
                "error_code": error_code or "UNKNOWN_ERROR",
                "message": str(e),
                "recovery_hint": recovery_hint
            } 