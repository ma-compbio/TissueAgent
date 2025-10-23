#!/usr/bin/env python3
"""
Test script to verify the Python REPL fix for function definitions.
"""

import sys
import os
sys.path.append('/Users/dustinm/Projects/research/ma-lab/TissueAgent/src')

from agents.agent_registry.coding_agent.python_repl import PythonREPL
import pandas as pd
import numpy as np
import scanpy as sc
import scipy.sparse as sp

def test_function_definitions():
    """Test the Python REPL with function definitions in code blocks."""
    
    # Create a mock adata object
    class MockAdata:
        def __init__(self):
            # Create mock data
            n_obs, n_vars = 100, 50
            X = np.random.poisson(5, (n_obs, n_vars))
            X = sp.csr_matrix(X)
            
            self.X = X
            self.obs = pd.DataFrame({
                'celltype_mapped_refined': np.random.choice(['T_cell', 'B_cell', 'NK_cell'], n_obs)
            })
            self.var_names = pd.Index([f'Gene_{i}' for i in range(n_vars)])
            self.raw = None
    
    # Initialize the Python REPL
    repl = PythonREPL()
    
    # Set up the mock adata in the REPL's global namespace
    repl.update_globals({
        'adata': MockAdata(),
        'pd': pd,
        'np': np,
        'sc': sc,
        'sp': sp
    })
    
    # The problematic code block
    test_code = """
import numpy as np
import scanpy as sc
import scipy.sparse as sp

qc_info = {}

adata_raw = adata.raw.to_adata() if adata.raw is not None else None
qc_info["raw_available"] = adata_raw is not None

def _nz_sample(X, n=50000):
    if sp.issparse(X):
        d = X.data
        if d.size == 0:
            return np.array([])
        idx = np.random.choice(d.size, size=min(n, d.size), replace=False)
        return d[idx]
    arr = np.asarray(X)
    flat = arr.ravel()
    nz = flat[flat != 0]
    if nz.size == 0:
        return np.array([])
    idx = np.random.choice(nz.size, size=min(n, nz.size), replace=False)
    return nz[idx]

def _assess_norm(X):
    vals = _nz_sample(X, n=50000)
    if vals.size == 0:
        return {"status":"unknown_no_nonzero","q99":None,"frac_nonint":None,"max":None,"dtype":str(getattr(X,"dtype",type(X)))}
    q99 = float(np.quantile(vals, 0.99))
    mx = float(np.max(vals))
    frac_nonint = float(np.mean(~np.isclose(vals, np.round(vals))))
    status = "ambiguous"
    if frac_nonint > 0.2 and q99 <= 20.0:
        status = "likely_log_normalized"
    elif frac_nonint <= 0.05 and (q99 > 50.0 or mx > 100.0):
        status = "likely_counts"
    return {"status":status,"q99":q99,"frac_nonint":frac_nonint,"max":mx,"dtype":str(getattr(X,"dtype",type(X)))}

norm_assess_X = _assess_norm(adata.X)
print("Function definitions and execution successful!")
print("norm_assess_X status:", norm_assess_X["status"])
"""
    
    print("Testing Python REPL with function definitions...")
    print("=" * 60)
    
    try:
        # Test without timeout (direct execution)
        print("Testing direct execution (no timeout):")
        result1 = repl.run(test_code)
        print("SUCCESS: Direct execution worked!")
        print("Output:", result1)
        
        # Test with timeout (multiprocessing)
        print("\nTesting with timeout (multiprocessing):")
        result2 = repl.run(test_code, timeout=30)
        print("SUCCESS: Multiprocessing execution worked!")
        print("Output:", result2)
        
        # Check if functions are available
        print("\nChecking function availability:")
        print("_nz_sample available:", '_nz_sample' in repl.globals)
        print("_assess_norm available:", '_assess_norm' in repl.globals)
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_function_definitions()
    if success:
        print("\n✅ Python REPL function definition test PASSED")
    else:
        print("\n❌ Python REPL function definition test FAILED")
        sys.exit(1)
