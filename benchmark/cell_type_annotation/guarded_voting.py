"""Experimental, truth-independent acceptance rule for saved majority votes."""

from __future__ import annotations

import pandas as pd


POLICY_ID = "expression_minority_guard_v1"
DOMINANT_FRACTION = 0.8


def select_guarded_predictions(
    raw: pd.Series,
    voted: pd.Series,
    clusters: pd.Series,
    distinct_minority: pd.Series,
) -> pd.DataFrame:
    """Retain raw labels in mixed clusters and expression-supported minorities.

    This is an experimental structural rule, not a calibrated correctness claim.
    A distinct minority is defined upstream from measured expression only.
    """
    for series in [voted, clusters, distinct_minority]:
        if not raw.index.is_unique or not raw.index.equals(series.index):
            raise ValueError("All voting inputs must have identical, unique cell IDs")
        if series.isna().any():
            raise ValueError("Voting inputs cannot have missing values")
    if raw.isna().any():
        raise ValueError("Raw predictions cannot have missing values")
    if not distinct_minority.isin([True, False]).all():
        raise ValueError("Minority support must be boolean")
    groups = pd.DataFrame({"raw": raw.astype(str), "cluster": clusters.astype(str)})
    counts = groups.groupby(["cluster", "raw"]).size()
    totals = groups.groupby("cluster").size()
    dominant = groups.cluster.map(counts.groupby(level=0).max() / totals)
    for cid, member in groups.groupby("cluster", sort=False):
        proposed = voted.loc[member.index].unique()
        if len(proposed) != 1 or counts.get((cid, proposed[0]), 0) != counts.loc[cid].max():
            raise ValueError("Saved majority label must be a modal raw label in its cluster")
    reason = pd.Series("accept_majority", index=raw.index, dtype="string")
    reason.loc[dominant < DOMINANT_FRACTION] = "retain_raw_mixed_cluster"
    reason.loc[(dominant >= DOMINANT_FRACTION) & distinct_minority.astype(bool)] = (
        "retain_raw_expression_supported_minority"
    )
    selected = voted.astype("string").copy()
    selected.loc[reason.ne("accept_majority")] = raw.loc[reason.ne("accept_majority")]
    reason.loc[raw.eq(voted)] = "raw_and_majority_agree"
    return pd.DataFrame({
        "raw_prediction": raw, "majority_prediction": voted,
        "guarded_prediction": selected, "over_clustering": clusters,
        "dominant_fraction": dominant, "distinct_minority": distinct_minority,
        "selection_reason": reason,
    })
