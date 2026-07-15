"""StructuredTool exposed to the manager for the TxAgent external agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.txagent_agent.runner import run_txagent_question


TxAgentTools: list[StructuredTool] = [
    StructuredTool.from_function(
        func=run_txagent_question,
        name="txagent_answer_question_tool",
        description=(
            "Answers a therapeutic / precision-medicine question (drug "
            "interactions, contraindications, dose adjustment for organ "
            "impairment) using TxAgent's multi-step tool-use reasoning over "
            "the ToolUniverse. "
            "Arguments: question (str, required), optional temperature (float, "
            "default 0.3), max_new_tokens (int, 1024), max_token (int, 90240), "
            "max_round (int, 20), multiagent (bool, False). "
            "Returns status (ok / no_answer / requires_gpu / unavailable / "
            "error). On 'ok': answer (recommendation) + reasoning_trace. "
            "NOTE: requires a CUDA GPU + model weights; without a GPU it "
            "returns 'requires_gpu' and does NOT fabricate an answer."
        ),
    )
]
