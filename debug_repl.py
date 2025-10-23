#!/usr/bin/env python3
"""
Debug script to isolate the Python REPL function definition issue.
"""

import sys
import os
sys.path.append('/Users/dustinm/Projects/research/ma-lab/TissueAgent/src')

from agents.agent_registry.coding_agent.python_repl import PythonREPL

def debug_repl():
    """Debug the Python REPL step by step."""
    
    repl = PythonREPL()
    
    # Step 1: Define a simple function
    print("Step 1: Define a simple function")
    result1 = repl.run("""
def test_func(x):
    return x * 2

print("Function defined")
""")
    print("Result 1:", result1)
    print("test_func in globals:", 'test_func' in repl.globals)
    print("test_func in locals:", 'test_func' in repl.locals)
    
    # Step 2: Try to use the function
    print("\nStep 2: Use the function")
    result2 = repl.run("""
result = test_func(5)
print("Result:", result)
""")
    print("Result 2:", result2)
    
    # Step 3: Check what's in globals
    print("\nStep 3: Check globals content")
    print("Globals keys:", list(repl.globals.keys()))
    print("Locals keys:", list(repl.locals.keys()))

if __name__ == "__main__":
    debug_repl()
