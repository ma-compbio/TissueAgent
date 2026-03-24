"""Tool definitions for the manager agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from agents.manager_agent.tools_impl.text_artifact_writer_tool import (
    text_artifact_writer_tool,
)

ManagerToolNames: List[str] = [
    "file_retriever_tool",
    "text_artifact_writer_tool",
]

ManagerTool: List[StructuredTool] = [
    file_retriever_tool,
    text_artifact_writer_tool,
]
