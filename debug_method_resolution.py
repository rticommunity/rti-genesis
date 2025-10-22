#!/usr/bin/env python3
"""Debug script to verify _call_function override."""
import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(__file__))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Create an instance
agent = OpenAIGenesisAgent(
    model_name="gpt-4o",
    agent_name="DebugAgent",
    base_service_name="DebugAgentService",
    description="Debug agent"
)

print("=" * 80)
print("Method Resolution Debug")
print("=" * 80)

# Check which _call_function is bound
method = agent._call_function
print(f"agent._call_function: {method}")
print(f"Defined in: {method.__qualname__}")
print(f"Source file: {inspect.getfile(method)}")
print(f"Line number: {method.__code__.co_firstlineno}")
print()

# Check method resolution order
print("Checking each class in MRO:")
for cls in type(agent).__mro__:
    has_method = '_call_function' in cls.__dict__
    print(f"  {cls.__name__:30} has _call_function: {has_method}")
    if has_method:
        line_no = cls.__dict__['_call_function'].__code__.co_firstlineno
        print(f"    {'':30} -> Line {line_no}")

print()
print("="  * 80)

