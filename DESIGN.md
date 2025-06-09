# Multi-Agent Example V2: Simple Genesis Demo

## Overview

This example demonstrates the core Genesis framework capabilities using a minimal multi-agent setup. It shows how to build agents that automatically discover each other and call external services.

## System Architecture

### 🏗️ **Actual Components**

1. **PersonalAssistant Agent** - OpenAI-powered assistant that can call other services
2. **Calculator Service** - Mathematical computation service (from existing Genesis services)
3. **CLI Interface** - Simple command-line interface for testing
4. **Launch Script** - Automated startup of all components

### 🔄 **Communication Flow**

```
CLI Interface (MonitoredInterface)
    ↓ discovers & connects
PersonalAssistant (OpenAIGenesisAgent)
    ↓ function calls
Calculator Service (via Genesis function discovery)
```

## Example Interactions

### 💬 **Scenario 1: Simple Conversation**
```
User: "Tell me a joke"
CLI → PersonalAssistant → OpenAI API → Response
```

### 🧮 **Scenario 2: Mathematical Calculation**
```
User: "What is 127 + 384?"
CLI → PersonalAssistant → Calculator Service → "511"
```

## Technical Implementation

### 🔧 **Genesis Framework Usage**

**PersonalAssistant**:
- Inherits from `OpenAIGenesisAgent`
- Uses `enable_agent_communication=True`
- Automatically discovers calculator service via Genesis
- Calls `await self.run()` to start RPC service

**CLI Interface**:
- Inherits from `MonitoredInterface`
- Uses built-in `available_agents` for discovery
- Uses built-in `connect_to_agent()` and `send_request()`
- No custom discovery or connection logic

**Calculator Service**:
- Uses existing `/services/calculator_service.py`
- No modifications needed - Genesis handles discovery

### 📁 **File Structure**

```
examples/MultiAgentV2/
├── agents/
│   └── personal_assistant.py     # OpenAIGenesisAgent implementation
├── test_cli.py                   # MonitoredInterface test client
├── run_multi_agent_demo.sh       # Launch script
├── README.md                     # Usage instructions
├── IMPLEMENTATION_GUIDE.md       # Technical patterns
└── IMPLEMENTATION_CHECKLIST.md   # Task tracking
```

## Success Criteria

### ✅ **Working Demo Requirements**

1. **One-Command Launch**: `./run_multi_agent_demo.sh` starts everything
2. **Automatic Discovery**: CLI finds PersonalAssistant without configuration
3. **LLM Integration**: PersonalAssistant responds to conversational queries
4. **Service Integration**: PersonalAssistant calls calculator for math
5. **Real APIs Only**: No mock data or simulated responses

### 🎯 **Demo Scenarios**

1. **Start demo script**
2. **CLI discovers PersonalAssistant**
3. **Test: "Tell me a joke"** → OpenAI response
4. **Test: "What is 127 + 384?"** → Calculator service → "511"
5. **All communication automatic** (no manual configuration)

## Implementation Notes

### ✅ **What Genesis Provides**

- **Agent Discovery**: Automatic via DDS topics
- **Function Discovery**: Automatic service detection
- **RPC Communication**: Built-in request/response
- **Monitoring**: Comprehensive event tracking
- **Error Handling**: Built-in timeouts and recovery

### ❌ **What NOT to Build**

- Custom discovery systems
- Connection managers
- Conversation managers  
- Mock data or simulation
- Manual DDS topic management

## Educational Value

This example teaches:

1. **Correct Genesis Patterns** - How to use the framework properly
2. **Agent Communication** - Real agent-to-agent and agent-to-service calls
3. **Automatic Discovery** - No configuration required
4. **LLM Integration** - OpenAI + function calling
5. **Service Integration** - Using existing Genesis services

## Target Audience

- **Genesis developers** learning the framework
- **New users** wanting to see Genesis capabilities
- **System integrators** needing multi-agent examples
- **Anyone** who wants to see "it just works" without complex setup

## Implementation Time

**Estimated**: 2-4 hours total
- PersonalAssistant: 30 minutes (copy existing pattern)  
- CLI Interface: 30 minutes (copy existing pattern)
- Launch Script: 15 minutes (standard bash script)
- Testing: 1-2 hours (verify real agent communication)
- Documentation: 30 minutes

This is a **simple, working example** that demonstrates Genesis capabilities without overengineering. 