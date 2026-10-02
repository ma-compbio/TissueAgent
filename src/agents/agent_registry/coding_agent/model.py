"""Canonical coding agent built on the ``deepagents`` harness.

The cached persistent-kernel implementation remains available at
:mod:`agents.agent_registry.coding_agent_cache.model` and can be selected with
``TISSUEAGENT_CODING_AGENT=cache``.

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
* **R is opt-in per step, via the ``r-execution`` skill.** When the recruiter
  assigns that skill to a step, the agent additionally gets an ``r()`` tool
  backed by the sandbox's persistent IRkernel (the same ``KernelClient`` the
  stock agent uses). Steps without the skill get a prompt and tool set
  byte-identical to before — Python-only tasks never see R.
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

from graph.ui_events import (
    emit_message,
    emit_subagent_token,
    stash_completed_subagent,
    subagent_invocation,
)

# The ``CustomAgent`` id is "coding" but the node id — and so the transfer-tool
# name the manager dispatches through — is "coding_agent". Keep both literals
# identical to the stock agent so the variants are swappable.
AGENT_NODE_ID = "coding_agent"
AGENT_DISPLAY_NAME = "Coding Agent"

# Where ``sync_workspace_skills`` materializes this step's folder skills, as a
# path *relative to the backend root* (DATA_DIR). deepagents resolves skill
# sources through the backend's filesystem tools, where an absolute host path
# outside DATA_DIR fails with ``path_not_found``.
WORKSPACE_SKILLS_SOURCE = "/project/skills"

# The recruiter-assigned skill that turns on the ``r`` tool for a step. Kept as
# a name check (not a registry lookup) so a missing/renamed skill folder can
# never break agent construction — it just means no step ever carries the name.
R_SKILL_NAME = "r-execution"


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


def create_coding_agent(
    state_queue: Queue,
    kernel_client=None,
    context_resolver=None,
):
    """Build the deepagents-backed coding agent as a ``StructuredTool``.

    Args:
        state_queue: Queue finished sub-agent states are posted to for the UI.
            Receives ``(agent_id, final_state, invocation_id)``.
        kernel_client: Client for the sandbox's Jupyter kernels. Shell
            execution never touches it; it only backs the ``r`` tool, which
            exists solely on steps the recruiter assigned the ``r-execution``
            skill to. ``graph.py`` filters ctor kwargs by
            ``inspect.signature``, so the parameter name must match the stock
            agent's.
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
    from agents.agent_registry.coding_agent_cache.params import coding_agent_model_ctor
    from config import DATA_DIR

    backend = LocalShellBackend(
        root_dir=str(DATA_DIR),
        virtual_mode=True,
        inherit_env=True,
        env=_shell_env(),
    )
    model = coding_agent_model_ctor()

    def _system_prompt(include_r: bool) -> str:
        """Base prompt, with the kernel-specific guidance replaced.

        The stock prompt documents ``python()``/``r()`` tools and the
        ``{{skill_prompt}}`` injection point, neither of which exists here.
        Rather than fork the whole prompt, we keep its domain guidance (paths,
        workspace policy, output schema) and overwrite the parts that would
        instruct the model to call tools it does not have.

        With ``include_r`` (the step carries the ``r-execution`` skill) the
        ``r`` tool exists, so its guidance is appended and the "no R kernel"
        claim corrected. Without it, the output is byte-identical to the
        pre-R prompt — Python-only steps must not pay for R in tokens or
        distraction.
        """
        base = CodingAgentPrompt(sandbox_enabled=False)
        note = _SHELL_EXECUTION_NOTE
        if include_r:
            note = (
                note.replace("You have no Python/R kernel.", "You have no Python kernel.")
                + _R_EXECUTION_NOTE
            )
        return base.replace("{{skill_prompt}}", note)

    def _r(code: str) -> str:
        """Execute R in the sandbox's persistent IRkernel via ``kernel_client``.

        Text-only return: the deepagents tool loop carries strings, not the
        stock agent's multimodal parts, so inline plots are spilled to files
        under the project's ``outputs/figures/_trace/`` and returned as paths —
        consistent with this variant's figures-are-files policy.
        """
        logging.info("r tool executing:\n%s", code)
        result = kernel_client.execute(code, language="r")
        logging.info("r tool output:\n%s", result.text)
        text = result.text
        if result.images:
            from agents.agent_registry.coding_agent_cache.image_spill import (
                spill_images_to_disk,
            )

            paths = spill_images_to_disk(result.images)
            if paths:
                listing = "\n".join(f"project/{p}" for p in paths)
                text += f"\n[Inline plots were saved to:\n{listing}]"
        return text

    r_tool = StructuredTool.from_function(
        func=_r,
        name="r",
        description=(
            "Execute R code in a persistent Jupyter kernel and return its output."
            " The kernel retains state (variables, libraries, definitions) across calls."
            " Use cat() or print() to surface values you need to inspect."
        ),
    )

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
                "coding_agent: materialized skills %s for step %s",
                materialized,
                step_ctx.step_id if step_ctx else None,
            )
        except Exception as e:
            logging.warning("per-step skill materialization failed: %s", e)

        # The r tool exists only on steps the recruiter assigned the
        # r-execution skill to; every other step gets the exact pre-R prompt
        # and tool set. Guarded on kernel_client so a caller that never wired
        # a kernel backend degrades to Python-only rather than a broken tool.
        use_r = kernel_client is not None and R_SKILL_NAME in skills
        system_prompt = _system_prompt(include_r=use_r)

        # Rebuilt per invocation: the skills index is read at agent-build time,
        # and each step materializes a different set. Construction is cheap next
        # to a single LLM round-trip.
        agent = create_deep_agent(
            model=model,
            tools=[r_tool] if use_r else None,
            system_prompt=system_prompt,
            backend=backend,
            skills=[WORKSPACE_SKILLS_SOURCE],
        )

        with subagent_invocation(
            AGENT_DISPLAY_NAME,
            step_id=step_ctx.step_id if step_ctx else None,
        ) as invocation_id:
            from agents.agent_registry.coding_agent.tracing import consume_deep_agent_stream
            from config import EXECUTOR_RECURSION_LIMIT

            final_state = consume_deep_agent_stream(
                agent,
                {"messages": [HumanMessage(prompt)]},
                {"recursion_limit": EXECUTOR_RECURSION_LIMIT},
                on_token=emit_subagent_token,
                on_message=lambda message, stream_id, source: emit_message(
                    message,
                    stream_id=stream_id,
                    source=source,
                ),
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

# Appended to the execution note only when the step carries the r-execution
# skill (and so the ``r`` tool). Python-only steps never see this text.
_R_EXECUTION_NOTE = """
## R execution (this step)

This step was assigned the `r-execution` skill, so you additionally have an
`r` tool: it runs R code in a persistent Jupyter kernel. Unlike `execute`,
**state persists across `r` calls** — variables, loaded libraries and in-memory
objects survive from one call to the next.

- Use `r` only for the work that needs R packages (e.g. Seurat, Bioconductor);
  keep everything else in Python via `execute`.
- The same workspace-relative paths apply (`project/uploads/...`,
  `project/outputs/...`). Exchange data with Python through files
  (`.csv`, `.rds`), not memory.
- Save figures to `project/outputs/figures/` (`ggsave()`, or
  `png(...); ...; dev.off()`). An inline plot you don't save is auto-spilled
  to a file and its path returned in the tool output.
- `project/skills/r-execution/SKILL.md` has full guidance, including package
  installation.
"""
