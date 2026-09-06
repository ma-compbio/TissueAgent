"""Artifact validation must inspect content, not just existence.

A run once "produced" a 67-byte file named ``*.png`` that no image reader could
open, and the existence-only check marked the step done. These tests lock in the
content-aware behaviour: a real figure passes, a placeholder / empty / headerless
stub is reported ``invalid`` (and so the step FAILS).
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from graph import node_factories  # noqa: E402
from graph.node_factories import (  # noqa: E402
    _validate_artifact_content,
    _validate_step_artifacts,
)


def _write_real_png(path: Path, size: tuple[int, int] = (64, 48)) -> None:
    from PIL import Image

    Image.new("RGB", size, (12, 34, 56)).save(path)


def test_real_png_passes(tmp_path):
    p = tmp_path / "fig.png"
    _write_real_png(p)
    assert _validate_artifact_content(p) is None


def test_placeholder_png_is_rejected(tmp_path):
    # The exact failure mode observed: a tiny stub with a PNG signature.
    p = tmp_path / "fake.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 59)  # 67 bytes
    reason = _validate_artifact_content(p)
    assert reason is not None


def test_empty_file_is_rejected(tmp_path):
    p = tmp_path / "empty.png"
    p.write_bytes(b"")
    assert _validate_artifact_content(p) == "file is empty (0 bytes)"


def test_csv_needs_a_data_row(tmp_path):
    header_only = tmp_path / "header.csv"
    header_only.write_text("gene,logfc\n")
    assert _validate_artifact_content(header_only) == "table has no data rows"

    with_data = tmp_path / "ok.csv"
    with_data.write_text("gene,logfc\nSOX2,1.3\n")
    assert _validate_artifact_content(with_data) is None


def test_empty_json_is_rejected(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    assert _validate_artifact_content(empty) == "JSON is empty"

    ok = tmp_path / "ok.json"
    ok.write_text('{"n_cells": 4123}')
    assert _validate_artifact_content(ok) is None


def test_unknown_text_type_accepts_nonempty(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("some real content")
    assert _validate_artifact_content(p) is None


def test_validate_step_artifacts_buckets(tmp_path, monkeypatch):
    # Point the validator's workspace root at a temp dir.
    monkeypatch.setattr(node_factories, "DATA_DIR", tmp_path)

    _write_real_png(tmp_path / "good.png")
    (tmp_path / "bad.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 59)

    found, missing, invalid = _validate_step_artifacts(
        ["good.png", "bad.png", "never.png"]
    )
    assert found == ["good.png"]
    assert missing == ["never.png"]
    assert len(invalid) == 1 and invalid[0].startswith("bad.png (")


def test_glob_matches_are_content_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(node_factories, "DATA_DIR", tmp_path)
    (tmp_path / "outputs").mkdir()
    _write_real_png(tmp_path / "outputs" / "panel_A.png")
    (tmp_path / "outputs" / "panel_B.png").write_bytes(b"")  # empty stub

    found, missing, invalid = _validate_step_artifacts(["outputs/*.png"])
    assert "outputs/panel_A.png" in found
    assert any("panel_B.png" in x for x in invalid)
    assert missing == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
