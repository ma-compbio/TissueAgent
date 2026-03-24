"""Central registry of all TissueAgent agents.

Defines the :class:`ReActAgent` and :class:`CustomAgent` dataclasses used to
declaratively describe each agent, and instantiates the five main pipeline
agents (Planner, Recruiter, Manager, Evaluator, Reporter) plus the
specialized sub-agents listed in :data:`AgentDefns`.
"""

from dataclasses import dataclass
from typing import Callable, List, Union

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel

from agents.agent_utils import file_retriever_tool
from agents.planner_agent.prompt import PlannerPrompt
from agents.planner_agent.tools import PlannerTools
from agents.recruiter_agent.prompt import RecruiterPrompt
from agents.manager_agent.prompt import ManagerPrompt
from agents.manager_agent.tools import ManagerTool
from agents.evaluator_agent.prompt import EvaluatorPrompt
from agents.reporter_agent.prompt import ReporterPrompt
from agents.reporter_agent.tools import ReporterTools
from config import DefaultModelCtor

import agents.agent_registry.coding_agent.model as CodingAgent
from agents.agent_registry.coding_agent.prompt import CodingAgentDescription
import agents.agent_registry.hypothesis_agent.model as HypothesisAgent
from agents.agent_registry.searcher_agent.prompt import (
    SearcherPrompt,
    SearcherDescription,
)
from agents.agent_registry.searcher_agent.tools import SearcherTools
from agents.agent_registry.single_cell_agent.prompt import (
    SingleCellPrompt,
    SingleCellDescription,
)
from agents.agent_registry.single_cell_agent.tools import SingleCellTools
from agents.agent_registry.pdf_reader_agent.prompt import (
    PDFReaderAgentPrompt,
    PDFReaderAgentDescription,
)
from agents.agent_registry.pdf_reader_agent.tools import PDFReaderTools
from agents.agent_registry.critic_agent.prompt import (
    CriticAgentPrompt,
    CriticAgentDescription,
)
from agents.agent_registry.critic_agent.tools import CriticTools
from agents.agent_registry.gene_agent.prompt import (
    GeneAgentPrompt,
    GeneAgentDescription,
)
from agents.agent_registry.gene_agent.tools import GeneAgentTools
from agents.agent_registry.hypothesis_agent.prompt import HypothesisAgentDescription


@dataclass
class ReActAgent:
    """Declarative definition of a standard ReAct-style agent.

    Agents described by this class are compiled into LangGraph sub-graphs
    with an agent node (LLM call) and a tool node (tool execution).

    Attributes:
        id: Short unique identifier used to derive graph node IDs.
        name: Human-readable display name shown in the UI.
        description: Free-text description surfaced to the recruiter/manager.
        prompt: System prompt string, or a callable that accepts
            ``agent_id_descriptions`` and returns the prompt.
        tools: List of LangChain ``StructuredTool`` instances available to
            the agent.
        model_ctor: Zero-argument callable that returns a
            :class:`~langchain_core.language_models.BaseChatModel`.
    """

    id: str
    name: str
    description: str
    prompt: Union[str, Callable[..., str]]
    tools: List[StructuredTool]
    model_ctor: Callable[..., BaseChatModel]


@dataclass
class CustomAgent:
    """Declarative definition of an agent with a custom graph constructor.

    Unlike :class:`ReActAgent`, the graph topology is built entirely by the
    *ctor* callable, allowing non-standard patterns such as the CodeAct loop.

    Attributes:
        id: Short unique identifier used to derive graph node IDs.
        name: Human-readable display name shown in the UI.
        description: Free-text description surfaced to the recruiter/manager.
        ctor: Factory callable that accepts a ``state_queue`` and returns a
            :class:`~langchain.tools.StructuredTool` wrapping the compiled
            sub-agent.
    """

    id: str
    name: str
    description: str
    ctor: Callable[..., StructuredTool]


PlannerAgent = ReActAgent(
    id="planner",
    name="Planner Agent",
    description="",
    prompt=PlannerPrompt,
    tools=PlannerTools,
    model_ctor=DefaultModelCtor,
)

RecruiterAgent = ReActAgent(
    id="recruiter",
    name="Recruiter Agent",
    description="",
    prompt=RecruiterPrompt,
    tools=[file_retriever_tool],
    model_ctor=DefaultModelCtor,
)

ManagerAgent = ReActAgent(
    id="manager",
    name="Manager Agent",
    description="",
    prompt=ManagerPrompt,
    tools=ManagerTool,
    model_ctor=DefaultModelCtor,
)

EvaluatorAgent = ReActAgent(
    id="evaluator",
    name="Evaluator Agent",
    description="",
    prompt=EvaluatorPrompt,
    tools=[],
    model_ctor=DefaultModelCtor,
)

ReporterAgent = ReActAgent(
    id="reporter",
    name="Reporter Agent",
    description="",
    prompt=ReporterPrompt,
    tools=ReporterTools,
    model_ctor=DefaultModelCtor,
)

AgentDefns: List[Union[ReActAgent, CustomAgent]] = [
    CustomAgent(
        id="coding",
        name="Coding Agent",
        description=CodingAgentDescription,
        ctor=CodingAgent.create_coding_agent,
    ),
    ReActAgent(
        id="pdf_reader",
        name="PDF Reader Agent",
        description=PDFReaderAgentDescription,
        prompt=PDFReaderAgentPrompt,
        tools=PDFReaderTools,
        model_ctor=DefaultModelCtor,
    ),
    ReActAgent(
        id="searcher",
        name="Searcher Agent",
        description=SearcherDescription,
        prompt=SearcherPrompt,
        tools=SearcherTools,
        model_ctor=DefaultModelCtor,
    ),
    ReActAgent(
        id="single_cell",
        name="Single Cell Agent",
        description=SingleCellDescription,
        prompt=SingleCellPrompt,
        tools=SingleCellTools,
        model_ctor=DefaultModelCtor,
    ),
    ReActAgent(
        id="critic",
        name="Critic Agent",
        description=CriticAgentDescription,
        prompt=CriticAgentPrompt,
        tools=CriticTools,
        model_ctor=DefaultModelCtor,
    ),
    ReActAgent(
        id="gene_agent",
        name="Gene Agent",
        description=GeneAgentDescription,
        prompt=GeneAgentPrompt,
        tools=GeneAgentTools,
        model_ctor=DefaultModelCtor,
    ),
    CustomAgent(
        id="hypothesis",
        name="Hypothesis Agent",
        description=HypothesisAgentDescription,
        ctor=lambda state_queue: HypothesisAgent.create_hypothesis_agent(state_queue),
    ),
]
