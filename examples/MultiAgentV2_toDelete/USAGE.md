# Quick Usage Guide

## Setup
```bash
export OPENAI_API_KEY="your-api-key-here"
cd examples/MultiAgentV2
```

## Run Interactive Demo
```bash
./run_interactive_demo.sh
```

## Run Quick Test
```bash
./run_multi_agent_demo.sh
```

## What You Can Try

### In Interactive Mode:
- **"Tell me a joke"** - Conversational AI
- **"What is 123 + 456?"** - Function calling
- **"How are you today?"** - General chat
- **"Calculate 42 times 1337"** - Math operations
- **"quit"** - Exit gracefully

### Expected Behavior:
- ✅ Services start automatically
- ✅ Agent discovery happens in ~5-10 seconds  
- ✅ Math questions trigger calculator service
- ✅ Chat questions use OpenAI directly
- ✅ Clean shutdown with Ctrl+C or "quit"

This showcases the complete Genesis framework in action! 