"""Tool definitions for the manager agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import write_tool

ManagerToolNames: List[str] = [
    "write",
]

ManagerTool: List[StructuredTool] = [
    write_tool,
]
