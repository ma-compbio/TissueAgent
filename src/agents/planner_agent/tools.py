"""Tool definitions for the planner agent."""
from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_utils import file_read_tools
from agents.planner_agent.tools_impl.read_template_tool import read_template_tool


PlannerToolNames: list[str] = [
    "glob",
    "grep",
    "read",
    "read_template",
]

PlannerTools: list[StructuredTool] = [
    *file_read_tools,
    read_template_tool,
]
