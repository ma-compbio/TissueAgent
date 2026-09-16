"""The skill assets-root path handed to sub-agents must be workspace-relative.

Regression guard for a bug where ``format_skill_prompt`` advertised an absolute
container path (``/workspace/project/skills/...``). The agent file tools reject
absolute paths outright ("Non-relative patterns are unsupported"), so every
folder skill's bundled ``scripts/`` were unreachable whenever the sandbox was
off — sub-agents silently hand-rolled the code those scripts provide.
"""

import pytest

from agents.agent_tools import glob_tool
from agents.agent_utils import format_skill_prompt
from agents.recruiter_agent.prompt import get_skill_metadata
from agents.skills_workspace import sync_workspace_skills
from knowledge import SKILLS_DIR


def _folder_skills() -> list[str]:
    root = SKILLS_DIR.resolve()
    return sorted(
        name
        for name, meta in get_skill_metadata().items()
        if meta.path.parent.resolve() != root
    )


def _assets_root(prompt: str) -> str | None:
    marker = "**Assets root:** `"
    i = prompt.find(marker)
    if i == -1:
        return None
    start = i + len(marker)
    return prompt[start : prompt.index("`", start)].rstrip("/")


@pytest.mark.parametrize("name", _folder_skills())
def test_assets_root_is_relative_and_reachable(name: str) -> None:
    """The advertised path must be relative and resolve through the agent's own glob."""
    sync_workspace_skills([name])
    root = _assets_root(format_skill_prompt([name]))

    assert root is not None, f"{name}: no assets-root note emitted"
    assert not root.startswith("/"), f"{name}: absolute path {root!r} — file tools reject these"
    assert root == f"project/skills/{name}"

    # The decisive check: the path the prompt hands the agent must actually
    # work in the tool the agent would use to reach it.
    out = glob_tool.func(f"{root}/*")
    assert "unsupported" not in out.lower(), f"{name}: glob rejected {root!r}"
    assert f"{root}/scripts" in out, f"{name}: scripts/ not reachable at {root!r}"
