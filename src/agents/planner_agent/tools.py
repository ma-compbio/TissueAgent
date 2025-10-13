from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool


PlannerToolNames: List[str] = [
    "file_retriever_tool",
]

PlannerTools: List[StructuredTool] = [
    file_retriever_tool,
]