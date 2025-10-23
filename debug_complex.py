#!/usr/bin/env python3
"""
Debug script for the complex code block issue.
"""

import sys
import os
sys.path.append('/Users/dustinm/Projects/research/ma-lab/TissueAgent/src')

from agents.agent_registry.coding_agent.python_repl import PythonREPL
import pandas as pd
import numpy as np
import scanpy as sc
import scipy.sparse as sp

def debug_complex():
    """Debug the complex code block step by step."""
    
    # Create a mock adata object
    class MockAdata:
        def __init__(self):
            n_obs, n_vars = 100, 50
            X = np.random.poisson(5, (n_obs, n_vars))
            X = sp.csr_matrix(X)
            
            self.X = X
            self.obs = pd.DataFrame({
                'celltype_mapped_refined': np.random.choice(['T_cell', 'B_cell', 'NK_cell'], n_obs)
            })
            self.var_names = pd.Index([f'Gene_{i}' for i in range(n_vars)])
            self.raw = None
    
    repl = PythonREPL()
    repl.update_globals({
        'adata': MockAdata(),
        'pd': pd,
        'np': np,
        'sc': sc,
        'sp': sp
    })
    
    # Step 1: Define the first function
    print("Step 1: Define _nz_sample function")
    result1 = repl.run("""
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

print("_nz_sample defined")
""")
    print("Result 1:", result1)
    print("_nz_sample in globals:", '_nz_sample' in repl.globals)
    
    # Step 2: Define the second function
    print("\nStep 2: Define _assess_norm function")
    result2 = repl.run("""
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

print("_assess_norm defined")
""")
    print("Result 2:", result2)
    print("_assess_norm in globals:", '_assess_norm' in repl.globals)
    
    # Step 3: Use the functions
    print("\nStep 3: Use the functions")
    result3 = repl.run("""
norm_assess_X = _assess_norm(adata.X)
print("Function execution successful!")
print("norm_assess_X status:", norm_assess_X["status"])
""")
    print("Result 3:", result3)

if __name__ == "__main__":
    debug_complex()
