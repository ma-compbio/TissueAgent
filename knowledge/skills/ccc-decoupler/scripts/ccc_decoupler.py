"""CCC ensemble — Step 5: decoupler + PROGENy (downstream-response axis).

Directly runnable AND importable. Run the whole step in the kernel with:

    %run project/skills/ccc-decoupler/scripts/ccc_decoupler.py

or import the scorer and call it yourself:

    import sys; sys.path.insert(0, "project/skills/ccc-decoupler/scripts")
    from ccc_decoupler import run_decoupler

Do NOT reimplement the receiving statistic and do NOT recompute PROGENy here (the
slimmed base no longer has the full transcriptome — read the per-cell amplitude
from obs['_dact']). The statistic is the signed, z-centred coherence
D = mean_i[z(recv)_i · z(a)_i] — it takes BOTH signs (all-positive scores mean the
statistic was changed). Use k = knn_k from the prep JSON log (6); do not raise it.
See ccc-decoupler.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import json
import numpy as np, pandas as pd, scanpy as sc
import scipy.sparse as sp
from sklearn.neighbors import NearestNeighbors


def _knn_W(coords, k=6):
    """Row-normalised kNN operator (self excluded) for the receiving statistic."""
    n = coords.shape[0]
    k = min(k, n - 1)
    nn = NearestNeighbors(n_neighbors=k + 1).fit(coords)
    _, idx = nn.kneighbors(coords)
    rows = np.repeat(np.arange(n), k)
    cols = idx[:, 1:].ravel()
    W = sp.csr_matrix((np.ones(n * k), (rows, cols)), shape=(n, n))
    d = np.asarray(W.sum(1)).ravel(); d[d == 0] = 1.0
    return sp.diags(1.0 / d) @ W


def run_decoupler(adata_slim, resource, cell_activity, k=6):
    """Per-pair downstream-response score on the LR-slimmed patch.

    cell_activity = the length-n_obs amplitude from obs['_dact'] (aligned to these cells).
        recv_i  = z(R)_i * (W @ z(L))_i;  D(pair) = mean_i[z(recv)_i * z(a)_i]
    Orthogonal to co-presence and OT because a comes from footprint genes.
    """
    coords = np.asarray(adata_slim.obsm["spatial"], float)
    W = _knn_W(coords, k)
    genes = sorted(set(resource.ligand) | set(resource.receptor))
    Xg = adata_slim[:, genes].X
    Xg = np.asarray(Xg.todense()) if sp.issparse(Xg) else np.asarray(Xg)
    mu, sd = Xg.mean(0), Xg.std(0); sd[sd == 0] = 1.0
    Z = (Xg - mu) / sd
    gi = {g: j for j, g in enumerate(genes)}
    a = np.asarray(cell_activity, float)
    za = (a - a.mean()) / (a.std() + 1e-12)
    rows = []
    for lig, rec in resource[["ligand", "receptor"]].itertuples(index=False):
        zl, zr = Z[:, gi[lig]], Z[:, gi[rec]]
        recv = zr * (W @ zl)
        rs = recv.std()
        zrecv = (recv - recv.mean()) / (rs if rs > 0 else 1.0)
        rows.append(dict(ligand=lig, receptor=rec, decoupler_score=float(np.mean(zrecv * za))))
    return pd.DataFrame(rows)


def main():
    prep = json.load(open("project/outputs/logs/ccc_data_prep.json"))
    k = prep.get("knn_k", 6)
    adata = sc.read_h5ad("project/outputs/ccc_base.h5ad")
    if "_dact" not in adata.obs:
        raise ValueError("obs['_dact'] missing — re-run ccc-data-prep (PROGENy needs full genes)")
    resource = pd.read_csv("project/outputs/ccc_lr_common.csv")[["ligand", "receptor"]]

    decoupler_df = run_decoupler(adata, resource,
                                 cell_activity=np.asarray(adata.obs["_dact"], float), k=k)
    decoupler_df.to_csv("project/outputs/decoupler_scores.csv", index=False)
    print(f"decoupler done — {len(decoupler_df)} LR pairs scored "
          f"(PROGENy footprint genes={prep.get('n_footprint_genes','?')})")


if __name__ == "__main__":
    main()
