"""CCC ensemble — Step 4: vectorised stLearn cci.lr (spatial co-expression axis).

Directly runnable AND importable. Run the whole step in the kernel with:

    %run project/skills/ccc-stlearn/scripts/ccc_stlearn.py

or import the scorer and call it yourself:

    import sys; sys.path.insert(0, "project/skills/ccc-stlearn/scripts")
    from ccc_stlearn import run_stlearn

No `stlearn` install is needed — the statistic below is plain numpy/scipy and
reproduces stLearn v0.2.5's exact cci.lr statistic (Spearman ~1.0 vs the stock
call). There is ONE radius (`dis_mult × median_nn` from the prep JSON log — the
same 1.5 COMMOT uses). Do NOT add a second regime or change the statistic. See
ccc-stlearn.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import json
import numpy as np, pandas as pd, scanpy as sc
import scipy.sparse as sp
from sklearn.neighbors import NearestNeighbors


def _neighbour_frac_matrix(coords, dis_thr):
    """Row-normalised binary radius graph -> `frac` operator (self excluded).

    `frac @ E` gives, per spot, the fraction of its within-dis_thr neighbours expressing each
    gene. Cells with no radius neighbour are given their single nearest neighbour so the
    fraction is always defined (the stock stLearn loop crashes on such spots).
    """
    n = coords.shape[0]
    nn = NearestNeighbors(radius=dis_thr).fit(coords)
    A = nn.radius_neighbors_graph(coords, mode="connectivity").tolil()
    A.setdiag(0)
    A = A.tocsr(); A.eliminate_zeros()
    deg = np.asarray(A.sum(1)).ravel()
    iso = np.where(deg == 0)[0]
    if len(iso):
        nn1 = NearestNeighbors(n_neighbors=2).fit(coords)
        _, idx = nn1.kneighbors(coords[iso])
        A = A.tolil()
        for r, j in zip(iso, idx[:, 1]):
            A[r, j] = 1
        A = A.tocsr()
        deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1.0
    return sp.diags(1.0 / deg) @ A


def run_stlearn(adata, resource, dis_thr, threshold=0.0):
    """Vectorised stLearn cci.lr co-expression statistic -> LR-level scores."""
    coords = np.asarray(adata.obsm["spatial"], float)
    frac = _neighbour_frac_matrix(coords, dis_thr)
    genes = sorted(set(resource.ligand) | set(resource.receptor))
    Xg = adata[:, genes].X
    Xg = np.asarray(Xg.todense()) if sp.issparse(Xg) else np.asarray(Xg)
    gi = {g: j for j, g in enumerate(genes)}
    Epos = (Xg > threshold).astype(float)
    fracExpr = frac @ Epos
    rows = []
    for lig, rec in resource[["ligand", "receptor"]].itertuples(index=False):
        li, ri = gi[lig], gi[rec]
        s = Epos[:, li] * fracExpr[:, ri] + Epos[:, ri] * fracExpr[:, li]
        rows.append(dict(ligand=lig, receptor=rec, stlearn_score=float(s.sum())))
    return pd.DataFrame(rows)


def main():
    prep = json.load(open("project/outputs/logs/ccc_data_prep.json"))
    median_nn, dis_mult = prep["median_nn"], prep.get("dis_mult", 1.5)
    if median_nn is None:
        raise ValueError("median_nn is null — stLearn needs calibrated coords (see ccc-data-prep)")

    adata = sc.read_h5ad("project/outputs/ccc_base.h5ad")
    resource = pd.read_csv("project/outputs/ccc_lr_common.csv")[["ligand", "receptor"]]

    stlearn_df = run_stlearn(adata, resource, dis_thr=dis_mult * median_nn)
    stlearn_df.to_csv("project/outputs/stlearn_scores.csv", index=False)
    print(f"stLearn done — {len(stlearn_df)} LR pairs scored at dis_thr={dis_mult * median_nn:.1f}")


if __name__ == "__main__":
    main()
