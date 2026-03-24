"""Factory functions that create LangChain tools for the Searcher agent."""

from typing import List
from langchain.tools import StructuredTool

from agents.agent_registry.searcher_agent.tools_impl.google_scholar_search_tool import (
    GoogleScholarAPIEngine,
)
from agents.agent_registry.searcher_agent.tools_impl.pubmed_search_tool import (
    PubMedAPIEngine,
)
from agents.agent_registry.searcher_agent.tools_impl.openai_web_search_tool import (
    OpenAIWebSearchEngine,
)


def create_google_scholar_search_tool() -> StructuredTool:
    """Create a LangChain tool that searches Google Scholar via SerpAPI.

    Returns:
        A StructuredTool wrapping GoogleScholarAPIEngine.run.
    """
    google_scholar_api_engine = GoogleScholarAPIEngine()
    return StructuredTool.from_function(
        func=google_scholar_api_engine.run,
        name="google_scholar_search_tool",
        description="Searches Google Scholar for the provided query",
    )


def create_pubmed_search_tool() -> StructuredTool:
    """Create a LangChain tool that searches PubMed via pymed.

    Returns:
        A StructuredTool wrapping PubMedAPIEngine.run.
    """
    pubmed_api_engine = PubMedAPIEngine()
    return StructuredTool.from_function(
        func=pubmed_api_engine.run,
        name="pubmed_search_tool",
        description="Searches PubMed for the provided query",
    )


def create_openai_web_search_tool() -> StructuredTool:
    """Create a LangChain tool that performs web search via the OpenAI Responses API.

    Returns:
        A StructuredTool wrapping OpenAIWebSearchEngine.run.
    """
    openai_web_engine = OpenAIWebSearchEngine()
    return StructuredTool.from_function(
        func=openai_web_engine.run,
        name="openai_web_search_tool",
        description="General web search via OpenAI Responses API. Returns a concise summary with citations.",
    )


SearcherTools: List[StructuredTool] = [
    create_google_scholar_search_tool(),
    create_pubmed_search_tool(),
    create_openai_web_search_tool(),
]
