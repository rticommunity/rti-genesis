# Agent-to-Agent Communication in Genesis

## Executive Summary

Agent-to-agent communication in Genesis will follow a hybrid approach combining elements from both the interface-to-agent and agent-to-service communication patterns. The implementation will use DDS RPC with the existing `AgentAgentRequest` and `AgentAgentReply` types, while incorporating agent discovery, automatic connection management, and monitoring capabilities.

## 1. Architecture Overview

### 1.1 Communication Model
- **Pattern**: Request-Reply using DDS RPC
- **Types**: `AgentAgentRequest` and `AgentAgentReply` (already defined in datamodel.xml)
- **Discovery**: Agents discover each other through the existing registration mechanism
- **Connection**: Dynamic RPC connections established on-demand between agents

### 1.2 Key Components
1. **Agent RPC Capability**: Agents can act as both RPC clients and servers
2. **Agent Discovery**: Leverage existing `genesis_agent_registration_announce` mechanism
3. **Dynamic Service Names**: Use `{base_service_name}_{agent_id}` pattern for unique RPC endpoints
4. **Capability Advertisement**: Extend `AgentCapability` usage for advertising agent-specific services

## 2. Implementation Components

### 2.1 New Base Class: `AgentCommunicationMixin`

```python
class AgentCommunicationMixin:
    """
    Mixin class that provides agent-to-agent communication capabilities.
    This can be mixed into GenesisAgent or MonitoredAgent.
    """
    
    def __init__(self):
        # Store active agent connections
        self.agent_connections: Dict[str, rpc.Requester] = {}
        self.discovered_agents: Dict[str, Dict[str, Any]] = {}
        
        # Agent capability writer for advertising
        self.agent_capability_writer = None
        
        # Initialize agent-to-agent RPC types
        self.agent_request_type = None
        self.agent_reply_type = None
```

### 2.2 Agent Discovery Enhancement

Extend the existing agent discovery mechanism to support agent-to-agent communication:

```python
def _setup_agent_discovery(self):
    """Set up agent discovery for agent-to-agent communication"""
    # Create reader for AgentCapability topic
    # Listen for other agents advertising their capabilities
    # Store discovered agents with their service names and capabilities
```

### 2.3 Agent RPC Service Setup

Each agent that wants to receive requests from other agents needs to set up an additional RPC replier:

```python
def _setup_agent_rpc_service(self):
    """Set up RPC service for receiving requests from other agents"""
    # Create unique service name for this agent
    agent_service_name = f"AgentService_{self.app.agent_id}"
    
    # Create replier for agent-to-agent communication
    self.agent_replier = rpc.Replier(
        request_type=self.agent_request_type,
        reply_type=self.agent_reply_type,
        participant=self.app.participant,
        service_name=agent_service_name
    )
```

### 2.4 Agent Connection Management

```python
async def connect_to_agent(self, target_agent_id: str, timeout_seconds: float = 5.0) -> bool:
    """
    Establish RPC connection to another agent.
    
    Args:
        target_agent_id: ID of the target agent
        timeout_seconds: Connection timeout
        
    Returns:
        True if connection successful, False otherwise
    """
    # Look up target agent in discovered agents
    # Get target agent's service name
    # Create RPC requester
    # Wait for DDS match
    # Store connection for reuse
```

### 2.5 Agent-to-Agent Request Handling

```python
async def send_agent_request(self, 
                           target_agent_id: str, 
                           message: str, 
                           conversation_id: Optional[str] = None,
                           timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
    """
    Send a request to another agent.
    
    Args:
        target_agent_id: ID of the target agent
        message: Request message
        conversation_id: Optional conversation ID for tracking
        timeout_seconds: Request timeout
        
    Returns:
        Reply data or None if failed
    """
    # Ensure connection exists
    # Create AgentAgentRequest
    # Send via RPC
    # Wait for AgentAgentReply
    # Return parsed response
```

## 3. Integration Points

### 3.1 GenesisAgent Enhancement

Modify `GenesisAgent` to support agent-to-agent communication:

```python
class GenesisAgent(ABC):
    def __init__(self, agent_name: str, base_service_name: str, 
                 service_instance_tag: Optional[str] = None, 
                 agent_id: str = None,
                 enable_agent_communication: bool = False):
        # Existing initialization...
        
        if enable_agent_communication:
            self._setup_agent_communication()
    
    def _setup_agent_communication(self):
        """Initialize agent-to-agent communication capabilities"""
        # Initialize mixin
        # Set up agent discovery
        # Set up agent RPC service
        # Advertise agent capability
```

### 3.2 MonitoredAgent Enhancement

Add monitoring for agent-to-agent communication:

```python
class MonitoredAgent(GenesisAgent):
    async def send_agent_request_monitored(self, target_agent_id: str, message: str, **kwargs):
        """Send agent request with monitoring"""
        # Publish AGENT_REQUEST event
        # Send request
        # Publish AGENT_RESPONSE event
        # Publish chain events for tracking
```

## 4. Usage Example

```python
# Agent A - Requester
class AgentA(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="AgentA",
            base_service_name="ServiceA",
            enable_agent_communication=True
        )
    
    async def collaborate_with_agent_b(self):
        # Discover Agent B
        await self.wait_for_agent("AgentB")
        
        # Send request to Agent B
        response = await self.send_agent_request(
            target_agent_id="agent_b_id",
            message="Please process this data: [1, 2, 3]"
        )
        
        if response:
            print(f"Agent B replied: {response['message']}")

# Agent B - Responder
class AgentB(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="AgentB",
            base_service_name="ServiceB",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests from other agents"""
        message = request.get('message', '')
        
        # Process the request
        result = self._process_data(message)
        
        return {
            'message': f"Processed result: {result}",
            'status': 0,
            'conversation_id': request.get('conversation_id', '')
        }
```

## 5. Monitoring and Observability

### 5.1 New Monitoring Events
- `AGENT_TO_AGENT_REQUEST`: When an agent sends a request to another agent
- `AGENT_TO_AGENT_RESPONSE`: When an agent receives a response from another agent
- `AGENT_CONNECTION_ESTABLISHED`: When agents establish RPC connection
- `AGENT_CONNECTION_LOST`: When agent connection is lost

### 5.2 Chain Event Tracking
- Track agent-to-agent interactions as part of chain events
- Include both agent IDs in the chain for visualization
- Support multi-hop agent chains

## 6. Advanced Features

### 6.1 Capability-Based Routing
```python
async def find_agent_with_capability(self, capability: str) -> Optional[str]:
    """Find an agent that advertises a specific capability"""
    for agent_id, agent_info in self.discovered_agents.items():
        if capability in agent_info.get('capabilities', []):
            return agent_id
    return None
```

### 6.2 Broadcast/Multicast Support
```python
async def broadcast_to_agents(self, message: str, capability_filter: Optional[str] = None):
    """Send a message to multiple agents"""
    target_agents = self._get_agents_by_capability(capability_filter)
    
    tasks = []
    for agent_id in target_agents:
        task = asyncio.create_task(
            self.send_agent_request(agent_id, message)
        )
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    return responses
```

### 6.3 Conversation Management
```python
class AgentConversation:
    """Manage multi-turn conversations between agents"""
    def __init__(self, initiator_id: str, responder_id: str):
        self.conversation_id = str(uuid.uuid4())
        self.initiator_id = initiator_id
        self.responder_id = responder_id
        self.message_history = []
```

## 7. Security Considerations

1. **Authentication**: Verify agent identities through DDS participant GUIDs
2. **Authorization**: Check if agents are allowed to communicate based on policies
3. **Encryption**: Leverage DDS Security for encrypted agent-to-agent channels
4. **Rate Limiting**: Prevent agent spam/DoS attacks

## 8. Performance Optimizations

1. **Connection Pooling**: Reuse RPC requesters for the same target agent
2. **Lazy Connection**: Only establish connections when first message is sent
3. **Connection Timeout**: Close idle connections after configurable timeout
4. **Batch Requests**: Support sending multiple requests in a single RPC call

## 9. Error Handling

1. **Connection Failures**: Graceful handling with retry logic
2. **Timeout Handling**: Configurable timeouts with proper cleanup
3. **Agent Unavailability**: Queue messages or fail gracefully
4. **Circular Dependencies**: Detect and prevent infinite agent request loops

## 10. Testing Strategy

1. **Unit Tests**: Test individual components (discovery, connection, messaging)
2. **Integration Tests**: Test full agent-to-agent communication flow
3. **Performance Tests**: Measure latency and throughput
4. **Resilience Tests**: Test failure scenarios (agent crash, network partition)

## 11. Migration Path

1. **Phase 1**: Implement basic agent-to-agent RPC
2. **Phase 2**: Add monitoring and observability
3. **Phase 3**: Implement advanced features (broadcast, conversations)
4. **Phase 4**: Security and performance optimizations

## 12. Documentation Requirements

1. **API Documentation**: Document all new methods and classes
2. **Usage Examples**: Provide complete examples for common scenarios
3. **Architecture Diagrams**: Update Genesis architecture documentation
4. **Best Practices Guide**: How to design agent-to-agent interactions 