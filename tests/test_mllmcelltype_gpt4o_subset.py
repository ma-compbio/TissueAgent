# ruff: noqa: D102, D103
"""Tests for the GPT-4o mLLMCelltype paired recruitment benchmark."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmark.mllmcelltype_gpt4o_subset.run import (
    AUTHOR_REPO,
    EXPECTED_DATASETS,
    SUBSET_ID,
    InputError,
    _find_recruited_result,
    _plan_evidence,
    _recover_tissueagent_checkpoint,
    _request_matches,
    dataset_input_hash,
    load_subset,
    main,
    summarize,
    tissueagent_prompt,
)


def _bundle() -> dict:
    return {
        "schema_version": 1,
        "provenance": {
            "author_repository": AUTHOR_REPO,
            "paper_subset": SUBSET_ID,
            "source_revision": "test-revision",
            "preparation_method": "test fixture only",
        },
        "datasets": [
            {
                "id": dataset_id,
                "name": dataset_id.replace("_", " ").title(),
                "species": "human",
                "tissue": "test tissue",
                "source_url": f"https://example.invalid/{dataset_id}",
                "marker_genes": {"0": ["CD3D", "CD3E"], "1": ["MS4A1"]},
                "reference_annotations": {"0": "T cell", "1": "B cell"},
                "profile_weights": {"0": 1, "1": 1},
            }
            for dataset_id in EXPECTED_DATASETS
        ],
    }


def _write_bundle(tmp_path: Path, bundle: dict) -> Path:
    path = tmp_path / "subset.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def test_load_subset_requires_exact_source_recoverable_three(tmp_path: Path) -> None:
    bundle = _bundle()
    loaded = load_subset(_write_bundle(tmp_path, bundle))
    assert [row["id"] for row in loaded["datasets"]] == list(EXPECTED_DATASETS)
    bundle["datasets"].pop()
    with pytest.raises(InputError, match="exactly the source-recoverable"):
        load_subset(_write_bundle(tmp_path, bundle))


def test_prompt_requires_exact_external_agent_and_gpt4o(tmp_path: Path) -> None:
    dataset = load_subset(_write_bundle(tmp_path, _bundle()))["datasets"][0]
    prompt = tissueagent_prompt(dataset)
    assert "exactly one execution plan step" in prompt
    assert "`mllmcelltype_agent`" in prompt
    assert "must not assign or invoke any other domain agent" in prompt
    assert "`mllmcelltype_annotate_clusters_tool` exactly once" in prompt
    assert "model='gpt-4o'" in prompt
    assert "mode='single'" in prompt
    assert dataset_input_hash(dataset) in prompt


def test_request_verification_catches_model_or_input_drift(tmp_path: Path) -> None:
    dataset = load_subset(_write_bundle(tmp_path, _bundle()))["datasets"][0]
    request = {
        "marker_genes": dataset["marker_genes"],
        "species": dataset["species"],
        "tissue": dataset["tissue"],
        "mode": "single",
        "provider": "openai",
        "model": "gpt-4o",
    }
    assert _request_matches(request, dataset)
    request["model"] = "gpt-4o-mini"
    assert not _request_matches(request, dataset)


def test_recruited_artifact_requires_matching_request(tmp_path: Path) -> None:
    dataset = load_subset(_write_bundle(tmp_path, _bundle()))["datasets"][0]
    run_dir = tmp_path / "state" / "workspace" / "project" / "outputs" / "mllmcelltype" / "run"
    run_dir.mkdir(parents=True)
    request = {
        "marker_genes": dataset["marker_genes"],
        "species": dataset["species"],
        "tissue": dataset["tissue"],
        "mode": "single",
        "provider": "openai",
        "model": "gpt-4o",
    }
    (run_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (run_dir / "result.json").write_text(
        json.dumps({"status": "ok", "annotations": {"0": "T cell", "1": "B cell"}}),
        encoding="utf-8",
    )
    path, result, verified = _find_recruited_result(tmp_path / "state", dataset)
    assert path == run_dir / "result.json"
    assert result["status"] == "ok"
    assert verified


def test_plan_evidence_requires_one_exact_external_agent() -> None:
    metrics = {"plan": {"steps": [{"assigned_agent": "mllmcelltype_agent"}]}}
    assert _plan_evidence(metrics) == (["mllmcelltype_agent"], True)
    metrics["plan"]["steps"].append({"assigned_agent": "single_cell_agent"})
    assert _plan_evidence(metrics) == (
        ["mllmcelltype_agent", "single_cell_agent"],
        False,
    )


def test_cli_dry_run_validates_without_api_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_path = _write_bundle(tmp_path, _bundle())
    monkeypatch.setattr(
        sys,
        "argv",
        ["mllmcelltype-gpt4o-subset", "--input", str(input_path), "--dry-run"],
    )
    assert main() == 0


def test_summary_reports_exact_arm_agreement_and_accuracy() -> None:
    record = {
        "dataset_id": "hlca",
        "reference_annotations": {"0": "T cell", "1": "B cell"},
        "profile_weights": {"0": 1, "1": 1},
        "direct": {
            "status": "ok",
            "annotations": {"0": "T-cell", "1": "B cell"},
        },
        "tissueagent": {
            "status": "ok",
            "annotations": {"0": "T cell", "1": "Monocyte"},
            "recruited": True,
            "tool_fired": True,
        },
    }
    summary = summarize([record])
    assert summary["valid_paired_datasets"] == 1
    assert summary["exact_arm_agreement_count"] == 1
    assert summary["exact_arm_agreement"] == 0.5
    assert summary["weighted_arm_agreement"] == 0.5
    assert summary["direct_exact_profile_accuracy"] == 1.0
    assert summary["tissueagent_exact_profile_accuracy"] == 0.5
    assert summary["tissueagent_weighted_profile_accuracy"] == 0.5
    assert summary["accuracy_difference"] == -0.5
    assert summary["per_dataset"][0]["direct_exact_profile_correct"] == 2
    assert summary["per_dataset"][0]["tissueagent_exact_profile_correct"] == 1


def test_isolated_driver_forwards_writable_log_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents.agent_registry.mllmcelltype_agent import _driver

    observed: dict = {}

    def annotate_clusters(**kwargs):
        observed.update(kwargs)
        return {"0": "T cell"}

    monkeypatch.setitem(
        sys.modules,
        "mllmcelltype",
        SimpleNamespace(
            annotate_clusters=annotate_clusters,
            interactive_consensus_annotation=lambda **kwargs: {},
        ),
    )
    log_dir = tmp_path / "logs"
    result = _driver._run(
        {
            "marker_genes": {"0": ["CD3D"]},
            "species": "human",
            "mode": "single",
            "provider": "openai",
            "model": "gpt-4o",
            "cache_dir": str(tmp_path / "cache"),
            "log_dir": str(log_dir),
        }
    )
    assert result["status"] == "ok"
    assert observed["log_dir"] == str(log_dir)


@pytest.mark.parametrize("with_metrics", [True, False])
def test_recover_tissueagent_checkpoint_after_reporter_interrupt(
    tmp_path: Path, with_metrics: bool
) -> None:
    dataset = load_subset(_write_bundle(tmp_path, _bundle()))["datasets"][0]
    state_root = tmp_path / "state" / "recruited" / dataset["id"]
    project = state_root / "workspace" / "project"
    run_dir = project / "outputs" / "mllmcelltype" / "run"
    run_dir.mkdir(parents=True)
    request = {
        "marker_genes": dataset["marker_genes"],
        "species": dataset["species"],
        "tissue": dataset["tissue"],
        "mode": "single",
        "provider": "openai",
        "model": "gpt-4o",
    }
    (run_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "mode": "single",
                "provider": "openai",
                "model": "gpt-4o",
                "annotations": {"0": "T cell", "1": "B cell"},
            }
        ),
        encoding="utf-8",
    )
    if with_metrics:
        (project / "metrics.json").write_text(
            json.dumps({"plan": {"steps": [{"assigned_agent": "mllmcelltype_agent"}]}}),
            encoding="utf-8",
        )
    else:
        plan_path = state_root / "plan_scratch" / "plan.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("assigned_agent: mllmcelltype_agent\n", encoding="utf-8")
    recovered = _recover_tissueagent_checkpoint(dataset, tmp_path)
    assert recovered is not None
    assert recovered["status"] == "ok"
    assert recovered["recovered_from_checkpoint"] is True
    assert recovered["orchestration_complete"] is False
