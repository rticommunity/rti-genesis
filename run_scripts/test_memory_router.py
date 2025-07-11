#!/usr/bin/env python3
"""
Test script for Genesis MemoryRouter functionality.

This script tests the MemoryRouter stub implementation to ensure it properly
routes to the SimpleMemoryAdapter and provides the foundation for future
multi-backend support.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.memory import MemoryRouter, SimpleMemoryAdapter

def test_memory_router():
    """Test basic MemoryRouter functionality."""
    print("🧪 Testing MemoryRouter functionality...")
    
    # Test 1: Basic router creation
    print("1. Creating MemoryRouter...")
    router = MemoryRouter()
    assert router is not None
    print("   ✅ Router created successfully")
    
    # Test 2: Default adapter access
    print("2. Testing default adapter access...")
    default_adapter = router.get_adapter('default')
    assert default_adapter is not None
    assert isinstance(default_adapter, SimpleMemoryAdapter)
    print("   ✅ Default adapter retrieved successfully")
    
    # Test 3: Simple adapter access
    print("3. Testing simple adapter access...")
    simple_adapter = router.get_adapter('simple')
    assert simple_adapter is not None
    assert isinstance(simple_adapter, SimpleMemoryAdapter)
    print("   ✅ Simple adapter retrieved successfully")
    
    # Test 4: Write through router
    print("4. Testing write through router...")
    router.write("Hello from router", metadata={"role": "user"})
    router.write("Router response", metadata={"role": "assistant"})
    print("   ✅ Write operations completed")
    
    # Test 5: Retrieve through router
    print("5. Testing retrieve through router...")
    items = router.retrieve(k=5)
    assert len(items) == 2
    assert items[0]["item"] == "Hello from router"
    assert items[0]["metadata"]["role"] == "user"
    assert items[1]["item"] == "Router response"
    assert items[1]["metadata"]["role"] == "assistant"
    print(f"   ✅ Retrieved {len(items)} items successfully")
    
    # Test 6: Router query routing
    print("6. Testing query routing...")
    adapter = router.route_query(query="test query", k=3)
    assert adapter is not None
    assert isinstance(adapter, SimpleMemoryAdapter)
    print("   ✅ Query routing working correctly")
    
    # Test 7: Adapter registration
    print("7. Testing adapter registration...")
    custom_adapter = SimpleMemoryAdapter()
    router.register_adapter("custom", custom_adapter)
    retrieved_adapter = router.get_adapter("custom")
    assert retrieved_adapter is custom_adapter
    print("   ✅ Custom adapter registered and retrieved successfully")
    
    # Test 8: Adapter hint routing
    print("8. Testing adapter hint routing...")
    router.write("Custom message", metadata={"role": "user"}, adapter_hint="custom")
    custom_items = custom_adapter.retrieve(k=5)
    assert len(custom_items) == 1
    assert custom_items[0]["item"] == "Custom message"
    print("   ✅ Adapter hint routing working correctly")
    
    # Test 9: Error handling
    print("9. Testing error handling...")
    try:
        router.get_adapter("nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported adapter type" in str(e)
        print("   ✅ Error handling working correctly")
    
    # Test 10: Invalid adapter registration
    print("10. Testing invalid adapter registration...")
    try:
        router.register_adapter("invalid", "not_an_adapter")
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "must implement MemoryAdapter interface" in str(e)
        print("    ✅ Invalid adapter registration properly rejected")
    
    print("\n🎉 All MemoryRouter tests passed!")
    return True

def test_router_with_custom_default():
    """Test MemoryRouter with custom default adapter."""
    print("\n🧪 Testing MemoryRouter with custom default adapter...")
    
    # Create custom adapter with some data
    custom_default = SimpleMemoryAdapter()
    custom_default.write("Pre-loaded message", metadata={"role": "system"})
    
    # Create router with custom default
    router = MemoryRouter(default_adapter=custom_default)
    
    # Verify the custom adapter is used
    items = router.retrieve(k=5)
    assert len(items) == 1
    assert items[0]["item"] == "Pre-loaded message"
    
    print("   ✅ Custom default adapter working correctly")
    return True

def main():
    """Run all memory router tests."""
    try:
        print("🚀 Starting Genesis MemoryRouter Tests")
        print("=" * 50)
        
        # Run tests
        test_memory_router()
        test_router_with_custom_default()
        
        print("\n" + "=" * 50)
        print("✅ ALL MEMORY ROUTER TESTS PASSED!")
        print("🎯 MemoryRouter is ready for future multi-backend support")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main()) 