"""Tool definitions for the reporter agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_read_tools
from agents.reporter_agent.tools_impl.jupyternb_generator_tool import (
    jupyternb_generator_tool,
)

ReporterToolNames = ["glob", "grep", "read", "jupyternb_generator_tool"]

ReporterTools: List[StructuredTool] = [
    *file_read_tools,
    jupyternb_generator_tool,
]
