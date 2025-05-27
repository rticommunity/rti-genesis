#!/usr/bin/env python3
"""
Simplified Graph Connectivity Test - With detailed output
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Force output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

def test_basic_imports():
    """Test if we can import required modules"""
    print("🔧 Testing basic imports...")
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        print("✅ matplotlib imported")
        
        import networkx as nx
        print("✅ networkx imported")
        
        import rti.connextdds as dds
        print("✅ RTI DDS imported")
        
        from genesis_lib.utils import get_datamodel_path
        print("✅ genesis_lib imported")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_script_exists():
    """Test if the run script exists"""
    print("🔧 Testing script existence...")
    
    script_path = Path("run_scripts/run_interface_agent_service_test.sh")
    if script_path.exists():
        print(f"✅ Script found: {script_path}")
        return True
    else:
        print(f"❌ Script not found: {script_path}")
        return False

def run_simple_test():
    """Run a simplified version of the graph test"""
    print("🚀 Starting Simple Graph Test")
    print("=" * 50)
    
    # Test 1: Basic imports
    if not test_basic_imports():
        return False
    
    # Test 2: Script exists
    if not test_script_exists():
        return False
    
    print("\n🎬 Testing scenario execution...")
    try:
        script_path = Path("run_scripts/run_interface_agent_service_test.sh")
        result = subprocess.run(
            [str(script_path)],
            cwd="run_scripts",
            timeout=20.0,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Genesis scenario executed successfully")
            print(f"Stdout length: {len(result.stdout)}")
            print(f"Stderr length: {len(result.stderr)}")
            return True
        else:
            print(f"❌ Genesis scenario failed: {result.returncode}")
            print(f"Error: {result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Genesis scenario timed out")
        return False
    except Exception as e:
        print(f"❌ Error running scenario: {e}")
        return False

if __name__ == "__main__":
    print("Simple Graph Test Starting...")
    success = run_simple_test()
    print(f"\nTest result: {'PASS' if success else 'FAIL'}")
    sys.exit(0 if success else 1) 