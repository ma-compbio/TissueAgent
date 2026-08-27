"""Graph node and tool factories for the TissueAgent LangGraph pipeline.

Provides reusable builders for agent nodes, tool nodes, and sub-agent invocation tools, as well as
step-context resolution and artifact validation helpers.
"""

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue
from typing import Any, cast

from langchain_core.tools import StructuredTool
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
from langgraph.managed import RemainingSteps
from langgraph.types import Command

from agents.agent_utils import format_skill_prompt
from config import DATA_DIR
from graph.message_utils import (
    normalize_trailing_assistant,
    sanitize_message,
    standardize_message_format,
)
from graph.ui_events import (
    _get_subagent_context,
    emit_message,
    emit_subagent_state,
    pop_completed_subagent,
    stash_completed_subagent,
    subagent_invocation,
)
from server.plan_store import plan_store, serialize_plan
from server.usage_tracker import usage_tracker


class AgentState(MessagesState):
    """Extended message state with optional skill prompt injection.

    ``system_prompt`` holds the fully-rendered system prompt (skills already
    substituted) that the sub-agent was actually invoked with. It is written by
    ``create_agent_node`` on each turn and read by
    ``message_serializer.serialize_subagent_state`` so the trace UI can show the
    exact prompt behind a dropdown. Last-write-wins is fine: every turn renders
    the same prompt, so the final value is representative.
    """

    skill_prompt: str
    system_prompt: str


class OrchestratorState(MessagesState):
    """Top-level graph state: messages + the orchestration bookkeeping channels.

    These fields MUST be declared as channels here. The main graph is compiled
    with this schema; if a field the nodes write via ``Command(update=...)`` is
    NOT a declared channel, LangGraph silently DROPS the write. That is exactly
    how the replan/retry caps became inert: ``replan_count`` was updated by the
    evaluator but never persisted, so every cycle read ``0``, ``new_count`` was
    always ``1``, ``MAX_REPLANS`` never tripped, and the graph replanned until it
    hit the top-level ``recursion_limit``. Same failure mode applies to each
    retry counter below. Reproduced in isolation before this fix.

    Plain (non-``Annotated``) fields get the default last-write-wins reducer,
    which is correct for these: counters are overwritten with their new value,
    and ``replan_history`` is rewritten with the full updated list by the writer.

    ``remaining_steps`` is LangGraph's own managed value, not one of ours: it is
    recomputed every super-step as ``recursion_limit - step`` and is read-only.
    Declaring it here is what lets the budget guards in :mod:`graph.graph` see
    how much of the graph budget is left and land the run on the reporter
    instead of letting it die with ``GraphRecursionError``.
    """

    replan_count: int
    replan_history: list
    recruiter_retry_count: int
    recruiter_validation_errors: object
    planner_retry_count: int
    planner_retry_phase: str
    planner_validation_errors: object
    remaining_steps: RemainingSteps


# Anthropic silently declines to cache a prefix shorter than the model minimum
# (1024 tokens for the current Sonnet/Opus tiers) — no error, just zeros in
# input_token_details. Marking a short prompt costs a cache-write premium with no
# reads to amortize it, so only mark prompts comfortably past the floor. Chars,
# not tokens, to avoid a tokenizer round-trip on every node build (~4 chars/token,
# so this is ~1150 tokens — clear of the 1024 minimum without being so high that
# it excludes the agents that actually benefit).
_MIN_CACHEABLE_PROMPT_CHARS = 4600


def _build_system_message(prompt_text: str, cacheable: bool) -> SystemMessage:
    """Wrap *prompt_text* in a SystemMessage, marking it cacheable when worthwhile.

    Anthropic prompt caching is a prefix match: the first call writes the prefix at
    ~1.25x input price, every later call with byte-identical bytes reads it at ~0.1x
    and skips prefill. Our agent nodes resend a large static system prompt on every
    turn of a tool loop (the coding agent alone did 24 turns x ~1.4k tokens in the
    Fig2b run), which is exactly the shape this pays off on.

    The *cacheable* gate is about the wire format, not about who benefits: OpenAI
    caches prompts over ~1024 tokens automatically (~50% input discount, no opt-in,
    best-effort eviction) and rejects Anthropic's ``cache_control`` field, so its
    prompts must stay plain strings. Anthropic's caching is opt-in and does nothing
    without the explicit breakpoint below — which is why only that path is marked.
    """
    if not cacheable or len(prompt_text) < _MIN_CACHEABLE_PROMPT_CHARS:
        return SystemMessage(prompt_text)
    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": prompt_text,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )


def _rejects_assistant_prefill(model: BaseChatModel) -> bool:
    """True when *model*'s provider 400s on a message list ending in an assistant turn.

    Anthropic removed assistant-turn prefill in the 4.6 generation, so every Claude
    model in our catalog rejects that shape. OpenAI (direct, and OpenRouter's
    OpenAI-compatible gateway) still accepts it.

    Detected from the bound model instance rather than the global selection so the
    answer stays correct for sub-agents that were built with an explicit override.
    Note this reads the *class*, not the model id: ``ChatAnthropic`` is only ever
    constructed for the ``anthropic`` provider in :func:`models.build_chat_model`,
    while OpenRouter-hosted Claude models go through ``ChatOpenAI`` and genuinely do
    accept the trailing turn.

    ``bind_tools()`` wraps the model in a ``RunnableBinding``, and every agent node
    receives the *bound* model — so the wrapper chain must be unwrapped first or this
    check silently returns False for exactly the models it exists to catch.
    """
    seen = 0
    while (inner := getattr(model, "bound", None)) is not None and seen < 10:
        model = inner
        seen += 1
    return any(base.__name__.startswith("ChatAnthropic") for base in type(model).__mro__)


@dataclass
class BudgetAction:
    """What a node should do when the graph's step budget is running out.

    Returned by a ``budget_guard`` (see :func:`create_agent_node`). Two shapes:

    * ``goto`` set — the node skips the LLM call entirely, emits ``message`` as its
      own turn, and routes straight to ``goto``. Costs one super-step instead of
      the two-or-more a tool-calling turn would.
    * ``directive`` only — the node still calls the LLM, but appends ``directive``
      to the system prompt and strips any tool calls off the response, forcing the
      turn to be terminal. Use this where the LLM's actual words matter (the
      reporter's report) and only its tool loop needs to stop.

    Both fields may be set; ``goto`` wins.
    """

    goto: str | None = None
    message: str = ""
    directive: str = ""


def _strip_tool_calls(response: AIMessage) -> None:
    """Remove tool calls from *response* so the turn terminates.

    Clears every place LangChain keeps them: the normalized ``tool_calls`` list,
    the parse failures in ``invalid_tool_calls``, and the raw provider payload in
    ``additional_kwargs``. Missing any one of them leaves an assistant turn that
    requests tools with no ToolMessage to answer it, which Anthropic and OpenAI
    both reject on the next request.
    """
    response.tool_calls = []
    response.invalid_tool_calls = []
    response.additional_kwargs.pop("tool_calls", None)
    response.additional_kwargs.pop("function_call", None)


def create_agent_node(
    agent_node_id: str,
    agent_model: BaseChatModel,
    prompt: str | Callable[[MessagesState], str],
    tool_node_id: str,
    exit_node: str | Callable[[AIMessage, MessagesState], str] | None = None,
    state_update_fn: Callable[[AIMessage, MessagesState], dict[str, Any] | None] | None = None,
    message_filter_fn: Callable[[list[BaseMessage]], list[BaseMessage]] | None = None,
    budget_guard: Callable[[MessagesState], "BudgetAction | None"] | None = None,
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
        budget_guard: Optional callable that inspects the state's ``remaining_steps`` before the
            LLM call and returns a :class:`BudgetAction` when the graph is about to run out of
            budget. This is what turns a ``GraphRecursionError`` into a finished run: the guard
            short-circuits an agent's tool loop while enough super-steps remain to reach the
            reporter. Returns ``None`` on every normal turn.

    Returns:
        A callable suitable for use as a LangGraph node function.
    """

    if callable(prompt):
        try:
            preview_text = prompt({"messages": []})
        except Exception as e:
            preview_text = f"<callable prompt; could not render at build time: {e}>"
    else:
        preview_text = prompt
    logging.info(f"System prompt for `{agent_node_id}`:\n{preview_text}")

    # Provider traits are fixed for the life of the node (the graph is rebuilt when
    # the model selection changes), so resolve once here rather than per turn.
    is_anthropic = _rejects_assistant_prefill(agent_model)

    def agent_node(state: MessagesState) -> Command:
        action = budget_guard(state) if budget_guard else None
        if action is not None and action.goto:
            # Out of budget: skip the model entirely. One super-step, one message,
            # and control moves on to a node that can still finish the run.
            forced = AIMessage(content=action.message)
            forced.name = agent_node_id
            logging.warning(
                "%s: step budget exhausted (remaining_steps=%s) — routing to %s",
                agent_node_id,
                state.get("remaining_steps"),
                action.goto,
            )
            emit_message(forced)
            return Command(goto=action.goto, update={"messages": [forced]})

        messages = list(map(sanitize_message, state["messages"]))
        if message_filter_fn:
            messages = message_filter_fn(messages)
        if is_anthropic:
            messages = normalize_trailing_assistant(messages)
        prompt_text = prompt(state) if callable(prompt) else prompt
        if action is not None and action.directive:
            prompt_text = f"{prompt_text}\n\n{action.directive}"
        system_prompt = _build_system_message(prompt_text, cacheable=is_anthropic)
        t0 = time.perf_counter()
        response = standardize_message_format(
            cast(AIMessage, agent_model.invoke([system_prompt] + messages))
        )
        elapsed = time.perf_counter() - t0
        response.name = agent_node_id

        if action is not None and action.directive and getattr(response, "tool_calls", []):
            # The directive told it to answer without tools and it called them anyway.
            # Honouring the calls would cost two more super-steps we do not have, so
            # drop them and let this turn be the agent's last.
            logging.warning(
                "%s: dropped %d tool call(s) — no step budget left to run them",
                agent_node_id,
                len(response.tool_calls),
            )
            _strip_tool_calls(response)
            if not response.content:
                response.content = (
                    "Stopping here: the graph step budget ran out before this tool "
                    "call could be run."
                )

        # state_update_fn runs BEFORE emit_message so any mutation of
        # response.content (e.g. evaluator forcing a REPORT verdict when the
        # replan limit is hit) is what the UI sees — otherwise the router and
        # the UI can disagree.
        extra_update: dict[str, Any] = {}
        if state_update_fn:
            maybe_update = state_update_fn(response, state) or {}
            if maybe_update:
                extra_update.update(maybe_update)

        emit_message(response)

        _, subagent_name, step_id = _get_subagent_context()
        usage_tracker.record_llm_call(
            subagent_name or agent_node_id,
            step_id,
            getattr(response, "usage_metadata", None),
            elapsed,
        )

        next_node = tool_node_id if getattr(response, "tool_calls", []) else None
        if not next_node and exit_node is not None:
            next_node = exit_node(response, state) if callable(exit_node) else exit_node

        # Persist the rendered prompt so the trace UI can surface it. Harmless on
        # graphs whose state schema doesn't declare ``system_prompt`` (main-graph
        # nodes): LangGraph drops writes to undeclared channels.
        update_payload = {"messages": [response], "system_prompt": prompt_text}
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
            tool_name = tool_call["name"]
            tool = tools_by_name.get(tool_name)
            if tool is None:
                observation = f"Error: unknown tool '{tool_name}'."
                logging.warning("tool_node: unknown tool %s", tool_name)
            else:
                try:
                    observation = tool.invoke(tool_call["args"])
                except Exception as exc:
                    # Return the error as a ToolMessage so the LLM can recover
                    # from a bad tool call instead of crashing the whole run.
                    logging.exception("tool_node: %s raised", tool_name)
                    observation = (
                        f"Error invoking tool '{tool_name}': {type(exc).__name__}: {exc}"
                    )
            message = ToolMessage(
                content=observation,
                tool_call_id=tool_call["id"],
                id=f"tool-{uuid.uuid4()}",
            )
            message.name = tool_name
            emit_message(message)

            # If the tool internally dispatched a sub-agent (via a transfer
            # tool), pair the just-completed sub-agent state with this
            # ToolMessage.id and push a subagent_state event now so the UI
            # can render the completed card inline. Without this, the card
            # only appears after run_complete — the live trace lingers at
            # the bottom and the ``artifact_validation`` message that
            # follows looks like a replacement.
            completed = pop_completed_subagent()
            if completed is not None:
                agent_name, final_state, invocation_id = completed
                emit_subagent_state(
                    message.id, agent_name, final_state, invocation_id
                )

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
    """Create a resolver that returns the currently-running step's context.

    Manager-judgment model: the manager's ``next_step`` / ``retry_step`` tools set exactly one
    plan step to ``status="running"`` before invoking the sub-agent. The resolver simply finds
    that step, so it transparently handles retries (same step dispatched twice in a row) without
    needing a per-call dispatched-set.

    The ``agent_node_id`` argument is retained for backward compatibility with CustomAgent ctors
    that pass their own agent id; it is not used for matching.
    """
    def resolve(agent_node_id: str) -> StepContext | None:
        from server.plan_store import plan_store

        doc = plan_store.read()
        for step in doc.steps:
            if step.status == "running":
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


def _record_step_outputs(step_id: int, found: list[str]) -> None:
    """Update a plan step's ``actual_outputs`` and emit a ``plan_updated`` UI event.

    Manager-judgment model: this never writes ``step.status`` — completion is decided
    explicitly by the manager via ``next_step`` / ``retry_step``. We only record what
    files were observed so the UI can show progress against expected artifacts.
    """
    doc = plan_store.read()
    for step in doc.steps:
        if step.id == step_id:
            step.actual_outputs = list(found)
            break
    plan_store.write(doc)

    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    emit_message(message)


def _format_progress_line(step_id: int) -> str:
    """Describe how many plan steps have been dispatched and how many remain.

    Reads the live plan cursor, so the number reflects the state *after* the
    just-dispatched step has been marked ``running``. "Remaining after this one"
    counts steps still ``pending``.
    """
    doc = plan_store.read()
    total = len(doc.steps)
    dispatched_idx = next(
        (i for i, s in enumerate(doc.steps) if s.id == step_id),
        None,
    )
    if dispatched_idx is None or total == 0:
        return f"Progress: step {step_id} dispatched"
    remaining_after = total - (dispatched_idx + 1)
    return (
        f"Progress: step {dispatched_idx + 1} of {total} dispatched; "
        f"{remaining_after} remaining after this one"
    )


def _format_validation_summary(
    step_id: int,
    found: list[str],
    missing: list[str],
    progress_line: str,
) -> str:
    """Format a human-readable validation summary for the UI event payload."""
    lines = [f"--- Artifact Validation (Step {step_id}) ---"]
    if found:
        lines.append(f"Found: {', '.join(found)}")
    if missing:
        lines.append(f"Missing: {', '.join(missing)}")
    status = "PASSED" if not missing else "FAILED"
    lines.append(f"Status: {status}")
    lines.append(progress_line)
    return "\n".join(lines)


def _emit_artifact_validation(
    step_id: int,
    found: list[str],
    missing: list[str],
    summary: str,
) -> None:
    """Push a ``artifact_validation`` UI event with the structured payload.

    The summary text is the same one returned to the manager via the tool channel;
    the ``validation_payload`` carries the parsed fields so future UI components
    (e.g. a per-step badge in PlanPanel) can render without re-parsing the string.
    """
    verdict = "PASSED" if not missing else "FAILED"
    message = AIMessage(
        content=summary,
        additional_kwargs={
            "validation_payload": {
                "step_id": step_id,
                "found": list(found),
                "missing": list(missing),
                "verdict": verdict,
            },
        },
        name="artifact_validation",
    )
    emit_message(message)


def run_heuristic_validation(
    step_id: int,
    expected_artifacts: list[str],
) -> tuple[list[str], list[str], str]:
    """Validate expected artifacts, record outputs, and emit a UI event.

    Wraps the four steps the manager's ``next_step``/``retry_step`` need after invoking
    a sub-agent:

    1. Glob/exact-match each expected artifact under ``DATA_DIR``.
    2. Record what was found in ``step.actual_outputs`` (no status write).
    3. Format the validation summary (Found/Missing/Status/Progress).
    4. Emit an ``artifact_validation`` UI event for display.

    Returns ``(found, missing, summary)``. The summary is the same text the UI event
    carries and is appended to the manager tool's return value so the manager can
    factor the verdict into its next decision.
    """
    found, missing = _validate_step_artifacts(expected_artifacts)
    _record_step_outputs(step_id, found)
    progress_line = _format_progress_line(step_id)
    summary = _format_validation_summary(step_id, found, missing, progress_line)
    _emit_artifact_validation(step_id, found, missing, summary)
    return found, missing, summary


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

    Under the manager-judgment model, validation is NOT performed here. The manager's
    ``next_step`` / ``retry_step`` wrappers call :func:`run_heuristic_validation` themselves
    after invoking this tool, so the validation result reaches the UI but never enters the
    tool's return value to the manager.

    Args:
        agent_node_id: Node ID of the sub-agent (used in the tool name).
        agent_name: Human-readable agent name shown in UI badges.
        agent: The compiled sub-agent graph to invoke.
        state_queue: Queue where ``(agent_name, final_state)`` tuples are placed after each
            invocation.
        context_resolver: Callable that returns a :class:`StepContext` for the current step
            (skills + expected artifacts), or ``None`` when no matching step is found. Used to
            build the ``skill_prompt`` injection for the sub-agent.

    Returns:
        A :class:`~langchain.tools.StructuredTool` named ``"{agent_node_id}_transfer_tool"``.
    """

    def _resolve_step_context() -> tuple[str, StepContext | None]:
        """Resolve context for the current step: skill prompt + step metadata.

        Also snapshots exactly this step's folder-skill assets into the workspace
        (clearing any prior step's), so a step never sees a later step's skill
        files on disk. Done before ``format_skill_prompt`` so the assets-root
        note it emits resolves against freshly-materialized directories.
        """
        if not context_resolver:
            return "", None
        ctx = context_resolver(agent_node_id)
        if ctx is None:
            return "", None
        try:
            from agents.skills_workspace import sync_workspace_skills

            sync_workspace_skills(ctx.skills)
        except Exception as e:
            logging.warning("per-step skill materialization failed: %s", e)
        if not ctx.skills:
            return "", ctx
        return format_skill_prompt(ctx.skills), ctx

    def _agent_invocation_tool(prompt: str) -> str:
        """Invoke the sub-agent with a text prompt and return its response.

        Pure invocation: pushes state to the UI queue and returns the sub-agent's last
        message content. Artifact validation is no longer appended here — the manager's
        ``next_step`` / ``retry_step`` orchestrate validation via
        :func:`run_heuristic_validation` and route it through the UI channel only.
        """
        logging.info(f"Invoking agent `{agent_node_id}`")
        message = HumanMessage(prompt)
        skill_prompt_text, step_ctx = _resolve_step_context()
        with subagent_invocation(
            agent_name,
            step_id=step_ctx.step_id if step_ctx else None,
        ) as invocation_id:
            final_state = agent.invoke({"messages": [message], "skill_prompt": skill_prompt_text})
        # Ride the step's assigned skills along with the returned state so the
        # UI trace can show which skills were loaded for this sub-agent. Keyed
        # into the dict (not the state tuple) so it survives save/rehydrate via
        # the ``{**state, ...}`` spreads in server.utils, and reaches
        # ``serialize_subagent_state`` unchanged.
        if isinstance(final_state, dict):
            final_state["step_skills"] = list(step_ctx.skills) if step_ctx else []
        state_queue.put((agent_name, final_state, invocation_id))
        # Hand off to the wrapping tool_node so it can pair the final state
        # with the ToolMessage.id of the manager tool that called us
        # (``next_step`` / ``retry_step``) and emit a subagent_state event
        # mid-run.
        stash_completed_subagent(agent_name, final_state, invocation_id)
        logging.info(f"Finished invoking agent `{agent_node_id}`")
        return final_state["messages"][-1].content

    agent_invocation_tool = _agent_invocation_tool

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{agent_node_id}_transfer_tool",
        description=f"Transfer control to {agent_name}",
    )
