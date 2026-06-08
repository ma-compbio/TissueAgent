"""Tools available to the Recruiter agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_tools import file_read_tools
from agents.recruiter_agent.tools_impl.read_skill_tool import read_skill_tool

RecruiterTools: list[StructuredTool] = [
    *file_read_tools,
    read_skill_tool,
]
