"""Tests for per-project sandboxing.

Covers:
    T1 — switch flips visibility (A→B parks A, promotes B)
    T2 — agent tools cannot reach parked storage outside DATA_DIR
    T3 — kernel cwd is invariant across switches (force_restart on swap)
    T4 — recovery cases B.1-B.5
    T5 — delete active project parks-then-removes
    T6 — pre-mint upload, then mint, no file movement
    T7 — .chat.json hidden from default glob('**/*')
    T8 — end-to-end migration of old layouts into new layout

Run:
    cd src && OPENAI_API_KEY=dummy pytest ../tests/test_project_sandbox.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest


# Allow `from server...` / `from config import ...` resolution.
os.environ.setdefault("OPENAI_API_KEY", "dummy")
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import config  # noqa: E402
from server import utils as server_utils  # noqa: E402
from agents import agent_tools  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: swap every relevant path constant to point inside tmp_path,
# across every module that captured the names by-value at import time.
# ---------------------------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Re-root the workspace at tmp_path and re-bind the constants everywhere."""
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    active_project_dir = workspace / "project"
    projects_dir = root / "projects"
    plan_scratch_dir = root / "plan_scratch"
    library_dir = workspace / "library"
    notebook_dir = workspace / "notebook"

    for d in (active_project_dir, projects_dir, plan_scratch_dir, library_dir, notebook_dir):
        d.mkdir(parents=True, exist_ok=True)
    # Canonical subdirs the active project always has.
    for sub in ("uploads", "outputs"):
        (active_project_dir / sub).mkdir(exist_ok=True)

    # Patch every module that imported these names directly.
    patches = {
        config: {
            "DATA_DIR": workspace,
            "ACTIVE_PROJECT_DIR": active_project_dir,
            "PROJECTS_DIR": projects_dir,
            "PLAN_SCRATCH_DIR": plan_scratch_dir,
            "LIBRARY_DIR": library_dir,
            "NOTEBOOK_DIR": notebook_dir,
        },
        server_utils: {
            "DATA_DIR": workspace,
            "ACTIVE_PROJECT_DIR": active_project_dir,
            "PROJECTS_DIR": projects_dir,
            "PLAN_SCRATCH_DIR": plan_scratch_dir,
            "LIBRARY_DIR": library_dir,
        },
        agent_tools: {
            "DATA_DIR": workspace,
            "ACTIVE_PROJECT_DIR": active_project_dir,
            "LIBRARY_DIR": library_dir,
            "NOTEBOOK_DIR": notebook_dir,
            "_AGENT_VISIBLE_ROOTS": (active_project_dir, library_dir, notebook_dir),
        },
    }
    for mod, attrs in patches.items():
        for name, value in attrs.items():
            monkeypatch.setattr(mod, name, value)

    # Stub the kernel restart hooks so tests don't need a real kernel.
    restart_calls: list[bool] = []

    def fake_force_kernel_restart():
        restart_calls.append(True)

    def fake_rearm_kernel():
        restart_calls.append(False)

    monkeypatch.setattr(server_utils, "_force_kernel_restart", fake_force_kernel_restart)
    monkeypatch.setattr(server_utils, "_rearm_kernel", fake_rearm_kernel)

    # Reset session.project_id between tests.
    from server.session_manager import session
    session.project_id = None
    session.project_title = ""

    return {
        "root": root,
        "workspace": workspace,
        "active": active_project_dir,
        "projects": projects_dir,
        "plan_scratch": plan_scratch_dir,
        "library": library_dir,
        "notebook": notebook_dir,
        "restart_calls": restart_calls,
    }


def _make_parked(projects_dir: Path, pid: str, file_relpath: str, content: str) -> None:
    """Create a parked project skeleton with one file under outputs/."""
    base = projects_dir / pid
    (base / "outputs").mkdir(parents=True, exist_ok=True)
    (base / "uploads").mkdir(exist_ok=True)
    (base / ".project_id").write_text(pid)
    target = base / file_relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


# ---------------------------------------------------------------------------
# T1 — switch flips visibility
# ---------------------------------------------------------------------------


def test_switch_flips_visibility(sandbox):
    """Activating B parks A and promotes B; only B's files are visible."""
    _make_parked(sandbox["projects"], "A", "outputs/a.txt", "from-a")
    _make_parked(sandbox["projects"], "B", "outputs/b.txt", "from-b")

    server_utils.switch_active_project("A")
    assert (sandbox["active"] / "outputs" / "a.txt").read_text() == "from-a"
    assert not (sandbox["projects"] / "A").exists()
    assert (sandbox["projects"] / "B").exists()

    server_utils.switch_active_project("B")
    assert (sandbox["active"] / "outputs" / "b.txt").read_text() == "from-b"
    assert not (sandbox["active"] / "outputs" / "a.txt").exists()
    assert (sandbox["projects"] / "A" / "outputs" / "a.txt").read_text() == "from-a"


# ---------------------------------------------------------------------------
# T2 — agent tools cannot reach parked storage
# ---------------------------------------------------------------------------


def test_parked_storage_unreachable_via_tools(sandbox):
    """The agent's path resolver and glob/grep cannot reach ../projects."""
    _make_parked(sandbox["projects"], "B", "outputs/secret.txt", "leaked")

    # _resolve_artifact_path: relative ../projects escapes DATA_DIR boundary.
    with pytest.raises(ValueError):
        agent_tools._resolve_artifact_path("../projects/B/outputs/secret.txt")

    # Absolute path into parked storage also rejected (outside DATA_DIR).
    parked_abs = str(sandbox["projects"] / "B" / "outputs" / "secret.txt")
    with pytest.raises(ValueError):
        agent_tools._resolve_artifact_path(parked_abs)

    # glob/grep walk only the allowlisted roots → no leak.
    assert agent_tools._glob("../projects/**").startswith("No matches")
    assert agent_tools._glob("projects/**").startswith("No matches")
    assert "secret" not in agent_tools._grep("leaked", include="**/*")


# ---------------------------------------------------------------------------
# T3 — kernel cwd is invariant; switch forces restart
# ---------------------------------------------------------------------------


def test_switch_forces_kernel_restart(sandbox):
    """Every project switch calls force_restart=True then re-arms."""
    _make_parked(sandbox["projects"], "A", "outputs/a.txt", "a")
    _make_parked(sandbox["projects"], "B", "outputs/b.txt", "b")

    sandbox["restart_calls"].clear()
    server_utils.switch_active_project("A")
    server_utils.switch_active_project("B")

    # Each switch should produce (force_restart=True, then re-arm=False).
    # Our stubs record True for force_restart, False for re-arm.
    assert sandbox["restart_calls"] == [True, False, True, False]


# ---------------------------------------------------------------------------
# T4 — recovery cases
# ---------------------------------------------------------------------------


def test_recovery_b1_no_project_dir(sandbox):
    """B.1: project/ absent → mkdir empty shell, return None."""
    # Sandbox fixture pre-creates the dir; remove it for B.1.
    import shutil
    shutil.rmtree(sandbox["active"])
    assert server_utils.recover_active_project() is None
    assert sandbox["active"].exists()
    assert (sandbox["active"] / "outputs").is_dir()


def test_recovery_b2_with_pid(sandbox):
    """B.2: project/ + .project_id → return that id."""
    (sandbox["active"] / ".project_id").write_text("X")
    assert server_utils.recover_active_project() == "X"


def test_recovery_b3_no_pid(sandbox):
    """B.3: project/ without .project_id → return None (anonymous shell)."""
    assert server_utils.recover_active_project() is None


def test_recovery_b4_collision(sandbox):
    """B.4: parked twin exists → rescue it, return id."""
    (sandbox["active"] / ".project_id").write_text("Z")
    _make_parked(sandbox["projects"], "Z", "outputs/old.txt", "stale")

    assert server_utils.recover_active_project() == "Z"
    # Parked twin should have been renamed with __rescued_<ts> suffix.
    rescued = [p for p in sandbox["projects"].iterdir() if p.name.startswith("Z__rescued_")]
    assert len(rescued) == 1
    assert not (sandbox["projects"] / "Z").exists()


def test_recovery_b5_only_parked(sandbox):
    """B.5: only parked exists → mkdir empty shell, return None."""
    _make_parked(sandbox["projects"], "Q", "outputs/q.txt", "q")
    import shutil
    shutil.rmtree(sandbox["active"])
    assert server_utils.recover_active_project() is None
    assert sandbox["active"].exists()
    assert (sandbox["projects"] / "Q").exists()


# ---------------------------------------------------------------------------
# T5 — delete active project parks-then-removes
# ---------------------------------------------------------------------------


def test_delete_active_project_parks_then_removes(sandbox):
    """Deleting the active project parks it first; ends with empty shell."""
    _make_parked(sandbox["projects"], "A", "outputs/a.txt", "a")
    server_utils.switch_active_project("A")
    assert server_utils.read_active_project_id() == "A"

    # Simulate the /delete handler: park then rmtree.
    server_utils.switch_active_project(None)
    assert server_utils.read_active_project_id() is None
    assert (sandbox["projects"] / "A").exists()

    import shutil
    shutil.rmtree(sandbox["projects"] / "A")
    assert not (sandbox["projects"] / "A").exists()
    # Active shell still present and empty.
    assert sandbox["active"].exists()
    assert (sandbox["active"] / "outputs").is_dir()
    assert not (sandbox["active"] / ".project_id").exists()


# ---------------------------------------------------------------------------
# T6 — pre-mint upload, mint, no movement
# ---------------------------------------------------------------------------


def test_pre_mint_upload_then_mint_no_movement(sandbox):
    """File dropped pre-mint stays at the same inode after .project_id is written."""
    uploads = sandbox["active"] / "uploads"
    foo = uploads / "foo.csv"
    foo.write_text("a,b\n1,2\n")
    inode_before = foo.stat().st_ino

    server_utils.write_active_project_id("2026-06-28_15-00-00")
    assert server_utils.read_active_project_id() == "2026-06-28_15-00-00"
    assert foo.stat().st_ino == inode_before


# ---------------------------------------------------------------------------
# T7 — dotfile hidden from default glob
# ---------------------------------------------------------------------------


def test_chat_dotfile_hidden_from_default_glob(sandbox):
    """`.chat.json` doesn't appear in glob('**/*') (pathlib excludes dotfiles)."""
    (sandbox["active"] / ".chat.json").write_text("{}")
    (sandbox["active"] / ".project_id").write_text("Z")
    (sandbox["active"] / "outputs" / "visible.txt").write_text("hi")

    out = agent_tools._glob("**/*")
    assert ".chat.json" not in out
    assert ".project_id" not in out
    assert "outputs/visible.txt" in out

    # Explicit match still works (this is convention, not enforcement).
    explicit = agent_tools._glob("**/.chat.json")
    assert ".chat.json" in explicit


# ---------------------------------------------------------------------------
# T8 — end-to-end migration
# ---------------------------------------------------------------------------


def test_migrations_end_to_end(sandbox):
    """Old layout (workspace/projects/X, workspace/plan_scratch, workspace/scratch)
    is reshaped into the new layout."""
    # Build old-style layout inside the patched workspace.
    old_projects = sandbox["workspace"] / "projects"
    (old_projects / "X" / "outputs").mkdir(parents=True)
    (old_projects / "X" / "chat.json").write_text('{"title":"X"}')

    old_plan = sandbox["workspace"] / "plan_scratch"
    old_plan.mkdir(exist_ok=True)
    (old_plan / "plan.md").write_text("# plan")

    old_scratch_up = sandbox["workspace"] / "scratch" / "uploads"
    old_scratch_up.mkdir(parents=True)
    (old_scratch_up / "bar.csv").write_text("x")

    server_utils.migrate_projects_out_of_workspace()
    server_utils.migrate_plan_scratch_out_of_workspace()
    server_utils.migrate_chat_json_to_dotfile()
    server_utils.migrate_scratch_into_active_project()

    # Project moved out of workspace and chat.json renamed.
    assert (sandbox["projects"] / "X" / ".chat.json").exists()
    assert not (sandbox["projects"] / "X" / "chat.json").exists()
    assert not (sandbox["workspace"] / "projects").exists()

    # Plan scratch moved out.
    assert (sandbox["plan_scratch"] / "plan.md").read_text() == "# plan"
    assert not (sandbox["workspace"] / "plan_scratch").exists()

    # Scratch contents migrated into active project uploads.
    assert (sandbox["active"] / "uploads" / "bar.csv").read_text() == "x"
    assert not (sandbox["workspace"] / "scratch").exists()
