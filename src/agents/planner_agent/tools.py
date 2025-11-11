from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from agents.planner_agent.tools_impl.plan_registry_tool import (
    plan_registry_tool,
)


PlannerToolNames: List[str] = [
    "file_retriever_tool",
    "plan_registry_tool",
]

PlannerTools: List[StructuredTool] = [
    file_retriever_tool,
    plan_registry_tool,
]