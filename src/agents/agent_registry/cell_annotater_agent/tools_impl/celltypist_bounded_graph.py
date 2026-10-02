"""Seeded memory-bounded CellTypist overclustering for explicit reference-trained runs."""

from pathlib import Path
import tempfile

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from sklearn.decomposition import PCA


def overcluster(query: ad.AnnData, random_state: int, directory: Path):
    """Use an expression-only HVG sample and disk-backed PCA; cluster all cells."""
    from .celltypist_annotation import _overclustering_resolution

    if query.n_obs <= 50:
        raise ValueError("CellTypist voting requires more than 50 nonzero cells")
    rows = np.linspace(0, query.n_obs - 1, min(50_000, query.n_obs), dtype=int)
    sample = ad.AnnData(
        X=query.X[rows].copy(),
        obs=pd.DataFrame(index=query.obs_names[rows]),
        var=pd.DataFrame(index=query.var_names),
    )
    sc.pp.filter_genes(sample, min_cells=5)
    sc.pp.highly_variable_genes(sample, n_top_genes=min(2500, sample.n_vars))
    selected = query.var_names.get_indexer(sample.var_names[sample.var.highly_variable])
    n_pcs = min(50, query.n_obs - 1, len(selected) - 1)
    if n_pcs < 2 or np.any(selected < 0):
        raise ValueError("Insufficient measured features for CellTypist overclustering")
    del sample
    batch = 2500
    with tempfile.TemporaryDirectory(prefix="celltypist-graph-", dir=directory) as temp:
        x = np.memmap(
            Path(temp) / "expression.f32",
            dtype="float32",
            mode="w+",
            shape=(query.n_obs, len(selected)),
        )
        for start in range(0, query.n_obs, batch):
            block = query.X[start : start + batch, selected]
            x[start : start + batch] = block.toarray() if sparse.issparse(block) else block
        means = np.zeros(len(selected), dtype=np.float64)
        squares = means.copy()
        for start in range(0, query.n_obs, batch):
            block = np.asarray(x[start : start + batch], dtype=np.float64)
            means += block.sum(axis=0)
            squares += (block * block).sum(axis=0)
        means /= query.n_obs
        scale = np.sqrt(np.maximum((squares - query.n_obs * means**2) / (query.n_obs - 1), 0))
        scale[scale == 0] = 1
        for start in range(0, query.n_obs, batch):
            x[start : start + batch] = np.clip((x[start : start + batch] - means) / scale, -10, 10)
        x.flush()
        coordinates = (
            PCA(n_components=n_pcs, svd_solver="randomized", random_state=random_state, copy=False)
            .fit_transform(x)
            .astype(np.float32)
        )
        del x
    graph = ad.AnnData(sparse.csr_matrix((query.n_obs, 1)), obs=pd.DataFrame(index=query.obs_names))
    graph.obsm["X_pca"] = coordinates
    neighbors = min(10, query.n_obs - 1)
    sc.pp.neighbors(
        graph, n_neighbors=neighbors, n_pcs=n_pcs, use_rep="X_pca", random_state=random_state
    )
    resolution = _overclustering_resolution(query.n_obs)
    sc.tl.leiden(
        graph,
        resolution=resolution,
        random_state=random_state,
        flavor="igraph",
        n_iterations=2,
        directed=False,
        key_added="over_clustering",
    )
    clusters = graph.obs.over_clustering.astype(str).to_numpy()
    return clusters, {
        "source": "expression_sampled_hvg_memmap_pca_v1",
        "random_state": random_state,
        "feature_selection_sample": len(rows),
        "n_variable_genes": len(selected),
        "n_pcs": n_pcs,
        "pca_solver": "randomized",
        "n_neighbors": neighbors,
        "resolution": resolution,
        "n_clusters": int(pd.Series(clusters).nunique()),
        "all_query_cells_clustered": True,
        "scale_zero_center": True,
        "scale_max_value": 10,
        "difference_from_native_default": "Fixed 50k expression-only HVG sample and disk-backed "
        "randomized PCA; same bounded ovarian baseline strategy",
    }
