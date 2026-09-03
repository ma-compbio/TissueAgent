"""Scoring: agent ensemble table vs the expert reference."""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "benchmark" / "optimizer_ccc"))

from score import REQUIRED_COLUMNS, aggregate_round, score_run  # noqa: E402


def _table(pairs_scores: list[tuple[str, str, float]]) -> pd.DataFrame:
    rows = []
    for lig, rec, s in pairs_scores:
        row = {c: 0.5 for c in REQUIRED_COLUMNS if c not in ("ligand", "receptor", "ensemble_score")}
        row.update(ligand=lig, receptor=rec, ensemble_score=s)
        rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture()
def reference_csv(tmp_path):
    pairs = [(f"L{i}", f"R{i}", 1.0 - i * 0.01) for i in range(50)]
    p = tmp_path / "reference.csv"
    _table(pairs).to_csv(p, index=False)
    return p, pairs


def test_identical_scores_perfectly(tmp_path, reference_csv):
    ref, pairs = reference_csv
    agent = tmp_path / "agent.csv"
    _table(pairs).to_csv(agent, index=False)
    r = score_run(agent, ref, k=20)
    assert r["valid"] and r["n_common"] == 50
    assert r["spearman"] == 1.0
    assert r["topk_jaccard"] == 1.0


def test_reversed_ranks_score_negative(tmp_path, reference_csv):
    ref, pairs = reference_csv
    reversed_pairs = [(lig, rec, 1.0 - s) for lig, rec, s in pairs]
    agent = tmp_path / "agent.csv"
    _table(reversed_pairs).to_csv(agent, index=False)
    r = score_run(agent, ref, k=20)
    assert r["valid"]
    assert r["spearman"] == -1.0
    assert r["topk_jaccard"] < 0.2


def test_case_normalization(tmp_path, reference_csv):
    ref, pairs = reference_csv
    lowered = [(lig.lower(), rec.lower(), s) for lig, rec, s in pairs]
    agent = tmp_path / "agent.csv"
    _table(lowered).to_csv(agent, index=False)
    r = score_run(agent, ref, k=20)
    assert r["n_common"] == 50 and r["spearman"] == 1.0


def test_missing_column_is_invalid(tmp_path, reference_csv):
    ref, pairs = reference_csv
    df = _table(pairs).drop(columns=["decoupler_pct"])
    agent = tmp_path / "agent.csv"
    df.to_csv(agent, index=False)
    r = score_run(agent, ref)
    assert not r["valid"] and "decoupler_pct" in r["reason"]


def test_missing_file_and_empty_table_invalid(tmp_path, reference_csv):
    ref, _ = reference_csv
    r = score_run(tmp_path / "nope.csv", ref)
    assert not r["valid"] and "missing file" in r["reason"]
    empty = tmp_path / "empty.csv"
    _table([]).reindex(columns=REQUIRED_COLUMNS).to_csv(empty, index=False)
    r = score_run(empty, ref)
    assert not r["valid"] and r["reason"] == "empty table"


def test_aggregate_round():
    per_run = [
        {"valid": True, "spearman": 0.8, "topk_jaccard": 0.5, "total_tokens": 100},
        {"valid": True, "spearman": 0.6, "topk_jaccard": 0.7, "total_tokens": 300},
        {"valid": False, "spearman": None, "topk_jaccard": None, "total_tokens": 200},
    ]
    agg = aggregate_round(per_run)
    assert agg["valid_run_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert agg["mean_spearman"] == 0.7
    assert agg["median_total_tokens"] == 200
