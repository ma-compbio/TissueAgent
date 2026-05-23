"""Tool definitions for the planner agent."""
from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from agents.planner_agent.tools_impl.plan_registry_tool import plan_registry_tool
from agents.planner_agent.tools_impl.template_selector_tool import (
    template_selector_tool,
)
from agents.planner_agent.tools_impl.write_plan_tool import write_plan_tool


PlannerToolNames: List[str] = [
    "file_retriever_tool",
    "plan_registry_tool",
    "template_selector_tool",
    "write_plan",
]

PlannerTools: List[StructuredTool] = [
    file_retriever_tool,
    plan_registry_tool,
    template_selector_tool,
    write_plan_tool,
]
