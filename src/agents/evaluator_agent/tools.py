"""Tool definitions for the evaluator agent."""
from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_utils import file_read_tools


# Exposed tool names (helps UI render / logs)
EvaluatorToolNames: list[str] = ["glob", "grep", "read"]

EvaluatorTools: list[StructuredTool] = list(file_read_tools)
