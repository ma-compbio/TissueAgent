"""CodeAct-style hypothesis agent with a persistent Python REPL for hypothesis synthesis."""

from __future__ import annotations

import ast
import builtins
from collections.abc import Callable
import logging
from pathlib import Path
from queue import Queue
import re


from langchain_core.tools import StructuredTool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_utils import extract_block
from agents.agent_registry.hypothesis_agent.tools import HypothesisTools
from agents.repl_history import compress_repl_history
from langchain_experimental.utilities import PythonREPL
from agents.agent_registry.hypothesis_agent.prompt import (
    HypothesisAgentPrompt,
    HypothesisAgentDescription,
)
from graph.ui_events import emit_message, stash_completed_subagent, subagent_invocation

from config import DATA_DIR, LIBRARY_DIR, PDF_UPLOADS_DIR, active_project_outputs


class HypothesisState(MessagesState):
    """Extended message state carrying the current code/response block.

    The persistent ``PythonREPL`` used by ``exec_node`` is not part of this state. It
    lives in a closure-local holder so it never reaches the checkpointer. The closure
    keeps the REPL alive across invocations so prior hypothesis variables remain available.
    """

    status_block: str  # content of <execute> or <response> block
    skill_prompt: str  # injected skill content for system prompt
    system_prompt: str  # fully-rendered system prompt, surfaced in the trace UI


def _extract_executable_code(text: str, *, allow_fenced_python: bool) -> str | None:
    """Extract tagged code, or one fenced Python block in benchmark mode."""
    tagged = extract_block("execute", text)
    if tagged is not None:
        if allow_fenced_python and "```" in text:
            return None
        return tagged
    if not allow_fenced_python:
        return None
    if re.search(r"(?i)<\s*(?:execute|response)\b", text) or text.count("```") != 2:
        return None
    match = re.search(r"(?is)```([^\r\n`]*)\r?\n(.*?)```", text)
    if match is None or match.group(1).strip().casefold() != "python":
        return None
    code = match.group(2).strip()
    return code or None


def create_hypothesis_agent(
    state_queue: Queue,
    context_resolver=None,
    prompt_override: str | Callable[[], str] | None = None,
    sandbox_root: Path | None = None,
    artifact_validator: Callable[[str, object], None] | None = None,
    stop_after_write: bool = False,
):
    """Build and return the hypothesis agent as a StructuredTool.

    Args:
        state_queue: Queue to which finished agent states are posted for UI consumption.
        context_resolver: Optional callable that resolves skill/artifact context for a step.
        prompt_override: Optional benchmark-specific system prompt or zero-argument prompt
            provider. Production callers omit this and use :data:`HypothesisAgentPrompt`.
        sandbox_root: Optional benchmark-only REPL boundary. When set, generated code can
            read and write only relative paths below this directory.
        artifact_validator: Optional benchmark-only callback run before a JSON artifact
            is written. Production callers leave it unset.
        stop_after_write: End a benchmark invocation after its first successful JSON write.

    Returns:
        A StructuredTool that invokes the hypothesis agent graph with a text prompt.
    """
    graph = StateGraph(HypothesisState)
    id = "hypothesis"

    ### Tools

    tools = HypothesisTools

    ### Model

    from agents.agent_registry.hypothesis_agent.params import model_ctor

    model = model_ctor()

    agent_node_id = "agent_node"
    exec_node_id = "exec_node"

    def agent_node(state: HypothesisState):
        """Invoke the LLM and route to exec or END based on block type."""
        if stop_after_write and successful_writes:
            return Command(goto=END)
        messages = state["messages"]
        skill_text = state.get("skill_prompt", "")
        base_prompt = prompt_override() if callable(prompt_override) else prompt_override
        base_prompt = base_prompt or HypothesisAgentPrompt
        full_prompt = base_prompt.replace("{{skill_prompt}}", skill_text)
        system_prompt = SystemMessage(full_prompt)

        # Strategy 2H: collapse older REPL iterations before re-sending.
        compressed = compress_repl_history(messages)

        logging.info(f"invoking {id} agent_node")
        response = model.invoke([system_prompt] + compressed)
        logging.info(f"finished invoking {id} agent_node")

        response.name = id
        emit_message(response)

        response_text = str(response.content)
        code_block = _extract_executable_code(
            response_text,
            allow_fenced_python=sandbox_root is not None,
        )
        response_block = extract_block("response", response_text)

        response_msg = [response]
        if code_block:
            logging.info("code block detected - transferring to exec_node")
            next_node = exec_node_id
            update = {"messages": response_msg, "status_block": code_block}
        elif stop_after_write:
            if response_block:
                reason = "A validated artifact must be written before returning a response."
            else:
                reason = (
                    "Expected exactly one <execute> block or one complete Python-fenced "
                    "block that writes the requested artifact."
                )
            raise RuntimeError(reason)
        elif response_block:
            logging.info("response block detected - final output, exiting")
            next_node = END
            update = {"messages": response_msg}
        else:
            logging.info("no execute or response block - treating as direct response and exiting")
            next_node = END
            update = {"messages": response_msg}

        logging.info(f"transferring from agent_node to {next_node}")
        return Command(
            goto=next_node,
            update={**update, "system_prompt": full_prompt},
        )

    # Closure-local holder. Persists across multiple ``agent_invocation_tool``
    # calls so the hypothesis agent's Python namespace survives manager
    # round-trips (matches the prior ``_persistent_repl_state`` behavior).
    repl_holder: dict = {"repl": None}
    successful_writes: set[str] = set()
    validated_write_payloads: dict[str, str] = {}
    write_violations: list[str] = []

    def exec_node(state: HypothesisState):
        """Extract and run the <execute> code block in a persistent Python REPL."""
        code_block = state.get("status_block")

        logging.info(f"executing {id} exec_node")

        assert code_block is not None

        if sandbox_root is not None:
            try:
                tree = ast.parse(code_block)
            except SyntaxError as exc:
                return {"messages": [HumanMessage(f"Python Error:\n{exc}")]}
            blocked_names = {
                "breakpoint",
                "compile",
                "eval",
                "exec",
                "getattr",
                "globals",
                "input",
                "locals",
                "open",
                "setattr",
                "vars",
                "__import__",
            }
            protected_helpers = {"read_json", "read_text", "write_json"}
            violations: set[str] = set()
            shadowed_helpers: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    violations.add("Imports are disabled in benchmark sandbox mode.")
                if isinstance(node, (ast.Global, ast.Nonlocal)):
                    violations.add(
                        "Global namespace changes are disabled in benchmark sandbox mode."
                    )
                if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                    violations.add(
                        "Private attribute access is disabled in benchmark sandbox mode."
                    )
                if isinstance(node, ast.Name) and node.id in blocked_names:
                    violations.add(f"{node.id} is disabled in benchmark sandbox mode.")
                if (
                    isinstance(node, ast.Name)
                    and node.id in protected_helpers
                    and isinstance(node.ctx, (ast.Store, ast.Del))
                ):
                    shadowed_helpers.add(node.id)
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and node.name in protected_helpers
                ):
                    shadowed_helpers.add(node.name)
                if isinstance(node, ast.arg) and node.arg in protected_helpers:
                    shadowed_helpers.add(node.arg)
                if isinstance(node, ast.ExceptHandler) and node.name in protected_helpers:
                    shadowed_helpers.add(node.name)
            if shadowed_helpers:
                names = ", ".join(sorted(shadowed_helpers))
                violations.add(
                    f"Do not define, overwrite, or delete provided helpers: {names}."
                )
            if violations:
                details = "\n".join(f"- {violation}" for violation in sorted(violations))
                return {"messages": [HumanMessage(f"Python Error:\n{details}")]}

        # Validate code doesn't call forbidden functions
        forbidden_calls = ["jupyternb_generator_tool", "generate_jupyternb"]
        for forbidden in forbidden_calls:
            if forbidden in code_block:
                error_msg = (
                    f"Error: {forbidden}() is not available in Hypothesis Agent.\n"
                    f"Only Reporter Agent can generate notebooks.\n"
                    f"Your role is to synthesize hypotheses, not generate notebooks."
                )
                logging.warning(f"Blocked forbidden function call: {forbidden}")
                return {
                    "messages": [HumanMessage(f"Python Error:\n{error_msg}")],
                }

        repl = repl_holder["repl"]
        if repl is None:
            repl = PythonREPL()
            # Share globals/locals so helper functions can see prior imports.
            repl.locals = repl.globals

            import json
            import re

            if sandbox_root is not None:
                root = Path(sandbox_root).resolve()

                def resolve_sandbox_path(relative_path: str) -> tuple[str, Path]:
                    relative = Path(relative_path)
                    if relative.parts[:2] == ("project", "outputs"):
                        relative = Path(*relative.parts[2:])
                    elif relative.parts[:1] == ("outputs",):
                        relative = Path(*relative.parts[1:])
                    canonical = relative.as_posix()
                    candidate = (root / relative).resolve()
                    candidate.relative_to(root)
                    return canonical, candidate

                def read_text(relative_path: str) -> str:
                    _, target = resolve_sandbox_path(relative_path)
                    return target.read_text(encoding="utf-8")

                def read_json(relative_path: str):
                    return json.loads(read_text(relative_path))

                def write_json(relative_path: str, payload) -> None:
                    if stop_after_write and successful_writes:
                        message = "Only one artifact write is allowed per benchmark invocation"
                        write_violations.append(message)
                        raise RuntimeError(message)
                    canonical, target = resolve_sandbox_path(relative_path)
                    if artifact_validator is not None:
                        artifact_validator(canonical, payload)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    successful_writes.add(canonical)
                    validated_write_payloads[canonical] = json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    )

                safe_builtins = {
                    name: getattr(builtins, name)
                    for name in (
                        "abs",
                        "all",
                        "any",
                        "bool",
                        "dict",
                        "enumerate",
                        "float",
                        "int",
                        "len",
                        "list",
                        "max",
                        "min",
                        "print",
                        "range",
                        "round",
                        "set",
                        "sorted",
                        "str",
                        "sum",
                        "tuple",
                        "zip",
                    )
                }
                initial_context = {
                    "__builtins__": safe_builtins,
                    "json": json,
                    "re": re,
                    "read_text": read_text,
                    "read_json": read_json,
                    "write_json": write_json,
                }
            else:
                # Pre-import commonly needed packages for the production agent.
                import subprocess
                import anndata as ad
                from anndata import AnnData

                tools_context = {tool.name: tool.func for tool in tools}
                initial_context = {
                    **tools_context,
                    "DATA_DIR": DATA_DIR,
                    "LIBRARY_DIR": LIBRARY_DIR,
                    "OUTPUTS_DIR": active_project_outputs(),
                    "PDF_UPLOADS_DIR": PDF_UPLOADS_DIR,
                    "subprocess": subprocess,
                    "Path": Path,
                    "ad": ad,
                    "AnnData": AnnData,
                    "json": json,
                    "re": re,
                }

            for key, value in initial_context.items():
                repl.globals[key] = value

            repl_holder["repl"] = repl

        output = repl.run(code_block)

        logging.info(f"finished {id} exec_node")

        if stop_after_write and write_violations:
            raise RuntimeError(write_violations[-1])

        output_message = HumanMessage(f"Python Output:\n{output}")
        emit_message(output_message)
        if stop_after_write and successful_writes:
            written = ", ".join(sorted(successful_writes))
            return {
                "messages": [HumanMessage(f"Artifact written and validated: {written}")]
            }
        return {"messages": [output_message]}

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(exec_node_id, exec_node)
    graph.add_edge(START, agent_node_id)
    graph.add_edge(exec_node_id, agent_node_id)

    agent = graph.compile()

    def agent_invocation_tool(prompt: str) -> str:
        """Run the hypothesis agent graph on a prompt and return the final message."""
        logging.info(f"Invoking agent `{id}`")

        skill_prompt_text = ""
        step_ctx = None
        if context_resolver:
            step_ctx = context_resolver("hypothesis")
            if step_ctx and step_ctx.skills:
                from agents.agent_utils import format_skill_prompt

                skill_prompt_text = format_skill_prompt(step_ctx.skills)

        if stop_after_write and sandbox_root is not None and step_ctx is not None:
            expected = list(step_ctx.expected_artifacts)
            if len(expected) == 1:
                relative = Path(expected[0])
                if relative.parts[:2] == ("project", "outputs"):
                    relative = Path(*relative.parts[2:])
                elif relative.parts[:1] == ("outputs",):
                    relative = Path(*relative.parts[1:])
                canonical = relative.as_posix()
                target = (Path(sandbox_root).resolve() / relative).resolve()
                expected_payload = validated_write_payloads.get(canonical)
                if expected_payload is not None and target.is_file():
                    import json

                    current_payload = json.dumps(
                        json.loads(target.read_text(encoding="utf-8")),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if current_payload == expected_payload:
                        result = f"Artifact already written and validated: {canonical}"
                        final_state = {
                            "messages": [HumanMessage(prompt), HumanMessage(result)],
                            "skill_prompt": skill_prompt_text,
                        }
                        with subagent_invocation("Hypothesis Agent") as invocation_id:
                            state_queue.put((id, final_state, invocation_id))
                            stash_completed_subagent(id, final_state, invocation_id)
                        return result

        # REPL persistence across invocations is handled by ``repl_holder``
        # in the closure above — no state-threading needed.
        successful_writes.clear()
        write_violations.clear()
        with subagent_invocation("Hypothesis Agent") as invocation_id:
            from config import RECURSION_LIMIT

            final_state = agent.invoke(
                {"messages": [HumanMessage(prompt)], "skill_prompt": skill_prompt_text},
                config={"recursion_limit": RECURSION_LIMIT},
            )

        if stop_after_write and not successful_writes:
            raise RuntimeError("Hypothesis Agent exited without a validated artifact write")

        state_queue.put((id, final_state, invocation_id))
        # Emit the finished card inline (see coding_agent/model.py): pair with
        # the dispatching ToolMessage.id via the wrapping tool_node so the live
        # trace flips to the completed card immediately, not at run_complete.
        stash_completed_subagent(id, final_state, invocation_id)
        result = final_state["messages"][-1].content

        # Artifact validation is owned by the manager's ``next_step`` / ``retry_step``
        # wrappers (see graph/node_factories.py::run_heuristic_validation). Do not
        # re-run it here.

        return result

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{id}_transfer_tool",
        description=f"Transfer control to Hypothesis Agent: {HypothesisAgentDescription}",
    )
