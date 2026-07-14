"""Reference-free metrics — score a prediction without ground truth.

These standardize the ad-hoc confidence numbers currently computed inline in
``cell_annotater_agent/tools_impl/harmony_transfer.py`` (``mean_prediction_confidence``),
so the same definition is reused by benchmarks and reports.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from eval_registry.metrics import metric


@metric("mean_prediction_confidence", kind="reference_free")
def mean_prediction_confidence(confidences: Sequence[float]) -> float:
    """Mean of per-cell prediction confidences (e.g. max class probability)."""
    arr = np.asarray(confidences, dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(arr.mean())


@metric("frac_low_confidence", kind="reference_free", higher_is_better=False)
def frac_low_confidence(confidences: Sequence[float], threshold: float = 0.5) -> float:
    """Fraction of predictions below *threshold* confidence (lower is better)."""
    arr = np.asarray(confidences, dtype=float)
    if arr.size == 0:
        return float("nan")
    return float((arr < threshold).mean())
