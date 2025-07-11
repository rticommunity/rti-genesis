# Genesis Memory Subsystem Implementation Guide

## Overview

The Genesis memory subsystem provides persistent conversation memory for agents, enabling them to recall information across multiple interactions. This system is designed to be pluggable, allowing different memory backends while maintaining a consistent interface.

## Architecture

### Core Components

1. **MemoryAdapter** (Interface)
   - Abstract base class defining the memory interface
   - Methods: `write()`, `retrieve()`, `summarize()`, `promote()`, `prune()`

2. **SimpleMemoryAdapter** (Implementation)
   - In-memory implementation using Python list/dict
   - Stores conversation history with metadata
   - Suitable for development and single-session use

3. **MemoryRouter** (Routing Layer)
   - Manages multiple memory backends
   - Provides intelligent routing for future multi-backend support
   - Currently routes to SimpleMemoryAdapter

### Memory Item Format

```python
{
    "item": "The actual content (user message, agent response, etc.)",
    "metadata": {
        "role": "user" | "assistant",
        "timestamp": "ISO timestamp",
        "type": "conversation" | "system" | "tool_result",
        # Additional metadata as needed
    }
}
```

## Usage

### Basic Usage

```python
from genesis_lib.memory import SimpleMemoryAdapter

# Create memory adapter
memory = SimpleMemoryAdapter()

# Store user message
memory.write("Hello, my name is Alice", metadata={"role": "user"})

# Store agent response  
memory.write("Nice to meet you, Alice!", metadata={"role": "assistant"})

# Retrieve recent conversation
recent_items = memory.retrieve(k=5)
for item in recent_items:
    print(f"{item['metadata']['role']}: {item['item']}")
```

### Agent Integration

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.memory import SimpleMemoryAdapter

# Create agent with memory
memory_adapter = SimpleMemoryAdapter()
agent = OpenAIGenesisAgent(
    agent_name="MyAgent",
    memory_adapter=memory_adapter
)

# Memory is automatically used in conversations
response = await agent.process_message("Remember my favorite color is blue")
# Agent will recall this in future conversations
```

### Memory Router Usage

```python
from genesis_lib.memory import MemoryRouter, SimpleMemoryAdapter

# Create router with default adapter
router = MemoryRouter()

# Use router like a memory adapter
router.write("Hello", metadata={"role": "user"})
items = router.retrieve(k=3)

# Register additional adapters (future)
# router.register_adapter("vector", VectorMemoryAdapter())
# router.register_adapter("graph", GraphMemoryAdapter())
```

## Implementation Details

### Memory Integration in Agents

The memory system is integrated into OpenAI Genesis agents at multiple levels:

1. **Message Processing**: Every user message and agent response is stored
2. **Context Retrieval**: Recent conversation history is retrieved and formatted for LLM context
3. **Cross-Session Persistence**: Memory persists across agent restarts (with persistent adapters)

### OpenAI Message Formatting

Memory items are converted to OpenAI-compatible message format:

```python
# Memory items
[
    {"item": "Hi", "metadata": {"role": "user"}},
    {"item": "Hello!", "metadata": {"role": "assistant"}}
]

# Converted to OpenAI format
[
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"}
]
```

### System Prompt Integration

The system prompts have been updated to inform the LLM about memory capabilities:

- **General Prompt**: Mentions external memory system for conversation history
- **Function-based Prompt**: Includes memory alongside tools and agents

## Testing

### Memory Test Suite

The memory system includes comprehensive tests:

1. **Basic Memory Test** (`run_scripts/test_agent_memory.py`)
   - Tests memory storage and retrieval
   - Validates agent identity and data recall
   - Confirms memory persistence across conversation turns

2. **Memory with Tools Test** (`run_scripts/test_memory_with_tools.py`)
   - Tests memory integration when tools are available
   - Ensures memory works correctly across different code paths
   - Validates user data recall after tool usage

3. **Interactive Memory Test** (`run_scripts/interactive_memory_test.py`)
   - Manual testing interface for memory validation
   - Real-time conversation with memory inspection
   - Useful for development and debugging

### Running Tests

```bash
# Run basic memory test
./run_scripts/run_test_agent_memory.sh

# Run memory with tools test  
python run_scripts/test_memory_with_tools.py

# Run interactive test
./run_scripts/run_interactive_memory_test.sh
```

## Configuration

### Memory Adapter Selection

```python
# Simple in-memory adapter (default)
from genesis_lib.memory import SimpleMemoryAdapter
memory = SimpleMemoryAdapter()

# Using router for future extensibility
from genesis_lib.memory import MemoryRouter
router = MemoryRouter()
memory = router.get_adapter('simple')
```

### Memory Parameters

- **Retrieval Count (k)**: Number of recent items to retrieve (default: 8)
- **Metadata**: Additional information stored with each item
- **Storage**: Currently in-memory, extensible to persistent backends

## Future Enhancements

### Planned Memory Backends

1. **Vector Stores**
   - Semantic search capabilities
   - Embedding-based retrieval
   - Integration with Pinecone, Weaviate, Chroma

2. **Graph Databases**
   - Relationship-based memory
   - Entity linking and knowledge graphs
   - Neo4j, Amazon Neptune integration

3. **Persistent Storage**
   - File-based persistence
   - Database backends (PostgreSQL, MongoDB)
   - Redis for distributed memory

### Advanced Features

1. **Memory Types**
   - Episodic memory (conversation history)
   - Semantic memory (facts and knowledge)
   - Procedural memory (skills and procedures)

2. **Memory Policies**
   - Retention policies (time-based, importance-based)
   - Compression and summarization
   - Privacy and security controls

3. **Memory Analytics**
   - Memory usage statistics
   - Retrieval performance metrics
   - Memory effectiveness analysis

## Troubleshooting

### Common Issues

1. **Memory Not Persisting**
   - Check that memory adapter is properly passed to agent
   - Verify write operations are being called
   - Ensure agent is using correct memory instance

2. **Agent Not Recalling Information**
   - Verify system prompts mention memory capabilities
   - Check memory retrieval in agent processing
   - Ensure proper message formatting for LLM

3. **Performance Issues**
   - Consider memory size limits for large conversations
   - Implement memory pruning for long-running agents
   - Use appropriate retrieval count (k parameter)

### Debug Information

Enable debug logging to trace memory operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Memory operations will be logged
memory.write("test", metadata={"role": "user"})
items = memory.retrieve(k=5)
```

## API Reference

### MemoryAdapter Interface

```python
class MemoryAdapter(ABC):
    @abstractmethod
    def write(self, item, metadata=None):
        """Store an item in memory with optional metadata."""
        
    @abstractmethod  
    def retrieve(self, query=None, k=5, policy=None):
        """Retrieve items from memory."""
        
    @abstractmethod
    def summarize(self, window=None):
        """Summarize memory contents."""
        
    @abstractmethod
    def promote(self, item_id):
        """Promote an item to higher importance."""
        
    @abstractmethod
    def prune(self, criteria=None):
        """Remove items based on criteria."""
```

### SimpleMemoryAdapter Methods

- `write(item, metadata=None)`: Store conversation item
- `retrieve(query=None, k=5, policy=None)`: Get recent items
- `summarize(window=None)`: Basic summary (stub)
- `promote(item_id)`: Promote item (stub)
- `prune(criteria=None)`: Remove items (stub)

### MemoryRouter Methods

- `get_adapter(adapter_type='default')`: Get specific adapter
- `register_adapter(adapter_type, adapter)`: Register new adapter
- `route_query(...)`: Route query to appropriate adapter
- All MemoryAdapter methods with `adapter_hint` parameter

## Examples

### Complete Agent with Memory

```python
import asyncio
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.memory import SimpleMemoryAdapter

async def main():
    # Create agent with memory
    memory = SimpleMemoryAdapter()
    agent = OpenAIGenesisAgent(
        agent_name="MemoryAgent",
        memory_adapter=memory
    )
    
    # Multi-turn conversation
    response1 = await agent.process_message("My name is Alice")
    print(f"Agent: {response1}")
    
    response2 = await agent.process_message("What's my name?")
    print(f"Agent: {response2}")  # Should recall "Alice"
    
    # Inspect memory
    items = memory.retrieve(k=10)
    for item in items:
        role = item['metadata']['role']
        content = item['item']
        print(f"{role}: {content}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Custom Memory Adapter

```python
from genesis_lib.memory import MemoryAdapter
import json

class FileMemoryAdapter(MemoryAdapter):
    def __init__(self, filename="memory.json"):
        self.filename = filename
        self._load_memory()
    
    def _load_memory(self):
        try:
            with open(self.filename, 'r') as f:
                self._store = json.load(f)
        except FileNotFoundError:
            self._store = []
    
    def _save_memory(self):
        with open(self.filename, 'w') as f:
            json.dump(self._store, f, indent=2)
    
    def write(self, item, metadata=None):
        entry = {"item": item, "metadata": metadata or {}}
        self._store.append(entry)
        self._save_memory()
    
    def retrieve(self, query=None, k=5, policy=None):
        return self._store[-k:] if k else self._store[:]
    
    def summarize(self, window=None):
        return f"Memory contains {len(self._store)} items"
    
    def promote(self, item_id):
        pass  # Implement promotion logic
    
    def prune(self, criteria=None):
        pass  # Implement pruning logic
```

## Conclusion

The Genesis memory subsystem provides a solid foundation for agent memory capabilities. The current implementation supports basic conversation memory with room for future enhancements including semantic search, persistent storage, and advanced memory management features.

For questions or contributions, please refer to the main Genesis documentation or contact the development team. 