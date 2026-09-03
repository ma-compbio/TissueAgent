"""The optimizer's agentic loop: a plain LangChain tool-calling loop.

Deliberately not a LangGraph graph — the control flow is a straight loop with
a hard iteration cap, and the whole feature must stay decoupled from the main
orchestrator so it can never interfere with a run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from optimizer import guardrails
from optimizer.session_digest import SessionDigest, load_session_digest, render_digest
from optimizer.tools import EditRecord, OptimizerContext, build_tools

_CONTEXT_DOC = guardrails.REPO_ROOT / "docs" / "OPTIMIZER_CONTEXT.md"

_FALLBACK_CONTEXT = """You are the knowledge optimizer for TissueAgent, an autonomous
spatial-transcriptomics analysis agent (planner → recruiter → manager → evaluator →
reporter over a step plan; executors run code in a Jupyter sandbox; state flows through
project/outputs/ artifacts). You analyze past run traces and make small, safe edits to
the knowledge layer only: plan templates (knowledge/plans/*.md) and skill markdown
(knowledge/skills/**/*.md, never scripts/). Make the smallest edits that remove failure
modes or trim token waste; never bloat; end with finish(report)."""


@dataclass
class OptimizerResult:
    digests: list[SessionDigest]
    edits: list[EditRecord] = field(default_factory=list)
    final_report: str = ""
    finished: bool = False
    iterations: int = 0
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0})


def load_context_prompt() -> str:
    if _CONTEXT_DOC.is_file():
        return _CONTEXT_DOC.read_text()
    logging.warning("docs/OPTIMIZER_CONTEXT.md missing; using embedded fallback prompt.")
    return _FALLBACK_CONTEXT


def run_optimizer(
    sessions: list[Path],
    focus: str,
    *,
    propose_only: bool = False,
    max_iterations: int = 40,
    model_role: str = "orchestration",
    model=None,
) -> OptimizerResult:
    """Run one optimization round over *sessions*.

    ``model`` is injectable for tests; by default the configured model for
    *model_role* is built via the repo's registry, wrapped with header-aware
    rate-limit retries, and bound to the optimizer tools.
    """
    digests = [load_session_digest(Path(s)) for s in sessions]
    ctx = OptimizerContext(digests=digests, propose_only=propose_only)
    tools = build_tools(ctx)
    tools_by_name = {t.name: t for t in tools}

    if model is None:
        from models import model_ctor_for_role
        from server.rate_limit import with_header_retry

        model = with_header_retry(model_ctor_for_role(model_role)().bind_tools(tools))
    else:
        model = model.bind_tools(tools)

    system = SystemMessage(
        load_context_prompt()
        + f"\n\n## This round\n"
        f"- Edit budget: {guardrails.MAX_EDITS_PER_ROUND} edits, "
        f"{guardrails.MAX_EDIT_CHARS} chars per edit.\n"
        f"- Mode: {'PROPOSE-ONLY (edits are recorded as diffs, then reverted)' if propose_only else 'apply'}.\n"
        f"- You have {max_iterations} tool-loop iterations. Investigate before editing; "
        "call finish(report) when done."
    )
    opening = HumanMessage(
        "## Focus from the user\n"
        + focus.strip()
        + "\n\n## Session digests\n"
        + "\n\n".join(f"[{i}] {render_digest(d)}" for i, d in enumerate(digests, 1))
    )
    messages: list = [system, opening]

    result = OptimizerResult(digests=digests)
    try:
        for _ in range(max_iterations):
            result.iterations += 1
            ai: AIMessage = model.invoke(messages)
            messages.append(ai)
            _accumulate_usage(result.usage, ai)
            if not ai.tool_calls:
                # Model stopped talking instead of calling finish(); keep its text.
                result.final_report = result.final_report or _text_of(ai)
                break
            for call in ai.tool_calls:
                tool = tools_by_name.get(call["name"])
                if tool is None:
                    output = f"error: unknown tool '{call['name']}'"
                else:
                    try:
                        output = tool.invoke(call["args"])
                    except Exception as e:  # tool bugs must not kill the round
                        logging.exception("optimizer tool %s failed", call["name"])
                        output = f"error: {type(e).__name__}: {e}"
                messages.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
            if ctx.finished:
                break
            remaining = max_iterations - result.iterations
            if remaining == 2:
                messages.append(
                    HumanMessage(
                        "Iteration budget nearly exhausted (2 left). Stop investigating; "
                        "make any final edit now and call finish(report) on your next turn."
                    )
                )
    finally:
        if propose_only and ctx.edits:
            ctx.revert_all_edits()

    result.edits = ctx.edits
    result.finished = ctx.finished
    if ctx.final_report:
        result.final_report = ctx.final_report
    return result


def _accumulate_usage(usage: dict, ai: AIMessage) -> None:
    meta = getattr(ai, "usage_metadata", None) or {}
    usage["input_tokens"] += meta.get("input_tokens", 0)
    usage["output_tokens"] += meta.get("output_tokens", 0)
    usage["llm_calls"] += 1


def _text_of(ai: AIMessage) -> str:
    content = ai.content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content or "")
