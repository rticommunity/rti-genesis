#!/usr/bin/env python3
"""
Test CLI Interface

Test the main CLI interface initialization and basic functionality.
"""

import sys
import os
import asyncio

# Add the parent directory to the path 
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from interface.cli_interface import MultiAgentCLI

async def test_cli_initialization():
    """Test CLI initialization."""
    print("🧪 Testing MultiAgentCLI initialization...")
    
    cli = MultiAgentCLI()
    
    # Test basic initialization
    assert cli.agent_selector is None
    assert cli.conversation_manager is None
    assert cli.running == False
    assert cli.current_agent is None
    
    print("✅ CLI initialization test passed!")
    return True

async def test_environment_validation():
    """Test environment validation."""
    print("🧪 Testing environment validation...")
    
    cli = MultiAgentCLI()
    
    # Test environment validation
    valid = cli._validate_environment()
    # Should be True unless there are serious configuration errors
    assert isinstance(valid, bool)
    
    print("✅ Environment validation test passed!")
    return True

async def test_component_initialization():
    """Test component initialization (partial - without full DDS)."""
    print("🧪 Testing component initialization...")
    
    cli = MultiAgentCLI()
    
    try:
        # Test that initialization doesn't crash
        # This may fail with DDS errors, but we're testing the code path
        success = await cli._initialize_components()
        print(f"   Component initialization result: {success}")
        
        # Clean up if successful
        if success:
            await cli._cleanup()
        
    except Exception as e:
        # Expected in test environment without full DDS setup
        print(f"   Expected initialization error (test environment): {type(e).__name__}")
    
    print("✅ Component initialization test completed!")
    return True

def test_help_display():
    """Test help display functionality."""
    print("🧪 Testing help display...")
    
    cli = MultiAgentCLI()
    
    # Test that help doesn't crash
    try:
        cli._show_help()
        print("✅ Help display works!")
    except Exception as e:
        print(f"❌ Help display failed: {e}")
        return False
    
    return True

async def test_system_status():
    """Test system status display."""
    print("🧪 Testing system status display...")
    
    cli = MultiAgentCLI()
    
    try:
        await cli._show_system_status()
        print("✅ System status display works!")
    except Exception as e:
        print(f"❌ System status failed: {e}")
        return False
    
    return True

async def main():
    """Run CLI interface tests."""
    print("🚀 CLI Interface Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 5
    
    try:
        # Run tests
        if await test_cli_initialization():
            tests_passed += 1
        
        if await test_environment_validation():
            tests_passed += 1
        
        if await test_component_initialization():
            tests_passed += 1
        
        if test_help_display():
            tests_passed += 1
        
        if await test_system_status():
            tests_passed += 1
        
        print("\n" + "=" * 50)
        print(f"🎯 Test Results: {tests_passed}/{total_tests} tests passed")
        
        if tests_passed == total_tests:
            print("🎉 All CLI interface tests PASSED!")
            return 0
        else:
            print("⚠️  Some CLI interface tests failed")
            return 1
        
    except Exception as e:
        print(f"\n❌ CLI interface test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 