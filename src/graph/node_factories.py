"""Graph node and tool factories for the TissueAgent LangGraph pipeline.

Provides reusable builders for agent nodes, tool nodes, and sub-agent invocation tools, as well as
step-context resolution and artifact validation helpers.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue
from typing import Any, cast

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agents.agent_utils import format_skill_prompt
from config import DATA_DIR
from graph.message_utils import sanitize_message, standardize_message_format
from graph.ui_events import emit_message, subagent_invocation
from server.plan_store import plan_store, serialize_plan


class AgentState(MessagesState):
    """Extended message state with optional skill prompt injection."""

    skill_prompt: str


def create_agent_node(
    agent_node_id: str,
    agent_model: BaseChatModel,
    prompt: str | Callable[[MessagesState], str],
    tool_node_id: str,
    exit_node: str | Callable[[AIMessage, MessagesState], str] | None = None,
    state_update_fn: Callable[[AIMessage, MessagesState], dict[str, Any] | None] | None = None,
    message_filter_fn: Callable[[list[BaseMessage]], list[BaseMessage]] | None = None,
) -> Callable[[MessagesState], Command]:
    """Build a LangGraph agent node that invokes an LLM and routes the result.

    The returned callable prepends a system prompt, invokes *agent_model*, normalises the response,
    logs it, and returns a :class:`Command` that either routes to the tool node (when tool calls are
    present) or to the configured exit node.

    Args:
        agent_node_id: Unique node identifier; also set as the message's ``name`` attribute for UI
            display.
        agent_model: Bound chat model (with tools already attached).
        prompt: System prompt injected before the conversation messages. May be a static string or
            a callable that receives the current state and returns the prompt string.
        tool_node_id: Node to route to when the response contains tool calls.
        exit_node: Node to route to when no tool calls are present. Either a static node ID string
            or a callable ``(response, state) -> str`` for conditional routing.
        state_update_fn: Optional callable that receives ``(response, state)`` and returns a dict of
            extra state updates to merge into the command payload.
        message_filter_fn: Optional callable that projects the full message history down to the
            subset relevant to this agent. Applied before the LLM call without mutating graph state.

    Returns:
        A callable suitable for use as a LangGraph node function.
    """

    def agent_node(state: MessagesState) -> Command:
        messages = list(map(sanitize_message, state["messages"]))
        if message_filter_fn:
            messages = message_filter_fn(messages)
        prompt_text = prompt(state) if callable(prompt) else prompt
        system_prompt = SystemMessage(prompt_text)
        logging.info(f"System prompt for `{agent_node_id}`:\n{prompt_text}")
        response = standardize_message_format(
            cast(AIMessage, agent_model.invoke([system_prompt] + messages))
        )
        response.name = agent_node_id
        emit_message(response)

        extra_update: dict[str, Any] = {}
        if state_update_fn:
            maybe_update = state_update_fn(response, state) or {}
            if maybe_update:
                extra_update.update(maybe_update)

        next_node = tool_node_id if getattr(response, "tool_calls", []) else None
        if not next_node and exit_node is not None:
            next_node = exit_node(response, state) if callable(exit_node) else exit_node

        update_payload = {"messages": [response]}
        if extra_update:
            update_payload.update(extra_update)
        if next_node is not None:
            return Command(goto=next_node, update=update_payload)
        return Command(update=update_payload)

    return agent_node


def create_tool_node(
    tools: list[StructuredTool],
) -> Callable[[MessagesState], MessagesState]:
    """Build a LangGraph tool-execution node from a list of tools.

    The returned callable reads the last AI message's ``tool_calls``, invokes each tool by name,
    wraps the results as :class:`~langchain_core.messages.ToolMessage` objects, and logs them.

    Args:
        tools: The tool instances available for invocation.  Each tool's ``name`` must be unique
            within the list.

    Returns:
        A callable suitable for use as a LangGraph node function.
    """
    tools_by_name = {tool.name: tool for tool in tools}

    def tool_node(state: MessagesState) -> MessagesState:
        result = []
        last_message = cast(AIMessage, state["messages"][-1])
        for tool_call in last_message.tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            message = ToolMessage(content=observation, tool_call_id=tool_call["id"])
            message.name = tool_call["name"]
            emit_message(message)
            result.append(message)
        return {"messages": result}

    return tool_node


@dataclass
class StepContext:
    """Pre-invocation context for a plan step, resolved by the step context resolver."""

    step_id: int
    skills: list[str]
    expected_artifacts: list[str]


type ContextResolver = Callable[[str], StepContext | None]


def create_step_context_resolver(assign_agent_node_id: Callable[[str], str]) -> ContextResolver:
    """Create a resolver that maps agent invocations to plan step context.

    Returns a callable: resolve(agent_node_id) -> StepContext or None. Uses a shared set to track
    dispatched steps across all transfer tools, ensuring each step's context is only returned once
    (for sequential execution).

    Args:
        assign_agent_node_id: Function that maps agent names to their node IDs.
    """
    dispatched: set[int] = set()

    def resolve(agent_node_id: str) -> StepContext | None:
        from server.plan_store import plan_store

        doc = plan_store.read()
        for step in doc.steps:
            if step.id in dispatched:
                continue
            if step.assigned_agent and assign_agent_node_id(step.assigned_agent) == agent_node_id:
                dispatched.add(step.id)
                return StepContext(
                    step_id=step.id,
                    skills=list(step.skills),
                    expected_artifacts=list(step.expected_artifacts),
                )
        return None

    return resolve


def _validate_step_artifacts(expected_artifacts: list[str]) -> tuple[list[str], list[str]]:
    """Check which expected artifacts exist in the workspace directory.

    Returns (found, missing) where each is a list of relative path strings. Paths are matched
    exactly first; if not found, they are tried as glob patterns to allow for minor naming
    variations.
    """
    found: list[str] = []
    missing: list[str] = []
    for artifact_path in expected_artifacts:
        full_path = DATA_DIR / artifact_path
        if full_path.exists():
            found.append(artifact_path)
        else:
            matches = sorted(DATA_DIR.glob(artifact_path))
            if matches:
                found.extend(str(m.relative_to(DATA_DIR)) for m in matches)
            else:
                missing.append(artifact_path)
    return found, missing


def _update_step_status(
    step_id: int,
    found: list[str],
    missing: list[str],
) -> None:
    """Update a plan step's status and actual_outputs after artifact validation.

    Emits a ``plan_updated`` UI event so the frontend reflects the change.
    """
    doc = plan_store.read()
    for step in doc.steps:
        if step.id == step_id:
            step.actual_outputs = list(found)
            step.status = "done" if not missing else "failed"
            break

    plan_store.write(doc)

    # Emit plan_updated event for the UI.
    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    emit_message(message)


def _format_validation_summary(
    step_id: int,
    found: list[str],
    missing: list[str],
) -> str:
    """Format a human-readable validation summary appended to the tool result."""
    lines = [f"\n\n--- Artifact Validation (Step {step_id}) ---"]
    if found:
        lines.append(f"Found: {', '.join(found)}")
    if missing:
        lines.append(f"Missing: {', '.join(missing)}")
    status = "PASSED" if not missing else "FAILED"
    lines.append(f"Status: {status}")
    return "\n".join(lines)


def create_agent_invocation_tool(
    agent_node_id: str,
    agent_name: str,
    agent: CompiledStateGraph,
    state_queue: Queue,
    context_resolver: ContextResolver | None = None,
) -> StructuredTool:
    """Create a LangChain tool that delegates a prompt to a compiled sub-agent.

    The returned :class:`~langchain.tools.StructuredTool` accepts a text prompt, invokes the
    sub-agent graph, pushes the final state onto *state_queue* for UI rendering, and returns the
    last message's content.

    After invocation, if a *context_resolver* is provided, the tool automatically validates expected
    artifacts and updates the plan step status in the plan store — removing the need for the manager
    LLM to perform artifact checking.

    Args:
        agent_node_id: Node ID of the sub-agent (used in the tool name).
        agent_name: Human-readable agent name shown in UI badges.
        agent: The compiled sub-agent graph to invoke.
        state_queue: Queue where ``(agent_name, final_state)`` tuples are placed after each
            invocation.
        context_resolver: Callable that returns a :class:`StepContext` for the current step (skills
            + expected artifacts), or ``None`` when no matching step is found.

    Returns:
        A :class:`~langchain.tools.StructuredTool` named ``"{agent_node_id}_transfer_tool"``.
    """

    def _resolve_step_context() -> tuple[str, StepContext | None]:
        """Resolve context for the current step: skill prompt + step metadata."""
        if not context_resolver:
            return "", None
        ctx = context_resolver(agent_node_id)
        if ctx is None:
            return "", None
        if not ctx.skills:
            return "", ctx
        return format_skill_prompt(ctx.skills), ctx

    def _post_invocation_validate(
        result: str,
        step_ctx: StepContext | None,
    ) -> str:
        """Validate artifacts and update the plan store.

        Returns result with summary appended.
        """
        if step_ctx is None or not step_ctx.expected_artifacts:
            return result
        found, missing = _validate_step_artifacts(step_ctx.expected_artifacts)
        _update_step_status(step_ctx.step_id, found, missing)
        summary = _format_validation_summary(step_ctx.step_id, found, missing)
        logging.info(summary)
        return result + summary

    def _agent_invocation_tool(prompt: str) -> str:
        """Invoke the sub-agent with a text prompt and return its response."""
        logging.info(f"Invoking agent `{agent_node_id}`")
        message = HumanMessage(prompt)
        skill_prompt_text, step_ctx = _resolve_step_context()
        with subagent_invocation(agent_name) as invocation_id:
            final_state = agent.invoke({"messages": [message], "skill_prompt": skill_prompt_text})
        state_queue.put((agent_name, final_state, invocation_id))
        logging.info(f"Finished invoking agent `{agent_node_id}`")
        result = final_state["messages"][-1].content
        return _post_invocation_validate(result, step_ctx)

    agent_invocation_tool = _agent_invocation_tool

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{agent_node_id}_transfer_tool",
        description=f"Transfer control to {agent_name}",
    )
