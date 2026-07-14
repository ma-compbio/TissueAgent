"""Reference-based metrics — compare a prediction against golden ground truth.

- ``ari`` / ``f1_macro`` — discrete label agreement (cell type annotation vs golden labels).
- ``abundance_jsd`` — distributional distance between predicted and golden per-spot cell
  type abundance/proportion matrices (deconvolution).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from eval_registry.metrics import metric


@metric("ari", kind="reference_based")
def ari(pred_labels: Sequence, true_labels: Sequence) -> float:
    """Adjusted Rand Index between predicted and true label arrays (1.0 = perfect)."""
    from sklearn.metrics import adjusted_rand_score

    return float(adjusted_rand_score(list(true_labels), list(pred_labels)))


@metric("f1_macro", kind="reference_based")
def f1_macro(pred_labels: Sequence, true_labels: Sequence) -> float:
    """Macro-averaged F1 over shared label classes (handles class imbalance)."""
    from sklearn.metrics import f1_score

    return float(f1_score(list(true_labels), list(pred_labels), average="macro"))


def _align_abundance(pred: pd.DataFrame, golden: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Align two abundance frames to shared rows (spots) and columns (cell types).

    Rows/columns present in only one frame are dropped. Each row is L1-normalised into a
    proportion distribution (rows summing to 0 become uniform) so the result is comparable
    regardless of whether inputs are raw abundances or proportions.
    """
    rows = pred.index.intersection(golden.index)
    cols = pred.columns.intersection(golden.columns)
    if len(rows) == 0 or len(cols) == 0:
        raise ValueError(
            f"No shared rows/cols to compare (rows={len(rows)}, cols={len(cols)})."
        )
    p = pred.loc[rows, cols].to_numpy(dtype=float)
    g = golden.loc[rows, cols].to_numpy(dtype=float)

    def _norm(m: np.ndarray) -> np.ndarray:
        s = m.sum(axis=1, keepdims=True)
        out = np.divide(m, s, out=np.full_like(m, 1.0 / m.shape[1]), where=s > 0)
        return out

    return _norm(p), _norm(g)


@metric("abundance_jsd", kind="reference_based", higher_is_better=False)
def abundance_jsd(pred: pd.DataFrame, golden: pd.DataFrame) -> float:
    """Mean per-spot Jensen-Shannon distance between predicted and golden abundances.

    0.0 = identical compositions; 1.0 = maximally different. Lower is better.
    """
    from scipy.spatial.distance import jensenshannon

    p, g = _align_abundance(pred, golden)
    dists = [jensenshannon(p[i], g[i], base=2) for i in range(p.shape[0])]
    # jensenshannon returns nan for degenerate rows; treat as 0 contribution.
    dists = [0.0 if np.isnan(d) else float(d) for d in dists]
    return float(np.mean(dists)) if dists else float("nan")
