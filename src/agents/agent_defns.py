"""Central registry of all TissueAgent agents.

Defines the :class:`ReActAgent` and :class:`CustomAgent` dataclasses used to declaratively describe
each agent, and instantiates the five main pipeline agents (Planner, Recruiter, Manager, Evaluator,
Reporter) plus the specialized sub-agents listed in :data:`AgentDefns`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel

import agents.agent_registry.coding_agent.model as CodingAgent
import agents.agent_registry.hypothesis_agent.model as HypothesisAgent
from agents.agent_registry.cell_annotater_agent.prompt import (
    CellTissueAnnotationDescription,
    CellTissueAnnotationPrompt,
)
from agents.agent_registry.cell_annotater_agent.tools import CellAnnotaterTools
from agents.agent_registry.coding_agent.prompt import CodingAgentDescription
from agents.agent_registry.critic_agent.prompt import (
    CriticAgentDescription,
    CriticAgentPrompt,
)
from agents.agent_registry.critic_agent.tools import CriticTools
from agents.agent_registry.gene_agent import agent_definition as GeneAgentDef
from agents.agent_registry.hypothesis_agent.prompt import HypothesisAgentDescription
from agents.agent_registry.pdf_reader_agent.prompt import (
    PDFReaderAgentDescription,
    PDFReaderAgentPrompt,
)
from agents.agent_registry.pdf_reader_agent.tools import PDFReaderTools
from agents.agent_registry.searcher_agent.prompt import (
    SearcherDescription,
    SearcherPrompt,
)
from agents.agent_registry.searcher_agent.tools import SearcherTools
from agents.agent_registry.single_cell_agent.prompt import (
    SingleCellDescription,
    SingleCellPrompt,
)
from agents.agent_registry.single_cell_agent.tools import SingleCellTools
from agents.agent_registry.spot_agent.prompt import (
    SpotDescription,
    SpotPrompt,
)
from agents.agent_registry.spot_agent.tools import SpotTools
from agents.evaluator_agent.prompt import EvaluatorPrompt
from agents.evaluator_agent.tools import EvaluatorTools
from agents.manager_agent.prompt import ManagerPrompt
from agents.manager_agent.tools import ManagerTools
from agents.planner_agent.prompt import PlannerPrompt
from agents.planner_agent.tools import PlannerTools
from agents.recruiter_agent.prompt import RecruiterPrompt
from agents.recruiter_agent.tools import RecruiterTools
from agents.reporter_agent.prompt import ReporterPrompt
from agents.reporter_agent.tools import ReporterTools
from config import DefaultModelCtor
from models import model_ctor_for_role

WorkerModelCtor = model_ctor_for_role("worker")


@dataclass
class ReActAgent:
    """Declarative definition of a standard ReAct-style agent.

    Agents described by this class are compiled into LangGraph sub-graphs with an agent node (LLM
    call) and a tool node (tool execution).

    Attributes:
        id: Short unique identifier used to derive graph node IDs.
        name: Human-readable display name shown in the UI.
        description: Free-text description surfaced to the recruiter/manager.
        prompt: System prompt string, or a callable that accepts ``agent_id_descriptions`` and
            returns the prompt.
        tools: List of LangChain ``StructuredTool`` instances available to the agent.
        model_ctor: Zero-argument callable that returns a
            :class:`~langchain_core.language_models.BaseChatModel`.
    """

    id: str
    name: str
    description: str
    prompt: str | Callable[..., str]
    tools: list[StructuredTool]
    model_ctor: Callable[..., BaseChatModel]


@dataclass
class CustomAgent:
    """Declarative definition of an agent with a custom graph constructor.

    Unlike :class:`ReActAgent`, the graph topology is built entirely by the *ctor* callable,
    allowing non-standard patterns such as the CodeAct loop.

    Attributes:
        id: Short unique identifier used to derive graph node IDs.
        name: Human-readable display name shown in the UI.
        description: Free-text description surfaced to the recruiter/manager.
        ctor: Factory callable that accepts a ``state_queue`` and returns a
            :class:`~langchain.tools.StructuredTool` wrapping the compiled sub-agent.
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
    tools=RecruiterTools,
    model_ctor=DefaultModelCtor,
)

ManagerAgent = ReActAgent(
    id="manager",
    name="Manager Agent",
    description="",
    prompt=ManagerPrompt,
    tools=ManagerTools,
    model_ctor=DefaultModelCtor,
)

EvaluatorAgent = ReActAgent(
    id="evaluator",
    name="Evaluator Agent",
    description="",
    prompt=EvaluatorPrompt,
    tools=EvaluatorTools,
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

AgentDefns: list[ReActAgent | CustomAgent] = [
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
        model_ctor=WorkerModelCtor,
    ),
    ReActAgent(
        id="searcher",
        name="Searcher Agent",
        description=SearcherDescription,
        prompt=SearcherPrompt,
        tools=SearcherTools,
        model_ctor=WorkerModelCtor,
    ),
    ReActAgent(
        id="single_cell",
        name="Single Cell Agent",
        description=SingleCellDescription,
        prompt=SingleCellPrompt,
        tools=SingleCellTools,
        model_ctor=WorkerModelCtor,
    ),
    ReActAgent(
        id="critic",
        name="Critic Agent",
        description=CriticAgentDescription,
        prompt=CriticAgentPrompt,
        tools=CriticTools,
        model_ctor=WorkerModelCtor,
    ),
    ReActAgent(
        id=GeneAgentDef.id,
        name=GeneAgentDef.name,
        description=GeneAgentDef.description,
        prompt=GeneAgentDef.prompt,
        tools=GeneAgentDef.tools,
        model_ctor=GeneAgentDef.model_ctor,
    ),
    ReActAgent(
        id="cell_annotator",
        name="Cell Annotator Agent",
        description=CellTissueAnnotationDescription,
        prompt=CellTissueAnnotationPrompt,
        tools=CellAnnotaterTools,
        model_ctor=WorkerModelCtor,
    ),
    ReActAgent(
        id="spot",
        name="Spot Agent",
        description=SpotDescription,
        prompt=SpotPrompt,
        tools=SpotTools,
        model_ctor=WorkerModelCtor,
    ),
    CustomAgent(
        id="hypothesis",
        name="Hypothesis Agent",
        description=HypothesisAgentDescription,
        ctor=lambda state_queue, context_resolver=None: HypothesisAgent.create_hypothesis_agent(
            state_queue, context_resolver
        ),
    ),
]
