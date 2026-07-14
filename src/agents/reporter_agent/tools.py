"""Tool definitions for the reporter agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_tools import file_read_write_tools
from agents.reporter_agent.tools_impl.jupyternb_generator_tool import (
    jupyternb_generator_tool,
)

ReporterToolNames = ["glob", "grep", "read", "write", "jupyternb_generator_tool"]

ReporterTools: list[StructuredTool] = [
    *file_read_write_tools,
    jupyternb_generator_tool,
]
