#!/usr/bin/env python3

print("Starting debug test...")

try:
    print("Importing modules...")
    import matplotlib
    matplotlib.use('Agg')
    import networkx as nx
    print("NetworkX imported successfully")
    
    from test_functions.test_graph_connectivity_validation import main
    print("Test module imported successfully")
    
    print("Running main test...")
    result = main()
    print(f"Test completed with result: {result}")
    
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc() 