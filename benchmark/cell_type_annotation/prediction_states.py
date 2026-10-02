"""Combine canonical identity with explicit native malignancy, without truth."""

from __future__ import annotations

import pandas as pd


POLICY_ID = "ovarian-explicit-malignant-state-v1"


def apply_explicit_malignancy(
    canonical_types: pd.Series, native_states: pd.Series
) -> pd.Series:
    """Promote exact affirmative 'malignant' states; preserve every other label.

    This policy accepts already mapped types and native annotation states only.
    Missing, uncertain, negative and cancer-associated states are not affirmative.
    Callers must explicitly opt into this ovarian label contract.
    """
    if not canonical_types.index.is_unique or not canonical_types.index.equals(native_states.index):
        raise ValueError("Cell types and states must have identical, unique cell IDs")
    result = canonical_types.astype("string").copy()
    positive = native_states.astype("string").str.strip().str.casefold().eq("malignant")
    result.loc[positive.fillna(False)] = "Malignant"
    return result
