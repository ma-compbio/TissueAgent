"""Tests for the analysis notebook logger (coding_agent/notebook_log.py).

The claim under test is reproducibility: after a run, ``outputs/analysis.ipynb``
must exist, be valid nbformat, and contain the code that actually ran with the
output it actually produced. A notebook that exists but doesn't open, or that
records the truncated digest instead of the real output, would be worse than
nothing — it would look like provenance while being wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import agents.agent_registry.coding_agent_cache.notebook_log as notebook_log


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Point the logger at a throwaway project dir; yield the notebook path."""
    project_dir = tmp_path / "project"
    (project_dir / "outputs").mkdir(parents=True)
    monkeypatch.setattr(notebook_log, "ACTIVE_PROJECT_DIR", project_dir)
    return project_dir / "outputs" / "analysis.ipynb"


_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lE"
    "QVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def test_notebook_is_created_and_valid(project):
    """The headline claim: a run produces an openable notebook."""
    notebook_log.append_cell("print('hi')", "hi\n", [], "python", False)

    assert project.exists(), "analysis.ipynb must exist after a cell runs"
    nb = nbf.read(str(project), as_version=4)
    nbf.validate(nb)  # raises if the file isn't a valid notebook
    assert nb.metadata.kernelspec["name"] == "python3"


def test_notebook_opens_with_a_cwd_setup_cell(project):
    """The notebook must restore the cwd the agent's paths were written against.

    That cwd is the *workspace root*, not the project dir: the prompt directs the
    agent to write workspace-relative paths ('project/outputs/figures/x.png') so
    kernel paths and the file tools agree. A setup cell that chdir'd into
    project/ would double the prefix and every savefig would fail.

    The agent's own seeding is plumbing that never reaches the notebook, so
    without this cell a reader opening it in place hits FileNotFoundError.
    """
    notebook_log.append_cell("print('hi')", "hi\n", [], "python", False)

    nb = nbf.read(str(project), as_version=4)
    setup = [c for c in nb.cells if c.cell_type == "code"][0]
    assert "chdir" in setup.source
    # Walks UP to the workspace root; must never descend into project/.
    assert "os.chdir('../..')" in setup.source
    assert "os.chdir('project')" not in setup.source


def test_plumbing_never_reaches_the_notebook(project):
    """chdir/makedirs seeding is not analysis and must stay out of the record."""
    notebook_log.append_cell("import scanpy as sc", "", [], "python", False)

    nb = nbf.read(str(project), as_version=4)
    agent_cells = [c for c in nb.cells if c.cell_type == "code"][1:]  # skip setup
    joined = "\n".join(c.source for c in agent_cells)
    assert "os.makedirs" not in joined
    assert "setwd(" not in joined


def test_code_and_output_are_recorded(project):
    """The cell must carry the real source and the real stdout."""
    notebook_log.append_cell("x = 1 + 1\nprint(x)", "2\n", [], "python", False)

    nb = nbf.read(str(project), as_version=4)
    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    assert code_cells[-1].source == "x = 1 + 1\nprint(x)"
    assert code_cells[-1].outputs[0].text == "2\n"


def test_untruncated_output_is_recorded(project):
    """The notebook records what printed, not the 3k digest the model saw.

    This is why the hook lives inside execute() rather than in the python() tool.
    """
    big = "row\n" * 20_000
    notebook_log.append_cell("print(df)", big, [], "python", False)

    nb = nbf.read(str(project), as_version=4)
    assert nb.cells[-1].outputs[0].text == big
    assert "truncated" not in nb.cells[-1].outputs[0].text


def test_cells_accumulate_in_order(project):
    """Order is the record — a reader must see what ran when."""
    for i in range(3):
        notebook_log.append_cell(f"step_{i}()", f"out{i}\n", [], "python", False)

    nb = nbf.read(str(project), as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"][1:]  # [0] is the cwd setup cell
    assert [c.source for c in code] == ["step_0()", "step_1()", "step_2()"]
    assert [c.execution_count for c in code] == [2, 3, 4]


def test_images_are_embedded_so_the_notebook_stands_alone(project):
    """Plots must render from the notebook alone, without the workspace."""
    notebook_log.append_cell("plt.show()", "", [_PNG], "python", False)

    nb = nbf.read(str(project), as_version=4)
    out = nb.cells[-1].outputs[0]
    assert out.output_type == "display_data"
    assert "image/png" in out.data


def test_r_cells_are_marked_not_mislabelled(project):
    """A notebook has one kernelspec; R cells must be preserved and labelled."""
    notebook_log.append_cell("library(CARD)", "ok\n", [], "r", False)

    nb = nbf.read(str(project), as_version=4)
    assert nb.cells[-1].source.startswith("%%R\n")
    assert "library(CARD)" in nb.cells[-1].source


def test_failed_cells_are_kept_with_their_error(project):
    """A cell that errored is part of the record, not noise to drop."""
    notebook_log.append_cell("boom()", "NameError: boom\n", [], "python", True)

    nb = nbf.read(str(project), as_version=4)
    out = nb.cells[-1].outputs[0]
    assert out.name == "stderr"
    assert "NameError" in out.text


def test_logging_failure_never_raises(project, monkeypatch):
    """Reproducibility logging must not break the execution it records."""

    def _boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(nbf, "write", _boom)
    notebook_log.append_cell("print(1)", "1\n", [], "python", False)  # must not raise


def test_environment_is_captured_once(project):
    """Version capture runs in the kernel, and only for a fresh notebook."""

    class _Result:
        text = "python 3.12.0\nscanpy 1.10.3\n"
        error = False

    calls = []

    def _fake_execute(code, language):
        calls.append((code, language))
        return _Result()

    notebook_log.record_environment(_fake_execute)
    assert len(calls) == 1
    assert "scanpy" in calls[0][0]

    nb = nbf.read(str(project), as_version=4)
    assert "scanpy 1.10.3" in nb.cells[-1].outputs[0].text

    # Second call is a no-op: the notebook already carries its header.
    notebook_log.record_environment(_fake_execute)
    assert len(calls) == 1
