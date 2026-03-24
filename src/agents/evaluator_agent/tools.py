"""Tool definitions for the evaluator agent."""
from __future__ import annotations

from typing import List

from agents.agent_utils import file_retriever_tool
from api_keys import APIKeys


# Exposed tool names (helps UI render / logs)
EvaluatorToolNames: List[str] = [
    "file_retriever_tool",
]


def create_evaluator_tools(api_keys: APIKeys):
    """Return the list of tools available to the Planner.

    (api_keys kept for signature symmetry; tools here are local and don't need keys.)
    """
    return [
        file_retriever_tool,
    ]
