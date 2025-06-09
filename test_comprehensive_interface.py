#!/usr/bin/env python3
"""
Simple test to verify the comprehensive test interface works correctly
"""

import sys
import os
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

async def test_interface_creation():
    """Test that we can create the comprehensive test interface"""
    try:
        from run_scripts.comprehensive_multi_agent_test_interface import ComprehensiveTestInterface
        
        print("✅ Successfully imported ComprehensiveTestInterface")
        
        # Create interface
        interface = ComprehensiveTestInterface()
        print("✅ Successfully created ComprehensiveTestInterface instance")
        
        # Test basic properties
        assert interface.interface_name == "ComprehensiveTestInterface"
        assert interface.service_name == "OpenAIAgent"
        assert len(interface.test_results) == 0  # No tests run yet
        print("✅ Interface properties are correct")
        
        # Clean up
        await interface.close()
        print("✅ Interface cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing interface: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_weather_agent_import():
    """Test that we can import the weather agent"""
    try:
        from test_functions.weather_agent import main as weather_main
        print("✅ Successfully imported weather agent")
        return True
    except Exception as e:
        print(f"❌ Error importing weather agent: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Testing Comprehensive Multi-Agent Test Components")
    print("=" * 60)
    
    results = []
    
    print("\n1. Testing Comprehensive Test Interface...")
    results.append(await test_interface_creation())
    
    print("\n2. Testing Weather Agent Import...")
    results.append(await test_weather_agent_import())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} tests passed! Components are ready.")
        return 0
    else:
        print(f"❌ {total - passed}/{total} tests failed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 