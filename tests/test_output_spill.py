"""Tests for oversized-tool-output spilling (src/agents/output_spill.py).

The load-bearing test here is the round-trip: a spilled path must actually open
via the ``read`` tool. The spill returns a DATA_DIR-relative path while the
sibling ``image_spill`` returns an ACTIVE_PROJECT_DIR-relative one, so it is easy
to hand back a path that looks plausible and 404s — which is strictly worse than
plain truncation, because it advertises data it can't deliver.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import agents.output_spill as output_spill
from agents.agent_utils import truncate_output


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point the spill module at a throwaway workspace mirroring the real layout."""
    data_dir = tmp_path / "workspace"
    project_dir = data_dir / "project"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr(output_spill, "DATA_DIR", data_dir)
    monkeypatch.setattr(output_spill, "ACTIVE_PROJECT_DIR", project_dir)
    return data_dir


# --------------------------------------------------------------------------
# spill_text_to_disk
# --------------------------------------------------------------------------


def test_spill_writes_full_text_and_returns_relative_path(workspace):
    """The file holds the whole payload, and the path is DATA_DIR-relative."""
    text = "x" * 50_000
    path = output_spill.spill_text_to_disk(text)

    assert path is not None
    assert not Path(path).is_absolute(), "path must be relative for the read tool"
    assert (workspace / path).read_text() == text, "spilled file must hold the FULL text"


def test_spill_lands_under_project_outputs(workspace):
    """Under outputs/ so it survives park/promote and reset_data_directories."""
    path = output_spill.spill_text_to_disk("hello")
    assert path.startswith("project/outputs/_trace/output/")
    assert path.endswith(".txt")


def test_spill_returns_none_for_empty_text(workspace):
    """Nothing to recover; don't litter the workspace."""
    assert output_spill.spill_text_to_disk("") is None


def test_spill_paths_are_unique(workspace):
    """Concurrent cells must not clobber each other's output."""
    a = output_spill.spill_text_to_disk("first")
    b = output_spill.spill_text_to_disk("second")
    assert a != b
    assert (workspace / a).read_text() == "first"
    assert (workspace / b).read_text() == "second"


def test_spill_returns_none_when_write_fails(workspace, monkeypatch):
    """A spill failure degrades to None — never raises into the tool call."""

    def _boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)
    assert output_spill.spill_text_to_disk("x" * 10_000) is None


# --------------------------------------------------------------------------
# truncate_output integration
# --------------------------------------------------------------------------


def test_short_text_is_untouched_and_writes_nothing(workspace):
    """Below the cap there is nothing to truncate and nothing to spill."""
    assert truncate_output("short", 3000, spill=True) == "short"
    assert not list(workspace.rglob("*.txt")), "no file should be written"


def test_truncation_notice_cites_a_readable_path(workspace):
    """The notice must name the spilled file so the agent can go get it."""
    out = truncate_output("y" * 50_000, 3000, spill=True)

    assert "characters truncated" in out
    assert "project/outputs/_trace/output/" in out
    assert "read" in out

    spilled = next(workspace.rglob("*.txt"))
    assert str(spilled.relative_to(workspace)) in out


def test_spill_off_by_default_keeps_old_behaviour(workspace):
    """Display-only callers (e.g. graph.py prompt previews) must not spill.

    They truncate to 600 chars on every graph build; spilling there would write
    files nobody ever reads.
    """
    out = truncate_output("z" * 50_000, 3000)
    assert "characters truncated" in out
    assert "_trace" not in out
    assert not list(workspace.rglob("*.txt"))


def test_truncation_falls_back_cleanly_when_spill_fails(workspace, monkeypatch):
    """If the spill fails we still truncate — just without a path."""
    monkeypatch.setattr(output_spill, "spill_text_to_disk", lambda _t: None)

    out = truncate_output("w" * 50_000, 3000, spill=True)
    assert "characters truncated" in out
    assert "_trace" not in out


def test_head_and_tail_are_preserved(workspace):
    """Truncation keeps the edges; only the middle moves to disk."""
    text = "HEAD" + ("m" * 50_000) + "TAIL"
    out = truncate_output(text, 3000, spill=True)
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")
    assert len(out) < len(text)
