"""StructuredTool exposed to the manager.

Replace the placeholder name and import path. Tool names must be globally
unique within TissueAgent.
"""

from __future__ import annotations

from langchain.tools import StructuredTool

# from agents.agent_registry.my_agent.runner import run_my_agent


MyAgentTools: list[StructuredTool] = [
    # StructuredTool.from_function(
    #     func=run_my_agent,
    #     name="my_agent_run_tool",
    #     description=(
    #         "TODO: one-sentence description of what the manager will get "
    #         "back when it invokes this tool, including required arguments "
    #         "and the shape of the return value."
    #     ),
    # )
]
