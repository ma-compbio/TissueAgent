"""Tool definitions for the evaluator agent."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from agents.agent_tools import file_read_tools

EvaluatorTools: list[StructuredTool] = list(file_read_tools)
