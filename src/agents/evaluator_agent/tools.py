"""Tool definitions for the evaluator agent."""
from __future__ import annotations

from typing import List

from agents.agent_utils import file_read_tools
from api_keys import APIKeys


# Exposed tool names (helps UI render / logs)
EvaluatorToolNames: List[str] = ["glob", "grep", "read"]


def create_evaluator_tools(api_keys: APIKeys):
    """Return the list of tools available to the Planner.

    (api_keys kept for signature symmetry; tools here are local and don't need keys.)
    """
    return list(file_read_tools)
