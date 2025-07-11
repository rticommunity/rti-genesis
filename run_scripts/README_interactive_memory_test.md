# Interactive Memory Test - Genesis Agent Memory System

This interactive CLI allows users to manually test the memory functionality of Genesis agents. It demonstrates how agents can maintain conversation context across multiple turns using the pluggable memory system.

## Features

- **Direct interaction** with OpenAI Genesis Agent
- **Memory persistence** across conversation turns
- **Memory content inspection** to see what the agent remembers
- **Memory management** with clear functionality
- **Clear demonstration** of memory recall capabilities

## Usage

### Option 1: Shell Script (Recommended)
```bash
cd run_scripts
./run_interactive_memory_test.sh
```

### Option 2: Direct Python
```bash
cd run_scripts
python interactive_memory_test.py
```

The shell script wrapper provides cleaner output by suppressing some DDS initialization messages.

## Commands

During the conversation, you can use these special commands:

- **Type any message** - Chat with the agent normally
- **`memory`** - Inspect current memory contents
- **`clear`** - Clear all memory
- **`help`** - Show help information
- **`exit`** or **`quit`** - End the session

## Suggested Test Scenarios

Try these scenarios to test memory functionality:

1. **Agent Identity Test:**
   ```
   You: What kind of agent are you?
   ```

2. **Basic Memory Storage:**
   ```
   You: My favorite color is blue. Remember this.
   ```

3. **Memory Recall:**
   ```
   You: What is my favorite color?
   ```

4. **Multiple Facts:**
   ```
   You: My birthday is March 15th. Please remember.
   You: I work as a software engineer.
   You: What do you remember about me?
   ```

5. **Memory Inspection:**
   ```
   You: memory
   ```

6. **Memory Clearing:**
   ```
   You: clear
   You: What do you remember about me?
   ```

## How It Works

The interactive test uses the same memory system as the automated tests:

1. **Memory Integration**: The agent uses `SimpleMemoryAdapter` to store conversation history
2. **Context Replay**: Each OpenAI API call includes the full conversation history from memory
3. **Persistent Context**: The agent can recall information from any point in the conversation
4. **Role-based Storage**: Messages are stored with proper roles (`user`, `assistant`)

## Example Session

```
🧠 Genesis Agent Memory Test - Interactive CLI
==================================================

🎯 This demo showcases:
   • Agent memory persistence across conversation turns
   • Context recall from previous messages
   • Memory content inspection and management
   • Genesis agent identity and capabilities

🚀 Ready to test memory capabilities!
==================================================

You: What kind of agent are you?
🤖 Agent: I am a Genesis agent, part of the Genesis distributed agent framework. I have memory capabilities and can recall previous conversations perfectly. How can I assist you today?

You: My favorite number is 42. Please remember this.
🤖 Agent: Got it! I'll remember that your favorite number is 42. Is there anything else you'd like me to remember or help you with?

You: What is my favorite number?
🤖 Agent: Your favorite number is 42, as you told me earlier. I have that stored in my memory from our conversation.

You: memory
📝 Current Memory Contents:
----------------------------------------
 1. [user     ] What kind of agent are you?
 2. [assistant] I am a Genesis agent, part of the Genesis distributed agent framework...
 3. [user     ] My favorite number is 42. Please remember this.
 4. [assistant] Got it! I'll remember that your favorite number is 42...
 5. [user     ] What is my favorite number?
 6. [assistant] Your favorite number is 42, as you told me earlier...
----------------------------------------
Total memory items: 6

You: exit
👋 Goodbye! Thanks for testing Genesis memory!
```

## Technical Details

- **Agent Class**: Uses `OpenAIGenesisAgent` with memory adapter
- **Memory Backend**: `SimpleMemoryAdapter` (in-memory storage)
- **LLM Model**: GPT-4o for conversation, GPT-4o-mini for classification
- **Memory Format**: OpenAI-compatible message format with roles
- **Context Window**: Retrieves last 8 conversation turns by default

## Notes

- This is for **interactive testing only** and is not included in the automated test suite
- Requires `OPENAI_API_KEY` environment variable to be set
- Memory is cleared when the session ends
- Some DDS initialization messages may appear during startup (this is normal)
- DDS cleanup warnings at exit are expected and don't affect functionality
- Use the shell script wrapper (`./run_interactive_memory_test.sh`) for the cleanest experience 