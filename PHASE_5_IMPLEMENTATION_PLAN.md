# Phase 5 Implementation Plan: Multi-Agent System with LLM Integration

## Current Status: Phase 5B Complete, Phase 5C In Progress ⚠️

### Completed:
- ✅ Phase 5A: Weather Agent Implementation (COMPLETE)
- ✅ Phase 5B: Multi-Agent Integration (COMPLETE)
- 🚧 Phase 5C: Comprehensive Chaining Tests (IN PROGRESS)

## Phase 5C: Comprehensive Chaining Tests (NEW - REQUIRED FOR COMPLETION)

### Overview
Implement and validate ALL multi-agent communication chains with REAL APIs and services. NO MOCK DATA allowed in final tests.

### Required Chain Patterns to Test:

#### 1. Sequential Agent Chain
**Pattern**: Interface → Agent A → Agent B → Service → Function
**Example**: "Ask the general agent to consult the weather specialist about Denver's weather, then calculate the temperature difference from freezing"
- Interface sends to OpenAI Agent
- OpenAI Agent routes to Weather Agent  
- Weather Agent gets real weather from OpenWeatherMap API
- Result passed back to OpenAI Agent
- OpenAI Agent calls Calculator Service
- Calculator performs real calculation
- Full chain result returned to Interface

#### 2. Parallel Agent Execution
**Pattern**: Interface → Agent → Multiple Agents in parallel → Multiple Services
**Example**: "Get weather for Denver AND New York, then calculate the temperature difference between them"
- Interface sends to OpenAI Agent
- OpenAI Agent spawns parallel requests:
  - Weather Agent → OpenWeatherMap API (Denver)
  - Weather Agent → OpenWeatherMap API (New York)
- Both results collected by OpenAI Agent
- OpenAI Agent → Calculator Service (temperature difference)
- Aggregated result returned to Interface

#### 3. Context-Preserving Agent Chain
**Pattern**: Interface → Agent → Agent (with context) → Agent → Service
**Example**: "Ask about Denver weather, remember that, then ask what clothes to pack, then calculate how many days until the weekend"
- Interface starts conversation with OpenAI Agent
- OpenAI Agent → Weather Agent (Denver weather)
- Context preserved in conversation_id
- OpenAI Agent → Fashion Agent (clothing recommendations based on weather context)
- OpenAI Agent → Calculator Service (days calculation)
- Full contextual response returned

### Implementation Requirements:

#### 1. Agent-as-Tool Pattern Implementation
```python
# In OpenAIGenesisAgent._ensure_agents_discovered():
def _convert_agents_to_tools(self, discovered_agents):
    """Convert discovered agents into OpenAI tool schemas"""
    agent_tools = []
    for agent_id, agent_info in discovered_agents.items():
        tool = {
            "type": "function", 
            "function": {
                "name": f"consult_{agent_info['prefered_name'].lower()}",
                "description": f"Consult {agent_info['prefered_name']} agent: {agent_info.get('description', '')}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": f"Question or request for {agent_info['prefered_name']}"
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context from previous interactions"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
        agent_tools.append(tool)
    return agent_tools
```

#### 2. Test Script Requirements

##### File: `run_scripts/comprehensive_chaining_test.sh`
```bash
#!/bin/bash
# Comprehensive Multi-Agent Chaining Test
# CRITICAL: NO MOCK DATA ALLOWED - ALL REAL APIs

# Environment validation
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ FATAL: OPENAI_API_KEY required for real LLM"
    exit 1
fi

if [ -z "$OPENWEATHERMAP_API_KEY" ]; then
    echo "❌ FATAL: OPENWEATHERMAP_API_KEY required for real weather"
    exit 1
fi

# Start services and agents
# 1. Calculator Service (real calculations)
# 2. Weather Agent (real OpenWeatherMap API)
# 3. Fashion Agent (new - clothing recommendations)
# 4. OpenAI Agent (with agent-as-tool enabled)
# 5. Test Interface with chain scenarios
```

##### File: `run_scripts/comprehensive_chaining_interface.py`
```python
class ComprehensiveChainingInterface(MonitoredInterface):
    """Test interface for comprehensive agent chains"""
    
    async def test_sequential_chain(self):
        """Test: Interface → Agent A → Agent B → Service → Function"""
        request = {
            "message": "Ask the weather specialist about Denver's current temperature, then calculate how many degrees above freezing it is",
            "conversation_id": "seq_chain_001"
        }
        # Validate full chain execution
        
    async def test_parallel_execution(self):
        """Test: Interface → Agent → Multiple Agents → Multiple Services"""
        request = {
            "message": "Get the current weather in Denver, New York, and London simultaneously, then calculate the average temperature",
            "conversation_id": "parallel_001"
        }
        # Validate parallel agent calls
        
    async def test_context_preservation(self):
        """Test: Multi-hop with context preservation"""
        # Step 1: Get weather
        # Step 2: Get clothing recommendations based on weather
        # Step 3: Calculate travel metrics
        # Validate context flows through chain
```

#### 3. New Agent Implementation

##### File: `test_functions/fashion_agent.py`
```python
class FashionAgent(MonitoredAgent):
    """Agent for clothing/fashion recommendations"""
    
    def __init__(self):
        super().__init__(
            agent_name="FashionExpert",
            base_service_name="FashionService",
            agent_type="SPECIALIZED_AGENT",
            enable_agent_communication=True
        )
        
    async def process_request(self, request):
        """Process fashion/clothing requests with weather context"""
        # Real logic based on weather conditions
```

### Validation Criteria:

1. **No Mock Data**:
   - ALL API calls must be real
   - ALL calculations must be real
   - ALL agent responses must be from real LLMs
   - Test fails if ANY mock data detected

2. **Chain Validation**:
   - Each hop in chain must be traceable via monitoring events
   - Context must be preserved across hops
   - Parallel executions must complete concurrently
   - Error propagation must work through chains

3. **Performance Metrics**:
   - Sequential chain < 30 seconds
   - Parallel execution shows concurrency benefit
   - Context preservation adds < 10% overhead

### Updated Components Checklist:

#### OpenAI Agent Enhancements:
- [ ] Implement `_ensure_agents_discovered()` method
- [ ] Implement `_convert_agents_to_tools()` method  
- [ ] Modify LLM call to include both function AND agent tools
- [ ] Handle agent tool calls via agent-to-agent communication
- [ ] Preserve context across agent calls

#### Test Infrastructure:
- [ ] Create `comprehensive_chaining_test.sh`
- [ ] Create `ComprehensiveChainingInterface` class
- [ ] Implement all three chain pattern tests
- [ ] Add validation for no mock data
- [ ] Add chain event validation

#### New Agents:
- [ ] Implement Fashion Agent (or other domain agent)
- [ ] Ensure agent-to-agent communication enabled
- [ ] Implement context-aware processing

#### Monitoring Enhancements:
- [ ] Validate AGENT_TO_AGENT edges in chains
- [ ] Track conversation_id through chains
- [ ] Measure chain execution timing
- [ ] Detect and report mock data usage

## Success Criteria for Phase 5 Completion:

1. **All Chain Patterns Working**:
   - Sequential chains execute correctly
   - Parallel chains show concurrency
   - Context preserved across hops

2. **Real APIs Only**:
   - OpenAI API for all LLM calls
   - OpenWeatherMap API for weather
   - Real calculations in calculator
   - No mock data in final tests

3. **Monitoring Complete**:
   - All hops visible in monitoring
   - Chain events track full flow
   - Performance metrics captured

4. **Error Handling**:
   - Errors propagate correctly
   - Partial failures handled
   - Timeouts work at each hop

## Next Steps:

1. Implement agent-as-tool pattern in OpenAI Agent
2. Create comprehensive chaining test script
3. Implement test interface with chain scenarios
4. Add third specialized agent (Fashion or similar)
5. Run full validation suite
6. Document chain execution patterns

Only when ALL these tests pass with REAL APIs can Phase 5 be considered complete. 