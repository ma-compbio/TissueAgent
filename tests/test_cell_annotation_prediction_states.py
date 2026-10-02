"""Regression checks for the explicit ovarian type/state scoring policy."""

import pandas as pd
import pytest

from benchmark.cell_type_annotation.prediction_states import apply_explicit_malignancy


def test_affirmative_state_and_existing_malignant_are_preserved():
    """Only explicit affirmative states override the frozen type mapping."""
    types = pd.Series(["Epithelial", "Stromal", "Malignant", "Unassigned"])
    states = pd.Series(["malignant", " MALIGNANT ", None, "malignant"])
    result = apply_explicit_malignancy(types, states)
    assert result.tolist() == ["Malignant"] * 4
    assert types.tolist() == ["Epithelial", "Stromal", "Malignant", "Unassigned"]


@pytest.mark.parametrize("state", [
    None, pd.NA, "", "non-malignant", "not malignant", "possibly malignant",
    "matrix-remodeling cancer-associated fibroblast", "hypoxic", "inflammatory",
])
def test_no_malignancy_inferred_from_other_states(state):
    """Tumor context, uncertainty and missing values cannot trigger promotion."""
    types = pd.Series(["Epithelial", "Stromal"])
    result = apply_explicit_malignancy(types, pd.Series([state, state]))
    assert result.tolist() == types.tolist()


def test_misaligned_cell_ids_are_rejected():
    """A state may never be assigned to another cell by row position."""
    with pytest.raises(ValueError, match="cell IDs"):
        apply_explicit_malignancy(
            pd.Series(["Epithelial"], index=["a"]),
            pd.Series(["malignant"], index=["b"]),
        )
