from dataclasses import dataclass
from functools import partial
from typing import Callable, List, Union

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from agents.agent_utils import file_retriever_tool
from agents.planner_agent.prompt import PlannerPrompt
from agents.recruiter_agent.prompt import RecruiterPrompt
from agents.manager_agent.prompt import ManagerPrompt
from agents.evaluator_agent.prompt import EvaluatorPrompt
from agents.reporter_agent.prompt import ReporterPrompt
from agents.reporter_agent.tools import ReporterTools


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
    description = "",
    prompt      = PlannerPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

RecruiterAgent = ReActAgent(
    id          = "recruiter",
    name        = "Recruiter Agent",
    description = "",
    prompt      = RecruiterPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

ManagerAgent = ReActAgent(
    id          = "manager",
    name        = "Manager Agent",
    description = "",
    prompt      = ManagerPrompt,
    tools       = [file_retriever_tool],
    model_ctor  = DefaultModelCtor,
)

EvaluatorAgent = ReActAgent(
    id          = "evaluator",
    name        = "Evaluator Agent",
    description = "",
    prompt      = EvaluatorPrompt,
    tools       = [],
    model_ctor  = DefaultModelCtor,
)

ReporterAgent = ReActAgent(
    id          = "reporter",
    name        = "Reporter Agent",
    description = "",
    prompt      = ReporterPrompt,
    tools       = ReporterTools,
    model_ctor  = DefaultModelCtor,
)

import agents.agent_registry.coding_agent.model as CodingAgent
from agents.agent_registry.coding_agent.prompt import CodingAgentDescription
from agents.agent_registry.searcher_agent.prompt import SearcherPrompt, SearcherDescription
from agents.agent_registry.searcher_agent.tools import SearcherTools
from agents.agent_registry.single_cell_agent.prompt import SingleCellPrompt, SingleCellDescription
from agents.agent_registry.single_cell_agent.tools import SingleCellTools
from agents.agent_registry.gene_agent.prompt import GeneAgentPrompt, GeneAgentDescription
from agents.agent_registry.gene_agent.tools import GeneAgentTools


AgentDefns: List[Union[ReActAgent, CustomAgent]] = [
    CustomAgent(
        id          = "coding",
        name        = "Coding Agent",
        description = CodingAgentDescription,
        ctor        = CodingAgent.create_coding_agent,
    ),
    ReActAgent(
        id          = "searcher",
        name        = "Searcher Agent",
        description = SearcherDescription,
        prompt      = SearcherPrompt,
        tools       = SearcherTools,
        model_ctor  = DefaultModelCtor,
    ),
    ReActAgent(
        id          = "single_cell",
        name        = "Single Cell Agent",
        description = SingleCellDescription,
        prompt      = SingleCellPrompt,
        tools       = SingleCellTools,
        model_ctor  = DefaultModelCtor,
    ),
    ReActAgent(
        id          = "gene_agent",
        name        = "Gene Agent",
        description = GeneAgentDescription,
        prompt      = GeneAgentPrompt,
        tools       = GeneAgentTools,
        model_ctor  = DefaultModelCtor,

    )
]