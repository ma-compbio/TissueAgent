"""Tool definitions for the planner agent."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from agents.agent_tools import file_read_tools
from agents.planner_agent.tools_impl.read_template_tool import read_template_tool

PlannerTools: list[StructuredTool] = [
    *file_read_tools,
    read_template_tool,
]
