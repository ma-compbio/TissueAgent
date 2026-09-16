"""Selection tests for the canonical and cached coding-agent implementations."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent


def _selection(env_value: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src")))
    env["MPLCONFIGDIR"] = str(tmp_path / "matplotlib")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    if env_value:
        env["TISSUEAGENT_CODING_AGENT"] = env_value
    else:
        env.pop("TISSUEAGENT_CODING_AGENT", None)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from agents.coding_agent_selection import "
                "coding_agent_ctor, coding_agent_implementation; "
                "print(coding_agent_implementation()); "
                "print(coding_agent_ctor().__module__)"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("env_value", "implementation", "module"),
    [
        ("", "deepagent", "agents.agent_registry.coding_agent.model"),
        ("deepagent", "deepagent", "agents.agent_registry.coding_agent.model"),
        ("cache", "cache", "agents.agent_registry.coding_agent_cache.model"),
        ("stock", "cache", "agents.agent_registry.coding_agent_cache.model"),
    ],
)
def test_coding_agent_selection(
    env_value: str,
    implementation: str,
    module: str,
    tmp_path: Path,
) -> None:
    """DeepAgent is canonical while cache and stock retain the legacy implementation."""
    result = _selection(env_value, tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-2:] == [implementation, module]


def test_unknown_coding_agent_selection_is_rejected(tmp_path) -> None:
    """A misspelled implementation name must not silently change behavior."""
    result = _selection("unknown", tmp_path)

    assert result.returncode != 0
    assert "Unsupported TISSUEAGENT_CODING_AGENT" in result.stderr
