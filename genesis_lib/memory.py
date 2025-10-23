# Copyright (c) 2025, RTI & Jason Upchurch

class MemoryAdapter:
    def write(self, item, metadata=None):
        raise NotImplementedError

    def retrieve(self, query=None, k=5, policy=None):
        raise NotImplementedError

    def summarize(self, window=None):
        pass  # Stub

    def promote(self, item_id):
        pass  # Stub

    def prune(self, criteria=None):
        pass  # Stub


class SimpleMemoryAdapter(MemoryAdapter):
    def __init__(self):
        self._store = []

    def write(self, item, metadata=None):
        self._store.append({'item': item, 'metadata': metadata})

    def retrieve(self, query=None, k=5, policy=None):
        # For now, just return the last k items
        return self._store[-k:] if k else self._store[:] 


class MemoryRouter:
    """
    Memory router for managing multiple memory backends.
    
    This is a stub implementation that currently only supports SimpleMemoryAdapter,
    but provides the foundation for future multi-backend support (vector stores,
    graph databases, external memory services, etc.).
    
    Future backends could include:
    - Vector stores (Pinecone, Weaviate, Chroma)
    - Graph databases (Neo4j, Amazon Neptune)  
    - External memory services (Redis, MongoDB)
    - Specialized memory adapters (episodic, semantic, procedural)
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
    
    def write(self, item, metadata=None, adapter_hint=None):
        """
        Write to memory through the router.
        
        Args:
            item: The item to store
            metadata: Optional metadata
            adapter_hint: Hint about which adapter to use
        """
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.write(item, metadata)
    
    def retrieve(self, query=None, k=5, policy=None, adapter_hint=None):
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
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.summarize(window)
    
    def promote(self, item_id, adapter_hint=None):
        """
        Promote a memory item through the router.
        
        Args:
            item_id: ID of item to promote
            adapter_hint: Hint about which adapter to use
        """
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.promote(item_id)
    
    def prune(self, criteria=None, adapter_hint=None):
        """
        Prune memory through the router.
        
        Args:
            criteria: Pruning criteria
            adapter_hint: Hint about which adapter to use
        """
        adapter = self.route_query(adapter_hint=adapter_hint)
        return adapter.prune(criteria) 