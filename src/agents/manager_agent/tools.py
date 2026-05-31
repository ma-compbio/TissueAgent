"""Tool definitions for the manager agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_tools

ManagerToolNames: List[str] = [
    "glob",
    "grep",
    "read",
    "write",
]

ManagerTool: List[StructuredTool] = [
    *file_tools,
]
