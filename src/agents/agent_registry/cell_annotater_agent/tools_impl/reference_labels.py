"""Reference target policy shared by acquisition and supervised transfer."""

import pandas as pd

REFERENCE_LABEL_POLICY = "biological_reference_targets_v1"
PLACEHOLDER_LABELS = frozenset(
    {
        "",
        "cell",
        "cells",
        "unknown",
        "unassigned",
        "unresolved",
        "other",
        "na",
        "n/a",
        "nan",
        "none",
        "not applicable",
        "not annotated",
    }
)


def biological_label_mask(labels: pd.Series) -> pd.Series:
    """Placeholder/missing labels cannot serve as supervised cell identities."""
    return ~labels.astype("string").fillna("").str.strip().str.casefold().isin(PLACEHOLDER_LABELS)
