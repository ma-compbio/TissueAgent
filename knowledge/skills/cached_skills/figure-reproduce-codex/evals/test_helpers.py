"""Behavioral evaluations for the isolated figure-reproduction skill."""

# ruff: noqa: D103

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
REPO_ROOT = SKILL_ROOT.parents[2]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT / "src"))

import build_colormap  # noqa: E402
import compare_figures  # noqa: E402
import extract_reference_spec  # noqa: E402
import infer_scatter_palette  # noqa: E402
import validate_reproduction  # noqa: E402


def _draw_legend(path: Path, positions: list[tuple[int, int]], colors: list[str]) -> None:
    image = Image.new("RGB", (260, 220), "white")
    draw = ImageDraw.Draw(image)
    for index, ((x, y), color) in enumerate(zip(positions, colors, strict=True)):
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color)
        draw.text((x + 16, y - 6), f"Class {index}", fill="black")
    image.save(path)


@pytest.mark.parametrize(
    ("positions", "expected_layout"),
    [
        ([(20, 25), (20, 65), (20, 105), (20, 145)], "vertical"),
        ([(25, 30), (85, 30), (145, 30), (205, 30)], "horizontal"),
        ([(25, 30), (145, 30), (25, 90), (145, 90)], "grid"),
    ],
)
def test_detects_repeated_swatch_layouts(tmp_path: Path, positions, expected_layout):
    colors = ["#ececea", "#8742a8", "#4ea876", "#e9d24c"]
    target = tmp_path / "legend.png"
    _draw_legend(target, positions, colors)

    spec = extract_reference_spec.extract_spec(target, legend_box=(0, 0, 260, 200))

    assert spec["legend"]["layout"] == expected_layout
    assert [entry["hex"] for entry in spec["legend"]["entries"]] == colors
    assert all(entry["confidence"] >= 0.8 for entry in spec["legend"]["entries"])


def test_unlabeled_count_mismatch_is_unresolved_not_positionally_shifted(tmp_path: Path):
    spec = {
        "legend": {
            "entries": [
                {"label": None, "hex": "#ff0000", "confidence": 0.99},
                {"label": None, "hex": "#00ff00", "confidence": 0.99},
                {"label": None, "hex": "#0000ff", "confidence": 0.99},
            ]
        }
    }

    result = build_colormap.resolve_colormap(["A", "B"], spec)

    assert result.mapping == {}
    assert result.unresolved_dataset_labels == ["A", "B"]
    assert "count mismatch" in result.status


def test_explicit_labels_and_aliases_bind_by_identity(tmp_path: Path):
    spec = {
        "legend": {
            "entries": [
                {"label": None, "hex": "#aa0000", "confidence": 0.98},
                {"label": None, "hex": "#00aa00", "confidence": 0.97},
                {"label": None, "hex": "#0000aa", "confidence": 0.96},
            ]
        }
    }

    result = build_colormap.resolve_colormap(
        ["Alpha", "Dataset name"],
        spec,
        legend_labels=["Alpha", "Reference name", "Reference only"],
        aliases={"Dataset name": "Reference name"},
    )

    assert result.mapping == {"Alpha": "#aa0000", "Dataset name": "#00aa00"}
    assert result.unresolved_dataset_labels == []
    assert result.unused_reference_labels == ["Reference only"]
    assert result.provenance["Dataset name"]["source"] == "legend-alias"


def test_category_scope_uses_only_explicit_plotted_categories():
    selected = build_colormap.select_categories(["plotted", "dataset-only", "plotted"], ["plotted"])

    assert selected == ["plotted"]


def test_registered_scatter_recovers_missing_category_color(tmp_path: Path):
    width = height = 220
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(7)
    categories = np.array(["known-a"] * 80 + ["known-b"] * 80 + ["missing"] * 70)
    coordinates = rng.uniform(0.05, 0.95, size=(len(categories), 2))
    colors = {"known-a": "#d23b3b", "known-b": "#365fc4", "missing": "#c8c7c4"}
    for (x, y), category in zip(coordinates, categories, strict=True):
        px = round(15 + x * 190)
        py = round(205 - y * 190)
        draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=colors[category])
    target = tmp_path / "scatter.png"
    image.save(target)

    result = infer_scatter_palette.infer_palette(
        target,
        coordinates,
        categories,
        known_palette={"known-a": colors["known-a"], "known-b": colors["known-b"]},
        unresolved=["missing"],
        plot_box=(15, 15, 205, 205),
    )

    assert result.registration["match_rate"] >= 0.2
    assert result.inferred["missing"]["confidence"] >= 0.8
    assert (
        infer_scatter_palette.delta_e_hex(result.inferred["missing"]["hex"], colors["missing"]) <= 5
    )


def test_registered_scatter_rejects_unrelated_reference(tmp_path: Path):
    target = tmp_path / "blank.png"
    Image.new("RGB", (120, 120), "white").save(target)
    coordinates = np.array([[0.1, 0.1], [0.9, 0.9]] * 60)
    categories = np.array(["known", "missing"] * 60)

    result = infer_scatter_palette.infer_palette(
        target,
        coordinates,
        categories,
        known_palette={"known": "#ff0000"},
        unresolved=["missing"],
        plot_box=(10, 10, 110, 110),
    )

    assert result.inferred == {}
    assert result.registration["accepted"] is False


def test_inference_merges_partial_provenance_without_default_colors():
    partial = {
        "mapping": {"known": "#ff0000"},
        "provenance": {"known": {"source": "legend-label", "hex": "#ff0000"}},
        "unresolved_dataset_labels": ["missing"],
        "unused_reference_labels": ["reference only"],
    }
    inference = infer_scatter_palette.InferenceResult(
        inferred={
            "missing": {
                "source": "registered-reference-pixels",
                "hex": "#c8c7c4",
                "confidence": 0.91,
            }
        },
        registration={"accepted": True, "match_rate": 0.7},
        unresolved=[],
    )

    merged = infer_scatter_palette.merge_provenance(partial, inference)

    assert merged["mapping"] == {"known": "#ff0000", "missing": "#c8c7c4"}
    assert merged["unresolved_dataset_labels"] == []
    assert merged["provenance"]["missing"]["source"] == "registered-reference-pixels"


def test_comparison_json_binds_metrics_to_both_images(tmp_path: Path):
    original = tmp_path / "original.png"
    reproduced = tmp_path / "reproduced.png"
    Image.new("RGB", (40, 60), "white").save(original)
    Image.new("RGB", (40, 60), "white").save(reproduced)

    metrics = compare_figures.compare(original, reproduced)

    assert metrics["inputs"]["original_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
    assert (
        metrics["inputs"]["reproduced_sha256"]
        == hashlib.sha256(reproduced.read_bytes()).hexdigest()
    )
    assert metrics["pass2_geometry"]["clean"] is True


def test_validator_rejects_unresolved_palette_and_stale_metrics(tmp_path: Path):
    target = tmp_path / "target.png"
    attempt = tmp_path / "figure_attempt1.png"
    final = tmp_path / "figure.png"
    for path in (target, attempt, final):
        Image.new("RGB", (30, 30), "white").save(path)
    provenance = tmp_path / "colormap_provenance.json"
    provenance.write_text(json.dumps({"unresolved_dataset_labels": ["missing"]}))
    metrics = tmp_path / "compare_metrics_attempt1.json"
    metrics.write_text(
        json.dumps(
            {
                "inputs": {
                    "original_sha256": "stale",
                    "reproduced_sha256": "stale",
                },
                "pass2_geometry": {"clean": True, "findings": []},
            }
        )
    )

    report = validate_reproduction.validate(
        target=target,
        final_figure=final,
        accepted_attempt=attempt,
        plotted_data=tmp_path / "plotted_data.csv",
        provenance=provenance,
        repro_note=tmp_path / "note.md",
        attempt_metrics=[metrics],
    )

    assert report["status"] == "fail"
    assert any("unresolved" in error for error in report["errors"])
    assert any("hash" in error for error in report["errors"])


def test_skill_is_valid_and_original_hash_manifest_is_unchanged():
    manifest = json.loads((SKILL_ROOT / "evals/original_manifest.json").read_text())
    root = SKILL_ROOT.parent / "figure-reproduce"
    current = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert current == manifest

    from agents.recruiter_agent.prompt import _skill_from_file

    metadata = _skill_from_file(SKILL_ROOT / "SKILL.md")
    assert metadata is not None
    assert metadata.name == "figure-reproduce-codex"
    assert metadata.applies_to == ["coding_agent"]
