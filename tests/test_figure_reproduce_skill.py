"""Regression tests for the bundled figure-reproduction helpers."""

import importlib.util
import sys
from pathlib import Path

from PIL import Image


SKILL_ROOT = Path(__file__).parent.parent / "knowledge" / "skills" / "figure-reproduce"


def _load_script(name: str):
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"figure_reproduce_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legend_entry_limit_is_independent_of_palette_limit(tmp_path, monkeypatch) -> None:
    """The dominant-color summary limit must not truncate a long legend."""
    extractor = _load_script("extract_reference_spec")
    image_path = tmp_path / "reference.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    received_limits = []

    def find_legend_swatches(_image, _box, max_colors):
        received_limits.append(max_colors)
        return [], "ok"

    monkeypatch.setattr(extractor, "find_legend_swatches", find_legend_swatches)
    monkeypatch.setattr(extractor, "quantize_colors", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(extractor, "ocr_lines", lambda *_args, **_kwargs: ([], "unavailable"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_reference_spec.py",
            str(image_path),
            "--legend-box",
            "0,0,100,100",
            "--max-colors",
            "3",
            "--json",
        ],
    )

    assert extractor.main() == 0
    assert received_limits == [64]


def test_explicit_legend_entry_limit_is_honored(tmp_path, monkeypatch) -> None:
    """Callers can override the generous legend-specific default."""
    extractor = _load_script("extract_reference_spec")
    image_path = tmp_path / "reference.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    received_limits = []

    def find_legend_swatches(_image, _box, max_colors):
        received_limits.append(max_colors)
        return [], "ok"

    monkeypatch.setattr(extractor, "find_legend_swatches", find_legend_swatches)
    monkeypatch.setattr(extractor, "quantize_colors", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(extractor, "ocr_lines", lambda *_args, **_kwargs: ([], "unavailable"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_reference_spec.py",
            str(image_path),
            "--legend-box",
            "0,0,100,100",
            "--max-legend-entries",
            "24",
            "--json",
        ],
    )

    assert extractor.main() == 0
    assert received_limits == [24]


def test_explicit_palette_wins_and_reference_conflict_is_recorded(
    tmp_path, monkeypatch
) -> None:
    """A measurable disagreement is reported without replacing explicit colors."""
    builder = _load_script("build_colormap")
    palette_path = tmp_path / "palette.yaml"
    palette_path.write_text('A: "#112233"\nB: "#445566"\n')
    output_path = tmp_path / "colormap.yaml"
    reference_calls = []

    def from_reference(image, legend_box=None, max_colors=40):
        reference_calls.append((image, legend_box, max_colors))
        return (
            [
                {"label": "A", "hex": "#ff0000"},
                {"label": "B", "hex": "#445566"},
            ],
            {"reliable": True},
            "ok",
        )

    monkeypatch.setattr(builder, "from_reference", from_reference)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_colormap.py",
            "--palette",
            str(palette_path),
            "--reference",
            "reference.png",
            "--legend-box",
            "1,2,30,40",
            "--out",
            str(output_path),
        ],
    )

    assert builder.main() == 0
    result = output_path.read_text()
    assert reference_calls == [("reference.png", (1, 2, 30, 40), 64)]
    assert "# source_tier : 1-supplied" in result
    assert 'A: "#112233"' in result
    assert 'B: "#445566"' in result
    assert "reference legend disagrees with explicit palette: A" in result


def test_existing_label_normalization_and_default_extension_are_preserved() -> None:
    """The selective migration retains the target's category safeguards."""
    builder = _load_script("build_colormap")

    assert builder._norm_label("T-cell") == builder._norm_label("tcell")
    extra = builder._extra_distinct_colors(5, builder.DEFAULT_PALETTE)
    assert len(extra) == 5
    assert len(set(extra + builder.DEFAULT_PALETTE)) == len(extra) + len(
        builder.DEFAULT_PALETTE
    )


def test_existing_duplicate_color_warning_is_preserved(tmp_path, monkeypatch) -> None:
    """Shared explicit colors remain visible in generated provenance warnings."""
    builder = _load_script("build_colormap")
    palette_path = tmp_path / "palette.yaml"
    palette_path.write_text('A: "#112233"\nB: "#112233"\n')
    output_path = tmp_path / "colormap.yaml"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_colormap.py",
            "--palette",
            str(palette_path),
            "--out",
            str(output_path),
        ],
    )

    assert builder.main() == 0
    assert "color(s) are shared by more than one category" in output_path.read_text()
