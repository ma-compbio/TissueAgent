"""Regression tests for planner-to-project artifact path normalization."""

from __future__ import annotations

import graph.node_factories as node_factories


def test_concise_artifact_path_resolves_under_project_outputs(tmp_path, monkeypatch) -> None:
    """Planner-style `tables/...` paths should validate coding-agent outputs."""
    data_dir = tmp_path / "workspace"
    outputs = data_dir / "project" / "outputs"
    artifact = outputs / "tables" / "result.csv"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("value\n1\n")
    monkeypatch.setattr(node_factories, "DATA_DIR", data_dir)
    monkeypatch.setattr(node_factories, "active_project_outputs", lambda: outputs)

    found, missing = node_factories._validate_step_artifacts(["tables/result.csv"])

    assert found == ["project/outputs/tables/result.csv"]
    assert missing == []


def test_explicit_project_output_path_still_resolves(tmp_path, monkeypatch) -> None:
    """Fully qualified project paths must retain their existing behavior."""
    data_dir = tmp_path / "workspace"
    outputs = data_dir / "project" / "outputs"
    artifact = outputs / "figures" / "plot.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"png")
    monkeypatch.setattr(node_factories, "DATA_DIR", data_dir)
    monkeypatch.setattr(node_factories, "active_project_outputs", lambda: outputs)

    found, missing = node_factories._validate_step_artifacts(
        ["project/outputs/figures/plot.png"]
    )

    assert found == ["project/outputs/figures/plot.png"]
    assert missing == []
