"""Regression tests for kernel workspace seeding (coding_agent/sandbox.py).

``_seed_kernel`` chdirs a freshly-started kernel into the workspace the server
configured (``DATA_DIR`` — see ``server/utils.py:973``). It was defined,
documented, and never called, so kernels kept whatever cwd the gateway was
launched with. That happens to be ``DATA_DIR`` when the server starts the gateway
itself, which is why this went unnoticed — but it breaks the moment the gateway
is launched from anywhere else (an operator-run gateway, a different service
dir), and the workspace-relative paths the prompt mandates
(``project/outputs/figures/x.png``) then resolve against the wrong root.

These tests pin the call so it cannot be dropped again by a dead-code cleanup.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.agent_registry.coding_agent.sandbox import KernelClient


@pytest.fixture
def client(monkeypatch):
    """A KernelClient whose kernel-start HTTP call is stubbed out."""
    kc = KernelClient(base_url="http://127.0.0.1:9999")

    resp = MagicMock()
    resp.json.return_value = {"id": "kernel-123"}
    resp.raise_for_status.return_value = None
    monkeypatch.setattr(
        "agents.agent_registry.coding_agent.sandbox.requests.post", lambda *a, **k: resp
    )
    return kc


def test_starting_a_kernel_seeds_its_working_directory(client, tmp_path):
    """A new kernel must chdir into the workspace before running agent code."""
    client.set_workspace(tmp_path)

    with patch.object(client, "execute") as mock_exec:
        client._get_or_start_kernel("python")

    mock_exec.assert_called_once()
    seed_code = mock_exec.call_args[0][0]
    assert "os.chdir" in seed_code
    assert str(tmp_path) in seed_code


def test_seeding_is_idempotent_per_language(client, tmp_path):
    """The chdir runs once per kernel, not on every execute."""
    client.set_workspace(tmp_path)

    with patch.object(client, "execute") as mock_exec:
        client._get_or_start_kernel("python")
        client._get_or_start_kernel("python")  # cached; must not re-seed

    assert mock_exec.call_count == 1


def test_r_kernels_seed_with_r_syntax(client, tmp_path):
    """R uses setwd(), not os.chdir — seeding must not emit Python into IRkernel."""
    client.set_workspace(tmp_path)

    with patch.object(client, "execute") as mock_exec:
        client._get_or_start_kernel("r")

    seed_code = mock_exec.call_args[0][0]
    assert "setwd(" in seed_code
    assert "os.chdir" not in seed_code


def test_seeding_is_skipped_when_no_workspace_set(client):
    """Without a workspace there is nothing to chdir into; don't invent one."""
    with patch.object(client, "execute") as mock_exec:
        client._get_or_start_kernel("python")

    mock_exec.assert_not_called()


def test_seed_executions_are_flagged_internal(client, tmp_path):
    """Seeding must not land in the analysis notebook.

    ``_internal_exec`` is what keeps chdir boilerplate out of the record; it also
    stops the seed's own execute() from recursing back through the logger.
    """
    client.set_workspace(tmp_path)
    seen = []

    def _spy(code, language="python"):
        seen.append(client._internal_exec)
        return MagicMock(text="", images=[], error=False)

    with patch.object(client, "execute", side_effect=_spy):
        client._get_or_start_kernel("python")

    assert seen == [True], "seed execution must run with _internal_exec set"
    assert client._internal_exec is False, "flag must be restored afterwards"
