"""Tool definitions for the manager agent."""
from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_tools import write_tool

ManagerToolsNames: list[str] = [
    "write",
]

ManagerTools: list[StructuredTool] = [
    write_tool,
]
