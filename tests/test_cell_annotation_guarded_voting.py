"""Checks for a fixed voting safeguard independent of query ground truth."""

import pandas as pd
import pytest

from benchmark.cell_type_annotation.guarded_voting import select_guarded_predictions


def test_mixed_cluster_keeps_individual_predictions():
    """A 60 percent plurality does not authorize replacement."""
    raw = pd.Series(["A", "A", "A", "B", "B"])
    result = select_guarded_predictions(
        raw, pd.Series(["A"] * 5), pd.Series(["0"] * 5), pd.Series([False] * 5),
    )
    assert result.guarded_prediction.tolist() == raw.tolist()


def test_supported_minority_is_preserved_but_unsupported_disagreement_is_voted():
    """An 80 percent majority can refine only unprotected disagreements."""
    raw = pd.Series(["A"] * 8 + ["B", "B"])
    result = select_guarded_predictions(
        raw, pd.Series(["A"] * 10), pd.Series(["0"] * 10),
        pd.Series([False] * 8 + [True, False]),
    )
    assert result.guarded_prediction.tolist() == ["A"] * 8 + ["B", "A"]
    assert raw.iloc[-1] == "B"


def test_cell_id_misalignment_rejected():
    """Votes cannot silently move to a different cell."""
    with pytest.raises(ValueError, match="cell IDs"):
        select_guarded_predictions(
            pd.Series(["A"], index=["x"]), pd.Series(["A"], index=["y"]),
            pd.Series(["0"], index=["x"]), pd.Series([False], index=["x"]),
        )


def test_nonmodal_vote_rejected():
    """Only native modal predictions can be candidates for acceptance."""
    with pytest.raises(ValueError, match="modal"):
        select_guarded_predictions(
            pd.Series(["A", "A", "B"]), pd.Series(["B"] * 3),
            pd.Series(["0"] * 3), pd.Series([False] * 3),
        )
