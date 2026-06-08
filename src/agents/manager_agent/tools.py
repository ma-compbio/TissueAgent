"""Tool definitions for the manager agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_tools import write_tool

ManagerTools: list[StructuredTool] = [
    write_tool,
]
