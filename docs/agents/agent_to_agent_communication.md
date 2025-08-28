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
5. **Agent Classification**: **PURE LLM-based system** to route requests to appropriate agents (all rule-based matching removed)
6. **Enhanced Discovery**: Find agents by capability, specialization, or model type

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

## Implementation Notes (2025-08-28)

The plan above has been implemented. Key entry points in `genesis_lib/agent_communication.py`:

- Type setup: `_initialize_agent_rpc_types()` — loads `AgentAgentRequest` and `AgentAgentReply` from `datamodel.xml` via `dds.QosProvider`.
- Discovery: `_setup_agent_discovery()` — creates durable `AgentCapability` reader with listener; QoS: TRANSIENT_LOCAL + RELIABLE + KEEP_LAST(depth≈500), liveliness AUTOMATIC.
- Capability publishing: `_setup_agent_capability_publishing()` — writer mirrors durable QoS to advertise this agent.
- RPC service: `_setup_agent_rpc_service()` — creates `rti.rpc.Replier` for agent-to-agent endpoint (unique service_name per agent instance).
- Request sending: `send_agent_request()` — creates `AgentAgentRequest`, sends via `rti.rpc.Requester`, correlates `AgentAgentReply`.
- Utilities: `get_agents_by_type()`, `get_agents_by_capability()`, `find_agents_by_capability()`, `find_agents_by_specialization()`.

Integration in agents:
- `genesis_lib/agent.py` → `_setup_agent_communication()` wires mixin into `GenesisAgent` when `enable_agent_communication=True`.
- `OpenAIGenesisAgent` (agent-as-tool): `_ensure_agents_discovered()` and `_convert_agents_to_tools()` create capability-based agent tools for unified tool calls.

See also:
- XML types: `genesis_lib/config/datamodel.xml` → `AgentCapability`, `AgentAgentRequest`, `AgentAgentReply`.
- QoS examples mirror FunctionCapability discovery for durability and reliability.
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

## 4. Usage Examples

### 4.1 Basic Agent-to-Agent Communication

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

### 4.2 Specialized Agent with Enhanced Capabilities

```python
# Weather Agent - Specialized agent
class WeatherAgent(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="WeatherExpert",
            base_service_name="WeatherService",
            enable_agent_communication=True
        )
    
    def get_agent_capabilities(self):
        """Advertise weather-specific capabilities"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology"],
            "capabilities": [
                "get_current_weather",
                "get_forecast",
                "check_weather_alerts"
            ],
            "classification_tags": [
                "weather", "temperature", "rain", 
                "forecast", "climate", "storm"
            ],
            "default_capable": False
        }
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process weather-related requests from other agents"""
        message = request.get('message', '')
        
        # Parse weather query and fetch data
        weather_data = await self.get_weather_data(message)
        
        return {
            'message': f"Weather report: {weather_data}",
            'status': 0,
            'conversation_id': request.get('conversation_id', '')
        }
```

### 4.3 General Agent with Classification

```python
# General Purpose Agent with agent routing
class SmartGeneralAgent(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="SmartAssistant",
            base_service_name="GeneralService",
            enable_agent_communication=True
        )
        self.agent_classifier = AgentClassifier()
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process requests with intelligent routing to specialized agents"""
        message = request['message']
        
        # Check if this needs a specialized agent
        best_agent = await self.agent_classifier.classify_request(
            message, 
            self.get_discovered_agents()
        )
        
        if best_agent and best_agent != self.app.agent_id:
            # Route to specialized agent
            logger.info(f"Routing request to specialized agent: {best_agent}")
            response = await self.send_agent_request(
                target_agent_id=best_agent,
                message=message,
                conversation_id=request.get('conversation_id')
            )
            
            if response and response['status'] == 0:
                return {
                    'message': f"[Via {best_agent}] {response['message']}",
                    'status': 0
                }
        
        # Handle locally if no specialized agent or if routing failed
        return await self.handle_general_request(request)
```

### 4.4 Concrete Weather Agent Implementation ✅ COMPLETE

**Production-ready weather agent using OpenWeatherMap API with natural language processing:**

**Key Design Principle: Natural Language In/Out Over Data Model**
- **Input**: Natural language requests (`"weather Monument Colorado"`)
- **Processing**: Simple location extraction (no complex parsing)
- **Output**: Natural language responses (`"Current weather in Monument: clear sky, 13.3°C..."`)
- **Transport**: DDS `AgentAgentRequest`/`AgentAgentReply` data model

```python
import aiohttp
import json
import os
from typing import Dict, Any, Optional

class OpenWeatherMapAgent(MonitoredAgent):
    """
    Specialized weather agent using OpenWeatherMap API
    Perfect for testing agent-to-agent communication and classification
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            agent_name="WeatherExpert",
            base_service_name="WeatherService",
            enable_agent_communication=True
        )
        
        # Get API key from environment or parameter
        self.api_key = api_key or os.getenv('OPENWEATHERMAP_API_KEY')
        if not self.api_key:
            logger.warning("No OpenWeatherMap API key provided. Weather agent will use mock data.")
        
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_agent_capabilities(self):
        """Advertise weather-specific capabilities"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology", "climate"],
            "capabilities": [
                "current_weather",
                "weather_forecast",
                "weather_alerts",
                "temperature_check",
                "precipitation_forecast"
            ],
            "classification_tags": [
                "weather", "temperature", "rain", "snow", "storm",
                "forecast", "climate", "humidity", "wind", "pressure",
                "sunny", "cloudy", "precipitation", "conditions"
            ],
            "model_info": None,  # Not an LLM-based agent
            "default_capable": False,  # Only handles weather queries
            "performance_metrics": {
                "avg_response_time": "2-3 seconds",
                "accuracy": "Real-time data from OpenWeatherMap"
            }
        }
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process weather-related requests from other agents"""
        message = request.get('message', '')
        conversation_id = request.get('conversation_id', '')
        
        try:
            # Parse the weather request
            location = self._extract_location(message)
            weather_type = self._classify_weather_request(message)
            
            # Get weather data
            if weather_type == "current":
                weather_data = await self._get_current_weather(location)
            elif weather_type == "forecast":
                weather_data = await self._get_forecast(location)
            else:
                weather_data = await self._get_current_weather(location)
            
            return {
                'message': self._format_weather_response(weather_data, weather_type),
                'status': 0,
                'conversation_id': conversation_id,
                'metadata': {
                    'location': location,
                    'weather_type': weather_type,
                    'source': 'OpenWeatherMap'
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing weather request: {e}")
            return {
                'message': f"Sorry, I couldn't get weather information: {str(e)}",
                'status': -1,
                'conversation_id': conversation_id
            }
    
    def _extract_location(self, message: str) -> str:
        """Extract location from natural language message"""
        # Simple keyword extraction - could be enhanced with NLP
        words = message.lower().split()
        
        # Look for common location indicators
        location_indicators = ['in', 'for', 'at', 'weather']
        for i, word in enumerate(words):
            if word in location_indicators and i + 1 < len(words):
                return words[i + 1].title()
        
        # Default to a test location if none found
        return "London"
    
    def _classify_weather_request(self, message: str) -> str:
        """Classify the type of weather request"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['forecast', 'tomorrow', 'week', 'future']):
            return "forecast"
        else:
            return "current"
    
    async def _get_current_weather(self, location: str) -> Dict[str, Any]:
        """Get current weather for a location"""
        if not self.api_key:
            return self._get_mock_weather_data(location)
        
        url = f"{self.base_url}/weather"
        params = {
            'q': location,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Weather API error: {response.status}")
    
    async def _get_forecast(self, location: str) -> Dict[str, Any]:
        """Get weather forecast for a location"""
        if not self.api_key:
            return self._get_mock_forecast_data(location)
        
        url = f"{self.base_url}/forecast"
        params = {
            'q': location,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Weather API error: {response.status}")
    
    def _format_weather_response(self, weather_data: Dict[str, Any], weather_type: str) -> str:
        """Format weather data into a natural language response"""
        if weather_type == "current":
            temp = weather_data['main']['temp']
            description = weather_data['weather'][0]['description']
            location = weather_data['name']
            
            return f"Current weather in {location}: {description}, {temp}°C"
        
        elif weather_type == "forecast":
            location = weather_data['city']['name']
            forecasts = weather_data['list'][:3]  # Next 3 periods
            
            forecast_text = f"Weather forecast for {location}:\n"
            for forecast in forecasts:
                temp = forecast['main']['temp']
                desc = forecast['weather'][0]['description']
                time = forecast['dt_txt']
                forecast_text += f"- {time}: {desc}, {temp}°C\n"
            
            return forecast_text.strip()
    
    def _get_mock_weather_data(self, location: str) -> Dict[str, Any]:
        """Return mock weather data for testing without API key"""
        return {
            'name': location,
            'main': {'temp': 22.5, 'humidity': 65},
            'weather': [{'description': 'partly cloudy'}]
        }
    
    def _get_mock_forecast_data(self, location: str) -> Dict[str, Any]:
        """Return mock forecast data for testing without API key"""
        return {
            'city': {'name': location},
            'list': [
                {
                    'dt_txt': '2025-01-15 12:00:00',
                    'main': {'temp': 23.0},
                    'weather': [{'description': 'sunny'}]
                },
                {
                    'dt_txt': '2025-01-15 15:00:00', 
                    'main': {'temp': 25.5},
                    'weather': [{'description': 'partly cloudy'}]
                }
            ]
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

### 6.1 Enhanced AgentCapability Structure

The `AgentCapability` struct needs to be enhanced to support rich discovery:

```xml
<struct name="AgentCapability">
    <member name="agent_id" type="string" key="true" stringMaxLength="128"/>
    <member name="name" type="string" stringMaxLength="256"/>
    <member name="description" type="string" stringMaxLength="2048"/>
    <member name="agent_type" type="string" stringMaxLength="128"/> <!-- "general", "specialized" -->
    <member name="service_name" type="string" stringMaxLength="128"/>
    <member name="last_seen" type="int64"/>
    <!-- Enhanced fields for discovery and classification -->
    <member name="capabilities" type="string" stringMaxLength="2048"/> <!-- JSON array -->
    <member name="specializations" type="string" stringMaxLength="2048"/> <!-- Domain expertise -->
    <member name="model_info" type="string" stringMaxLength="1024"/> <!-- Model name/version -->
    <member name="classification_tags" type="string" stringMaxLength="2048"/> <!-- For routing -->
    <member name="performance_metrics" type="string" stringMaxLength="1024"/> <!-- Optional -->
    <member name="default_capable" type="int32"/> <!-- Can handle general requests -->
</struct>
```

### 6.2 Agent Classification System (PURE LLM ONLY)

**⚠️ CRITICAL: All rule-based matching removed to prevent classification bugs**

```python
class AgentClassifier:
    """
    Classify requests using PURE LLM-based semantic understanding.
    NO rule-based matching, keyword matching, or pattern matching.
    """
    
    def __init__(self, openai_api_key=None, model_name="gpt-4o-mini"):
        self.openai_client = None
        self.model_name = model_name
        self.agent_registry = {}  # agent_id -> capability info
        
        # Initialize OpenAI client for pure LLM classification
        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
    async def classify_request(self, request: str, available_agents: Dict[str, Dict]) -> Optional[str]:
        """
        Determine which agent is best suited using PURE LLM classification.
        
        Returns:
            Agent ID of best suited agent, or None if no suitable agent found
        """
        # ONLY use LLM-based semantic classification
        if self.openai_client:
            return await self._llm_classify(request, available_agents)
        else:
            # Only fallback to default capable agent if no LLM
            return self._find_default_capable_agent(available_agents)
```

### 6.3 Capability-Based Routing
```python
async def find_agent_with_capability(self, capability: str) -> Optional[str]:
    """Find an agent that advertises a specific capability"""
    for agent_id, agent_info in self.discovered_agents.items():
        capabilities = json.loads(agent_info.get('capabilities', '[]'))
        if capability in capabilities:
            return agent_id
    return None

async def find_agents_by_specialization(self, specialization: str) -> List[str]:
    """Find all agents with a specific specialization"""
    matching_agents = []
    for agent_id, agent_info in self.discovered_agents.items():
        specializations = json.loads(agent_info.get('specializations', '[]'))
        if specialization in specializations:
            matching_agents.append(agent_id)
    return matching_agents
```

### 6.4 Enhanced Agent Advertisement

Agents need to advertise their capabilities when they start:

```python
class SpecializedWeatherAgent(GenesisAgent):
    def __init__(self):
        super().__init__(
            agent_name="WeatherExpert",
            base_service_name="WeatherService",
            enable_agent_communication=True
        )
        
    def get_agent_capabilities(self):
        """Define this agent's capabilities for advertisement"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology", "climate"],
            "capabilities": [
                "current_weather",
                "weather_forecast", 
                "weather_alerts",
                "historical_weather"
            ],
            "classification_tags": [
                "weather", "temperature", "forecast",
                "rain", "snow", "storm", "climate",
                "humidity", "wind", "pressure"
            ],
            "model_info": None,  # Not an LLM-based agent
            "default_capable": False  # Only handles weather queries
        }

class GeneralPurposeAgent(GenesisAgent):
    def __init__(self, model_name="claude-3-opus"):
        super().__init__(
            agent_name="GeneralAssistant",
            base_service_name="GeneralService",
            enable_agent_communication=True
        )
        self.model_name = model_name
        
    def get_agent_capabilities(self):
        """Define general agent capabilities"""
        return {
            "agent_type": "general",
            "specializations": [],  # Can handle many topics
            "capabilities": ["general_assistance", "reasoning", "analysis"],
            "classification_tags": ["general", "assistant", "ai"],
            "model_info": {
                "model": self.model_name,
                "context_length": 200000,
                "capabilities": ["text", "code", "analysis"]
            },
            "default_capable": True  # Can handle any request
        }
```

### 6.5 Broadcast/Multicast Support
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

### 6.6 Conversation Management
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
