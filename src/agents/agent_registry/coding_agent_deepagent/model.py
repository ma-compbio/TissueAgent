"""Coding agent built on the ``deepagents`` harness (experimental).

A drop-in alternative to :mod:`agents.agent_registry.coding_agent.model` that
uses deepagents *natively* — its own agent loop, its own filesystem/shell tools,
and its own progressive-disclosure skills middleware — so the harness can be
evaluated on its own terms rather than as a wrapper around our existing pieces.

Selected at run time with ``TISSUEAGENT_CODING_AGENT=deepagent`` (see
``agents.agent_defns._coding_agent_ctor``); unset, the stock agent is used.

What the agent gets
-------------------
``ls`` / ``read_file`` / ``write_file`` / ``edit_file`` / ``delete`` / ``glob`` /
``grep`` / ``execute`` / ``task``, plus a skills index. ``edit_file`` and
``task`` have no equivalent in the stock agent.

Deliberate differences from the stock coding agent
--------------------------------------------------
* **Execution is shell, not a Jupyter kernel.** ``execute`` runs
  ``subprocess.run(shell=True)`` locally through ``LocalShellBackend`` — no
  sandbox service, no API key. The consequence is that **execution is
  stateless**: each call is a fresh process, so nothing survives between calls
  (verified: ``export FOO=42`` then ``echo $FOO`` returns empty). A large
  ``.h5ad`` must be re-read per invocation, or the work written as a script.
* **No R tool.** Neither environment ships an ``ir`` kernel, so an ``r()`` tool
  would only ever fail; offering it invites the model to waste turns.
* **No ``analysis.ipynb``, no inline plot capture, no executor failure budget.**
  All three are implemented inside ``KernelClient.execute``, which is not in
  this variant's path. Figures reach the user as files under
  ``project/outputs/`` rather than as trace images.
* **Skills are model-selected, not recruiter-injected.** deepagents indexes each
  skill's ``name``/``description`` at startup and the model reads the body on
  demand. Our ``strict: true`` guarantee therefore does not apply here — that is
  the trade being evaluated.

The graph integration contract is identical to the stock agent's, so the two are
interchangeable without touching ``graph.py``, ``cli.py`` or the manager.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from queue import Queue

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from graph.ui_events import stash_completed_subagent, subagent_invocation

# The ``CustomAgent`` id is "coding" but the node id — and so the transfer-tool
# name the manager dispatches through — is "coding_agent". Keep both literals
# identical to the stock agent so the variants are swappable.
AGENT_NODE_ID = "coding_agent"
AGENT_DISPLAY_NAME = "Coding Agent"

# Where ``sync_workspace_skills`` materializes this step's folder skills, as a
# path *relative to the backend root* (DATA_DIR). deepagents resolves skill
# sources through the backend, and ``virtual_mode=True`` confines it to that
# root — an absolute host path outside DATA_DIR fails with ``path_not_found``.
WORKSPACE_SKILLS_SOURCE = "/project/skills"


def _shell_env() -> dict[str, str]:
    """PATH override so the agent's shell reaches *this* interpreter's env.

    ``LocalShellBackend`` defaults to ``inherit_env=False``, under which the
    shell cannot even find ``python3`` (exit 127). Merely inheriting is not
    enough either: on a conda install ``which python3`` then resolves to *base*,
    where scanpy and friends are absent. Prepending the running interpreter's
    ``bin`` directory is what makes ``python3 -c "import scanpy"`` work.
    """
    bindir = str(Path(sys.executable).parent)
    return {"PATH": bindir + os.pathsep + os.environ.get("PATH", "")}


def create_coding_agent_deep(
    state_queue: Queue,
    kernel_client=None,
    context_resolver=None,
):
    """Build the deepagents-backed coding agent as a ``StructuredTool``.

    Args:
        state_queue: Queue finished sub-agent states are posted to for the UI.
            Receives ``(agent_id, final_state, invocation_id)``.
        kernel_client: Accepted for signature compatibility with the stock
            agent and **unused** — this variant executes through the shell.
            ``graph.py`` filters ctor kwargs by ``inspect.signature``, so the
            parameter must stay for the shared call site to keep working.
        context_resolver: Optional ``Callable[[str], StepContext | None]``
            resolving the currently-running plan step.

    Returns:
        A ``StructuredTool`` named ``coding_agent_transfer_tool`` taking a
        single ``prompt`` argument.
    """
    # Imported lazily so this module stays importable (and the app bootable)
    # where deepagents is absent; only building the agent needs it.
    from deepagents import create_deep_agent
    from deepagents.backends import LocalShellBackend

    from agents.agent_registry.coding_agent.prompt import CodingAgentPrompt
    from agents.agent_registry.coding_agent.params import coding_agent_model_ctor
    from config import DATA_DIR

    backend = LocalShellBackend(
        root_dir=str(DATA_DIR),
        virtual_mode=True,  # blocks ../ and ~ traversal out of the workspace
        inherit_env=True,
        env=_shell_env(),
    )
    model = coding_agent_model_ctor()

    def _system_prompt() -> str:
        """Base prompt, with the kernel-specific guidance replaced.

        The stock prompt documents ``python()``/``r()`` tools and the
        ``{{skill_prompt}}`` injection point, neither of which exists here.
        Rather than fork the whole prompt, we keep its domain guidance (paths,
        workspace policy, output schema) and overwrite the parts that would
        instruct the model to call tools it does not have.
        """
        base = CodingAgentPrompt(sandbox_enabled=False)
        return base.replace("{{skill_prompt}}", _SHELL_EXECUTION_NOTE)

    def agent_invocation_tool(prompt: str) -> str:
        """Run the deep agent on a prompt and return its final message."""
        logging.info("Invoking agent `%s` (deepagents)", AGENT_NODE_ID)
        try:
            from server.executor_tracker import executor_tracker

            executor_tracker.begin_step()
        except Exception as e:  # metrics must never break a dispatch
            logging.debug("executor_tracker: could not mark step boundary: %s", e)

        step_ctx = context_resolver(AGENT_NODE_ID) if context_resolver else None

        # Materialize this step's folder skills into the workspace so the
        # middleware can index them: deepagents reads skill sources *through*
        # the backend, which cannot see outside DATA_DIR. Passing an empty list
        # clears the tree, so an unskilled step correctly sees no skills.
        skills = list(step_ctx.skills) if step_ctx else []
        try:
            from agents.skills_workspace import sync_workspace_skills

            from config import active_project_skills

            materialized = sync_workspace_skills(skills)
            # ``sync_workspace_skills([])`` rmtree's the whole tree, which would
            # leave the skills source path missing and make the middleware warn
            # "path_not_found" on every skill-less step. Recreate the (empty)
            # directory so an empty index is reported as empty rather than as a
            # load failure — otherwise a real failure is indistinguishable from
            # the normal no-skills case.
            active_project_skills().mkdir(parents=True, exist_ok=True)
            logging.info(
                "coding_agent_deepagent: materialized skills %s for step %s",
                materialized,
                step_ctx.step_id if step_ctx else None,
            )
        except Exception as e:
            logging.warning("per-step skill materialization failed: %s", e)

        system_prompt = _system_prompt()

        # Rebuilt per invocation: the skills index is read at agent-build time,
        # and each step materializes a different set. Construction is cheap next
        # to a single LLM round-trip.
        agent = create_deep_agent(
            model=model,
            system_prompt=system_prompt,
            backend=backend,
            skills=[WORKSPACE_SKILLS_SOURCE],
        )

        with subagent_invocation(
            AGENT_DISPLAY_NAME,
            step_id=step_ctx.step_id if step_ctx else None,
        ) as invocation_id:
            from config import EXECUTOR_RECURSION_LIMIT

            final_state = agent.invoke(
                {"messages": [HumanMessage(prompt)]},
                config={"recursion_limit": EXECUTOR_RECURSION_LIMIT},
            )

        # deepagents owns its state schema, so the fields our trace UI reads are
        # not written for us. Attach them so the trace card shows the prompt the
        # agent ran with and this step's skill chips.
        if isinstance(final_state, dict):
            final_state["system_prompt"] = system_prompt
            final_state["step_skills"] = skills

        state_queue.put((AGENT_NODE_ID, final_state, invocation_id))
        # Must run on this thread before returning: the wrapping tool_node pops
        # it right after emitting the dispatching ToolMessage, which is what
        # flips the live trace card to the finished card inline.
        stash_completed_subagent(AGENT_NODE_ID, final_state, invocation_id)
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{AGENT_NODE_ID}_transfer_tool",
        description=f"Transfer control to {AGENT_NODE_ID}",
    )


# Replaces the stock prompt's ``{{skill_prompt}}`` block. The stock text tells
# the model to call python()/r(); this variant has neither, so it needs to know
# how code actually runs — and, critically, that nothing persists between calls.
_SHELL_EXECUTION_NOTE = """\
## Running code

You have no Python/R kernel. Run code with the `execute` tool, which runs a
shell command from the workspace root (e.g. `python3 script.py`, or
`python3 -c "..."` for a one-liner).

**Each `execute` call is a fresh process — nothing persists between calls.**
Variables, imports and loaded datasets are gone the moment a command returns.
So for anything beyond a trivial check:

- Write a self-contained script under `project/outputs/scripts/` with
  `write_file`, then run it with `execute`. Amend it with `edit_file` and re-run
  rather than pasting ever-longer `-c` one-liners.
- Have scripts persist what the next step needs (a `.csv`, a `.h5ad`, a `.json`)
  instead of assuming state carries over.
- Save figures to files under `project/outputs/figures/`; plots are not captured
  inline. Inspect a written figure by reading it back if you need to check it.

Use `python3` (not `python`). Prefer `read_file`/`write_file`/`edit_file`/`glob`/
`grep` over shelling out to `cat`, `sed` or `find`.
"""
