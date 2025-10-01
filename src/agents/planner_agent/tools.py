# from langchain.tools import StructuredTool

# from agents.agent_utils import file_retriever_tool
# # from agents.planner_agent.tools_impl.jupyternb_generator_tool import create_generate_jupyternb
# from api_keys import APIKeys

# ### computed at load time for render_conversation_history in app_utils
# PlannerToolNames = ["file_retriever_tool"]

# def create_planner_tools(api_keys: APIKeys):
#     return [
#         file_retriever_tool,
#     ]


from __future__ import annotations

from langchain.tools import StructuredTool
from typing import List

from agents.agent_utils import file_retriever_tool
from api_keys import APIKeys

# from .tools_impl.plan_registry_tool import plan_registry_tool
# from .tools_impl.template_selector_tool import template_selector_tool


# Exposed tool names (helps UI render / logs)
PlannerToolNames: List[str] = [
    "file_retriever_tool",
    # "plan_registry_tool",
    # "template_selector_tool",
]

def create_planner_tools(api_keys: APIKeys):
    """
    Return the list of tools available to the Planner.
    (api_keys kept for signature symmetry; tools here are local and don't need keys.)
    """
    return [
        file_retriever_tool,
        # plan_registry_tool,
        # template_selector_tool,
    ]
