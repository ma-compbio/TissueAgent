from dataclasses import dataclass
from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.data_analysis_agent.prompt import DataAnalysisPrompt, DataAnalysisDescription
from agents.agent_registry.data_analysis_agent.tools import create_data_analysis_tools
from agents.agent_registry.data_processing_agent.prompt import DataProcessingPrompt, DataProcessingDescription
from agents.agent_registry.data_processing_agent.tools import DataProcessingTools
from agents.agent_registry.searcher_agent.prompt import SearcherPrompt, SearcherDescription
from agents.agent_registry.searcher_agent.tools import create_searcher_tools
from agents.agent_registry.single_cell_agent.prompt import SingleCellPrompt, SingleCellDescription
from agents.agent_registry.single_cell_agent.tools import create_single_cell_tools
from agents.reporter_agent.prompt import ReporterPrompt, ReporterDescription
from agents.reporter_agent.tools import create_reporter_tools
from api_keys import APIKeys

@dataclass
class Agent:
    id: str
    name: str
    description: str
    prompt: str
    tools: List[StructuredTool]

def create_agent_defns(api_keys: APIKeys) -> List[Agent]:
    return [
        Agent(
            id="data_processing",
            name="Data Processing Agent",
            description=DataProcessingDescription,
            prompt=DataProcessingPrompt,
            tools=DataProcessingTools,
        ),
        Agent(
            id="data_analysis",
            name="Data Analysis Agent",
            description=DataAnalysisDescription,
            prompt=DataAnalysisPrompt,
            tools=create_data_analysis_tools(api_keys)
        ),
        Agent(
            id="searcher",
            name="Searcher Agent",
            description=SearcherDescription,
            prompt=SearcherPrompt,
            tools=create_searcher_tools(api_keys),
        ),
        Agent(
            id="single_cell",
            name="Single Cell Agent",
            description=SingleCellDescription,
            prompt=SingleCellPrompt,
            tools=create_single_cell_tools(api_keys),
        ),
        Agent(
            id="reporter",
            name="Report Agent",
            description=ReporterDescription,
            prompt=ReporterPrompt,
            tools=create_reporter_tools(api_keys),
        )
    ]
