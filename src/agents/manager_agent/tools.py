from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool

ManagerToolNames: List[str] = [
    "file_retriever_tool"
]

ManagerTool: List[StructuredTool] = [
    file_retriever_tool,
]