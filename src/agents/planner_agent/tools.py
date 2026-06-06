"""Tool definitions for the planner agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_read_tools
from agents.planner_agent.tools_impl.read_template_tool import read_template_tool


PlannerToolNames: List[str] = [
    "glob",
    "grep",
    "read",
    "read_template",
]

PlannerTools: List[StructuredTool] = [
    *file_read_tools,
    read_template_tool,
]
