from dataclasses import dataclass
from functools import partial
from typing import Callable, List, Union

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from agents.agent_utils import file_retriever_tool
from agents.planner_agent.prompt import PlannerPrompt, PlannerDescription
from agents.recruiter_agent.prompt import RecruiterPrompt, RecruiterDescription
from agents.manager_agent.prompt import ManagerPrompt, ManagerDescription
from agents.evaluator_agent.prompt import EvaluatorPrompt, EvaluatorDescription
from agents.reporter_agent.prompt import ReporterPrompt, ReporterDescription
from agents.reporter_agent.tools import ReporterTools
from api_keys import APIKeys

@dataclass
class ReActAgent:
    id: str
    name: str
    description: str
    prompt: Union[str, Callable[..., str]]
    tools: List[StructuredTool]
    model_ctor: Callable[..., BaseChatModel]

@dataclass
class CustomAgent:
    id: str
    name: str
    description: str
    ctor: Callable[..., StructuredTool]


DefaultModelCtor = partial(ChatOpenAI, model="gpt-5")

PlannerAgent = ReActAgent(
    id          = "planner",
    name        = "Planner Agent",
    description = PlannerDescription,
    prompt      = PlannerPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

RecruiterAgent = ReActAgent(
    id          = "recruiter",
    name        = "Recruiter Agent",
    description = RecruiterDescription,
    prompt      = RecruiterPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

ManagerAgent = ReActAgent(
    id          = "manager",
    name        = "Manager Agent",
    description = ManagerDescription,
    prompt      = ManagerPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

EvaluatorAgent = ReActAgent(
    id          = "evaluator",
    name        = "Evaluator Agent",
    description = EvaluatorDescription,
    prompt      = EvaluatorPrompt,
    tools       = [],
    model_ctor  = DefaultModelCtor,
)

ReporterAgent = ReActAgent(
    id          = "reporter",
    name        = "Reporter Agent",
    description = ReporterDescription,
    prompt      = ReporterPrompt,
    tools       = ReporterTools,
    model_ctor  = DefaultModelCtor,
)



import agents.agent_registry.coding_agent.model as CodingAgent
import agents.agent_registry.data_processing_agent.prompt as DataProcessingAgentPrompt
import agents.agent_registry.data_processing_agent.tools as DataProcessingAgentTools
import agents.agent_registry.searcher_agent.prompt as SearcherAgentPrompt
import agents.agent_registry.searcher_agent.tools as SearcherAgentTools
import agents.agent_registry.single_cell_agent.prompt as SingleCellAgentPrompt
import agents.agent_registry.single_cell_agent.tools as SingleCellAgentTools

def create_agent_defns(api_keys: APIKeys) -> List[Union[ReActAgent, CustomAgent]]:
    return [
        CustomAgent(
            id          = "coding_agent",
            name        = "Coding Agent",
            description = CodingAgent.CodingAgentDescription,
            ctor        = CodingAgent.create_coding_agent,
        ),
        ReActAgent(
            id          = "data_processing",
            name        = "Data Processing Agent",
            description = DataProcessingAgentPrompt.DataProcessingDescription,
            prompt      = DataProcessingAgentPrompt.DataProcessingPrompt,
            tools       = DataProcessingAgentTools.DataProcessingTools,
            model_ctor  = DefaultModelCtor,
        ),
        ReActAgent(
            id          = "searcher",
            name        = "Searcher Agent",
            description = SearcherAgentPrompt.SearcherDescription,
            prompt      = SearcherAgentPrompt.SearcherPrompt,
            tools       = SearcherAgentTools.create_searcher_tools(api_keys=api_keys),
            model_ctor  = DefaultModelCtor,
        ),
        ReActAgent(
            id          = "single_cell",
            name        = "Single Cell Agent",
            description = SingleCellAgentPrompt.SingleCellDescription,
            prompt      = SingleCellAgentPrompt.SingleCellPrompt,
            tools       = SingleCellAgentTools.SingleCellTools,
            model_ctor  = DefaultModelCtor,
        ),
    ]

# from dataclasses import dataclass
# from typing import List

# from langchain.tools import StructuredTool

# from agents.agent_registry.data_analysis_agent.prompt import DataAnalysisPrompt, DataAnalysisDescription
# from agents.agent_registry.data_analysis_agent.tools import create_data_analysis_tools
# from agents.agent_registry.data_processing_agent.prompt import DataProcessingPrompt, DataProcessingDescription
# from agents.agent_registry.data_processing_agent.tools import DataProcessingTools
# from agents.agent_registry.searcher_agent.prompt import SearcherPrompt, SearcherDescription
# from agents.agent_registry.searcher_agent.tools import create_searcher_tools
# from agents.agent_registry.single_cell_agent.prompt import SingleCellPrompt, SingleCellDescription
# from agents.agent_registry.single_cell_agent.tools import create_single_cell_tools
# # from agents.reporter_agent.prompt import ReporterPrompt, ReporterDescription
# # from agents.reporter_agent.tools import create_reporter_tools
# from api_keys import APIKeys

# @dataclass
# class Agent:
#     id: str
#     name: str
#     description: str
#     prompt: str
#     tools: List[StructuredTool]

# def create_agent_defns(api_keys: APIKeys) -> List[Agent]:
#     return [
#         Agent(
#             id="data_processing",
#             name="Data Processing Agent",
#             description=DataProcessingDescription,
#             prompt=DataProcessingPrompt,
#             tools=DataProcessingTools,
#         ),
#         Agent(
#             id="data_analysis",
#             name="Data Analysis Agent",
#             description=DataAnalysisDescription,
#             prompt=DataAnalysisPrompt,
#             tools=create_data_analysis_tools(api_keys)
#         ),
#         Agent(
#             id="searcher",
#             name="Searcher Agent",
#             description=SearcherDescription,
#             prompt=SearcherPrompt,
#             tools=create_searcher_tools(api_keys),
#         ),
#         Agent(
#             id="single_cell",
#             name="Single Cell Agent",
#             description=SingleCellDescription,
#             prompt=SingleCellPrompt,
#             tools=create_single_cell_tools(api_keys),
#         ),
#         # Agent(
#         #     id="reporter",
#         #     name="Report Agent",
#         #     description=ReporterDescription,
#         #     prompt=ReporterPrompt,
#         #     tools=create_reporter_tools(api_keys),
#         # )
#     ]
