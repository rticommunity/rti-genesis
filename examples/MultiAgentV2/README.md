# Genesis Multi-Agent Demo V2

A complete demonstration of the Genesis framework's multi-agent capabilities, featuring real agent-to-agent communication, function calling, and interactive chat.

## Features

- **🤖 Real AI Agent**: PersonalAssistant powered by OpenAI GPT models
- **🔧 Function Services**: Calculator service for mathematical operations
- **💬 Interactive Chat**: Smooth conversational interface
- **🔍 Auto-Discovery**: Agents and services discover each other automatically
- **📊 Full Monitoring**: Complete Genesis framework monitoring and logging
- **🚀 One-Click Launch**: Everything starts with a single command

## Quick Start

### Prerequisites

1. **OpenAI API Key**: Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

2. **Python Environment**: Ensure you're in the Genesis virtual environment:
   ```bash
   # From Genesis_LIB root directory
   source venv/bin/activate
   ```

3. **Directory**: Navigate to this demo directory:
   ```bash
   cd examples/MultiAgentV2
   ```

## Running the Demo

### Option 1: Quick Test (Automated)

Run the automated test that demonstrates all features:

```bash
./run_multi_agent_demo.sh
```

This will:
- Start calculator service
- Start PersonalAssistant agent
- Run automated tests (joke request, math calculation)
- Show the complete interaction flow
- Clean up automatically

### Option 2: Interactive Chat (Manual)

Have a real conversation with the PersonalAssistant:

```bash
./run_interactive_demo.sh
```

This will:
- Start calculator service and PersonalAssistant
- Launch an interactive chat interface
- Let you have real conversations with the AI agent
- Allow you to request calculations that use the function service
- Provide a conversation summary when you exit

#### Interactive Demo Usage

Once the interactive demo starts, you can:

- **Ask questions**: "What's the capital of France?"
- **Request jokes**: "Tell me a funny joke"
- **Do math**: "What is 123 multiplied by 456?"
- **Have conversations**: "How are you today?"
- **Exit gracefully**: Type `quit`, `exit`, or `bye`

Example conversation:
```
You: Tell me a joke about programming
PersonalAssistant: Why do programmers prefer dark mode? Because light attracts bugs! 😄

You: What is 42 times 1337?
PersonalAssistant: Let me calculate that for you. 42 × 1337 = 56,154

You: quit
👋 Thanks for chatting! Goodbye!
```

## What's Happening Under the Hood

### Agent Architecture

1. **PersonalAssistant** (`agents/personal_assistant.py`)
   - OpenAI GPT-powered conversational agent
   - Automatically discovers and calls calculator functions
   - Handles both chat and functional requests
   - Uses Genesis framework for all communication

2. **Calculator Service** (`../../test_functions/calculator_service.py`)
   - Provides mathematical functions (add, subtract, multiply, divide)
   - Automatically advertises capabilities via Genesis
   - Handles concurrent requests from multiple agents

### Genesis Framework Features Demonstrated

- **🔍 Service Discovery**: Agents automatically find available functions
- **🤖 Agent Communication**: Real AI agent powered by OpenAI
- **🔧 Function Calling**: LLM automatically calls calculator when needed
- **📊 Monitoring**: Complete event tracking and lifecycle management
- **🚀 RPC Services**: High-performance DDS-based communication
- **🔗 Connection Management**: Automatic connection handling and recovery

### Technical Flow

1. **Startup**: Services start and announce their capabilities
2. **Discovery**: PersonalAssistant discovers calculator functions
3. **Connection**: Interactive CLI discovers and connects to PersonalAssistant
4. **Conversation**: User interacts with AI agent naturally
5. **Function Calls**: Agent automatically calls calculator when needed
6. **Monitoring**: All interactions tracked by Genesis monitoring system

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Interactive CLI │◄──►│ PersonalAssistant│◄──►│Calculator Service│
│                 │    │    (OpenAI)      │    │   (Math Funcs)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │              ┌─────────▼─────────┐              │
         └─────────────►│  Genesis Framework │◄─────────────┘
                        │  (DDS, Discovery,  │
                        │   Monitoring)      │
                        └────────────────────┘
```

## Files

- `run_multi_agent_demo.sh` - Automated test demonstration
- `run_interactive_demo.sh` - Interactive chat launcher  
- `interactive_cli.py` - Smooth conversational interface
- `test_cli.py` - Automated test client
- `agents/personal_assistant.py` - AI agent implementation
- `README.md` - This documentation
- `IMPLEMENTATION_CHECKLIST.md` - Development tracking

## Troubleshooting

### Common Issues

1. **"No agents discovered"**
   - Ensure OpenAI API key is set: `echo $OPENAI_API_KEY`
   - Check that you're in the correct directory
   - Wait a few more seconds for discovery to complete

2. **"Calculator service not found"**
   - Ensure you're running from `examples/MultiAgentV2/`
   - Check that `../../test_functions/calculator_service.py` exists

3. **Connection timeouts**
   - Services might need more time to start
   - Try running the demo again
   - Check for any error messages in the logs

4. **OpenAI API errors**
   - Verify your API key is valid and has credits
   - Check your internet connection
   - Ensure the API key has the necessary permissions

### Getting Help

If you encounter issues:

1. Check the error messages - they're designed to be helpful
2. Look at the detailed logs during startup
3. Ensure all prerequisites are met
4. Try the quick test first, then the interactive demo

## Example Interactions

The PersonalAssistant can handle:

- **Conversational requests**: General chat, questions, jokes
- **Mathematical operations**: Any calculation using the calculator service
- **Mixed conversations**: Combining chat and calculations naturally

The agent automatically determines when to use functions vs. conversational AI, providing a seamless experience that showcases the full power of the Genesis framework.

## Success Criteria

✅ **This demo successfully shows**:
- Real AI agents powered by OpenAI
- Automatic service discovery and function calling
- Interactive user experience with live conversation
- Complete Genesis framework integration
- Production-ready patterns for multi-agent systems

This demonstrates how Genesis enables building sophisticated AI systems that just work, with no manual configuration or complex setup required.