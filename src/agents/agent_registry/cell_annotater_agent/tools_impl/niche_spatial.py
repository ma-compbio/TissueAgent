"""Spatial evidence for niche annotation, computed only from the supplied AnnData."""

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


MAX_DIRECTED_EDGES = 20_000_000


class RadiusGraphLimitError(ValueError):
    """Report an oversized candidate before allocating its spatial graph."""

    def __init__(self, radius: float, estimated_edges: int, edge_limit: int):
        """Retain the resource estimate for per-candidate inspection results."""
        self.radius = radius
        self.estimated_edges = estimated_edges
        self.edge_limit = edge_limit
        super().__init__(
            f"Candidate radius {radius:g} creates {estimated_edges:,} directed edges in one "
            f"section, exceeding the {edge_limit:,}-edge resource limit. "
            "Inspect another feasible radius or use a bounded neighborhood backend."
        )


def radius_graph(adata, spatial_key: str, slide_key: str | None, radius: float):
    """Build a sparse non-self radius graph without joining independent sections."""
    if not np.isfinite(radius) or radius <= 0:
        raise ValueError("Neighborhood radius must be finite and positive.")
    coords = np.asarray(adata.obsm[spatial_key], dtype=float)[:, :2]
    groups = adata.obs[slide_key].astype(str) if slide_key else np.repeat("sample", adata.n_obs)
    rows, cols = [], []
    for group in np.unique(groups):
        positions = np.flatnonzero(np.asarray(groups) == group)
        tree = cKDTree(coords[positions])
        degrees = tree.query_ball_point(coords[positions], radius, return_length=True) - 1
        estimated_edges = int(degrees.sum())
        if estimated_edges > MAX_DIRECTED_EDGES:
            raise RadiusGraphLimitError(radius, estimated_edges, MAX_DIRECTED_EDGES)
        pairs = tree.query_pairs(radius, output_type="ndarray")
        rows.extend([positions[pairs[:, 0]], positions[pairs[:, 1]]])
        cols.extend([positions[pairs[:, 1]], positions[pairs[:, 0]]])
    row, col = np.concatenate(rows), np.concatenate(cols)
    return sparse.csr_matrix(
        (np.ones(len(row), dtype=np.float32), (row, col)), shape=(adata.n_obs, adata.n_obs)
    )


def graph_diagnostics(graph) -> dict:
    """Describe neighborhood scale without imposing a biologically optimal value."""
    degree = np.diff(graph.indptr)
    count, membership = connected_components(graph, directed=False)
    sizes = np.bincount(membership)
    return {
        "n_cells": graph.shape[0],
        "mean_nonself_neighbors": float(degree.mean()),
        "neighbor_quantiles": dict(
            zip(
                ["min", "p25", "median", "p75", "p95", "max"],
                np.quantile(degree, [0, 0.25, 0.5, 0.75, 0.95, 1]).tolist(),
                strict=True,
            )
        ),
        "isolated_fraction": float(np.mean(degree == 0)),
        "connected_components": int(count),
        "largest_component_fraction": float(sizes.max() / graph.shape[0]),
    }


def _composition(values, weights=None, top_n=8) -> dict:
    counts = (
        pd.Series(np.ones(len(values)) if weights is None else weights)
        .groupby(np.asarray(values))
        .sum()
        .sort_values(ascending=False)
    )
    if counts.sum() == 0:
        return {}
    return {
        str(key): round(float(value / counts.sum()), 4) for key, value in counts.head(top_n).items()
    }


def spatial_niche_evidence(adata, niche_key, celltype_key, spatial_key, slide_key, radius):
    """Summarize cluster extent, spatial components, and neighboring populations."""
    graph = radius_graph(adata, spatial_key, slide_key, radius)
    labels = adata.obs[niche_key].astype(str).to_numpy()
    celltypes = adata.obs[celltype_key].astype(str).to_numpy() if celltype_key else None
    coords = np.asarray(adata.obsm[spatial_key])[:, :2]
    overview, clusters = [], {}
    for label in np.unique(labels):
        mask = labels == label
        count, membership = connected_components(graph[mask][:, mask], directed=False)
        sizes = np.bincount(membership)
        neighbor_weights = np.asarray(graph[mask].sum(axis=0)).ravel()
        info = {
            "n_cells": int(mask.sum()),
            "coordinate_min": coords[mask].min(axis=0).tolist(),
            "coordinate_max": coords[mask].max(axis=0).tolist(),
            "spatial_components": int(count),
            "largest_component_fraction": float(sizes.max() / mask.sum()),
            "neighbor_cluster_fractions": _composition(labels, neighbor_weights),
            "neighbor_celltype_fractions": (
                _composition(celltypes, neighbor_weights) if celltypes is not None else {}
            ),
        }
        overview.append(
            {
                "cluster": str(label),
                "n_cells": info["n_cells"],
                "centroid": coords[mask].mean(axis=0).tolist(),
                "celltype_fractions": _composition(celltypes[mask])
                if celltypes is not None
                else {},
            }
        )
        clusters[str(label)] = info
    return {
        "radius": radius,
        "graph": graph_diagnostics(graph),
        "cluster_overview": overview,
        "clusters": clusters,
    }
