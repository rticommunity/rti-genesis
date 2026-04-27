#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

"""
Memory Subsystem - Pluggable Memory Adapters for Genesis

This module defines the pluggable memory abstraction for Genesis agents, a minimal
in-memory default adapter used at runtime today, and a router scaffold for future
multi-backend memory.

=================================================================================================
ARCHITECTURE OVERVIEW - Components
=================================================================================================

1) MemoryAdapter (Interface)
   - Contract for memory backends.
   - Required: store(item, metadata), retrieve(query, k, policy)
   - Optional (future): summarize(window), promote(item_id), prune(criteria)

2) SimpleMemoryAdapter (ACTIVE DEFAULT)
   - Minimal, process-local, list-based memory store.
   - Used by Genesis agents today for conversation history.
   - Retrieval is last-k only; no query semantics yet.

3) MemoryRouter (Scaffolding)
   - Registry and routing shell intended to select between multiple adapters
     (e.g., vector store, graph store, Redis, etc.).
   - Not wired into agent construction today.

=================================================================================================
CURRENT RUNTIME USAGE - Where Memory Is Used Today
=================================================================================================

- GenesisAgent constructs `self.memory` as a SimpleMemoryAdapter when no custom
  adapter is provided, and uses it to:
  • retrieve the last k items to build LLM prompts
  • store each user/assistant turn after responses

- MonitoredAgent wraps memory operations (store/retrieve) to emit monitoring events.

Call Chain (simplified):
```
User Request
  → GenesisAgent.process_request()
      → self.memory.retrieve(k=...)   # conversation context
      → LLM call / tool orchestration
      → self.memory.store(user/assistant)
```

=================================================================================================
STATUS & TODO - What Is Implemented vs Stubbed
=================================================================================================

Implemented and used at runtime:
- SimpleMemoryAdapter: append-only store + last-k retrieval

Scaffolding / Not wired into runtime yet:
- MemoryRouter: registry + routing shell
- MemoryAdapter.summarize/promote/prune: method stubs

TODO markers in this file highlight the intended extension points.

=================================================================================================
EXTENSION POINTS - How To Plug In a New Adapter
=================================================================================================

1) Implement MemoryAdapter:
   - store(item, metadata), retrieve(query, k, policy) are required.
   - Optionally implement summarize/promote/prune.

2) Register with MemoryRouter (future):
   - router.register_adapter("my_store", MyAdapter(...))
   - pass adapter_hint or configure router policies to select per query.

3) Provide to agents today (no router required):
   - Pass your adapter via `memory_adapter=...` when constructing the agent.

=================================================================================================
DESIGN RATIONALE - Why a Router Exists
=================================================================================================

The router provides a single composition point for future multi-store memory
strategies (semantic vs episodic, vector vs graph, etc.) and centralized policy
application (e.g., routing by query shape, cost, or retention).
"""

class MemoryAdapter:
    """Interface for pluggable memory backends.

    Implementations must provide `store` and `retrieve`.

    Note: Higher-level operations (`summarize`, `promote`, `prune`) are
    intentionally left as stubs for future adapters (e.g., vector or graph
    stores) and are not used by the current runtime path.
    """

    def store(self, item, metadata=None):
        raise NotImplementedError

    def retrieve(self, query=None, k=100, policy=None):
        raise NotImplementedError

    def summarize(self, window=None):
        # TODO: Implement summarization policy across adapters (unused stub today)
        pass

    def promote(self, item_id):
        # TODO: Implement item promotion/pinning semantics (unused stub today)
        pass

    def prune(self, criteria=None):
        # TODO: Implement pruning/retention policy (unused stub today)
        pass


class SimpleMemoryAdapter(MemoryAdapter):
    """Minimal in-memory list-based adapter.

    This is the active default used by agents. `GenesisAgent` constructs this
    when no custom adapter is provided and uses it to store the most recent
    user/assistant turns for prompt construction.

    Characteristics:
    - Ephemeral (process-local), not persisted
    - FIFO-like retrieval of the last k items
    - No query semantics or policies yet
    """

    def __init__(self):
        self._store = []

    def store(self, item, metadata=None):
        self._store.append({'item': item, 'metadata': metadata})

    def retrieve(self, query=None, k=100, policy=None):
        # For now, just return the last k items
        return self._store[-k:] if k else self._store[:]


class MemoryRouter:
    """
    Memory router for managing multiple memory backends.
    
    Current status: Scaffolding only. It defaults to the SimpleMemoryAdapter and
    is not used by agents at runtime.
    
    Future backends could include:
    - Vector stores (Pinecone, Weaviate, Chroma)
    - Graph databases (Neo4j, Amazon Neptune)
    - External memory services (Redis, MongoDB)
    - Specialized memory adapters (episodic, semantic, procedural)

    TODO: Wire this router into agent construction once multi-backend support
    is available and routing policies are defined.
    """
    
    def __init__(self, default_adapter=None):
        """
        Initialize the memory router.
        
        Args:
            default_adapter: The default memory adapter to use. If None, creates SimpleMemoryAdapter.
        """
        self.default_adapter = default_adapter or SimpleMemoryAdapter()
        self.adapters = {
            'simple': self.default_adapter,
            'default': self.default_adapter
        }
        
    def get_adapter(self, adapter_type='default'):
        """
        Get a memory adapter by type.
        
        Args:
            adapter_type: Type of adapter to retrieve ('simple', 'default', etc.)
            
        Returns:
            MemoryAdapter instance
            
        Raises:
            ValueError: If adapter_type is not supported
        """
        if adapter_type not in self.adapters:
            raise ValueError(f"Unsupported adapter type: {adapter_type}. Available: {list(self.adapters.keys())}")
        
        return self.adapters[adapter_type]
    
    def register_adapter(self, adapter_type, adapter):
        """
        Register a new memory adapter.
        
        Args:
            adapter_type: String identifier for the adapter
            adapter: MemoryAdapter instance
        """
        if not isinstance(adapter, MemoryAdapter):
            raise TypeError("Adapter must implement MemoryAdapter interface")
        
        self.adapters[adapter_type] = adapter
    
    def route_query(self, query=None, k=5, policy=None, adapter_hint=None):
        """
        Route a query to the appropriate memory adapter.
        
        Currently just returns the default adapter, but in the future could
        implement intelligent routing based on query type, size, or other factors.
        
        Args:
            query: The query to route
            k: Number of items to retrieve
            policy: Retrieval policy
            adapter_hint: Hint about which adapter to use
            
        Returns:
            MemoryAdapter instance to use for this query
        """
        # Future routing logic could go here:
        # - Route to vector store for semantic queries
        # - Route to graph store for relationship queries  
        # - Route to episodic store for temporal queries
        # - Route based on query size, complexity, etc.
        
        if adapter_hint and adapter_hint in self.adapters:
            return self.adapters[adapter_hint]
        
        return self.default_adapter
    
    def store(self, item, metadata=None, adapter_hint=None):
        """
        Store to memory through the router.
        
        Args:
            item: The item to store
            metadata: Optional metadata
            adapter_hint: Hint about which adapter to use
        """
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.store(item, metadata)
    
    def retrieve(self, query=None, k=100, policy=None, adapter_hint=None):
        """
        Retrieve from memory through the router.
        
        Args:
            query: Optional query for retrieval
            k: Number of items to retrieve
            policy: Optional retrieval policy
            adapter_hint: Hint about which adapter to use
            
        Returns:
            List of retrieved memory items
        """
        adapter = self.route_query(query, k, policy, adapter_hint)
        return adapter.retrieve(query, k, policy)
    
    def summarize(self, window=None, adapter_hint=None):
        """
        Summarize memory through the router.
        
        Args:
            window: Optional window for summarization
            adapter_hint: Hint about which adapter to use
            
        Returns:
            Summary of memory contents
        """
        # TODO: Integrate with adapters that implement summarization (unused stub)
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.summarize(window)
    
    def promote(self, item_id, adapter_hint=None):
        """
        Promote a memory item through the router.
        
        Args:
            item_id: ID of item to promote
            adapter_hint: Hint about which adapter to use
        """
        # TODO: Integrate with adapters that implement promotion (unused stub)
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.promote(item_id)
    
    def prune(self, criteria=None, adapter_hint=None):
        """
        Prune memory through the router.
        
        Args:
            criteria: Pruning criteria
            adapter_hint: Hint about which adapter to use
        """
        # TODO: Integrate with adapters that implement pruning (unused stub)
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.prune(criteria) 