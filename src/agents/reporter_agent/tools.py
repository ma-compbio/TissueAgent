from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from agents.reporter_agent.tools_impl.jupyternb_generator_tool import jupyternb_generator_tool

ReporterToolNames = ["file_retriever_tool", "jupyternb_generator_tool"]

ReporterTools: List[StructuredTool] =  [
    jupyternb_generator_tool,
    file_retriever_tool,
]
