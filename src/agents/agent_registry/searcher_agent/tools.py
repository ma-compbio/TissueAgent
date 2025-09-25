# src/agents/searcher_agent/tools.py
from typing import List, Optional, Iterable, Union
from langchain.tools import StructuredTool

from agents.agent_registry.searcher_agent.tools_impl.google_scholar_search_tool import GoogleScholarAPIEngine
from agents.agent_registry.searcher_agent.tools_impl.pubmed_search_tool import PubMedAPIEngine

from agents.agent_registry.searcher_agent.tools_impl.openai_web_search_tool import OpenAIWebSearchEngine
from api_keys import APIKeys
from config import CACHED_DOCS_DIR


def create_searcher_tools(api_keys: APIKeys) -> List[StructuredTool]:
    google_scholar_api_engine = GoogleScholarAPIEngine(api_keys["serp"])
    google_scholar_search_tool = StructuredTool.from_function(
        func=google_scholar_api_engine.run,
        name="google_scholar_search_tool",
        description="Searches Google Scholar for the provided query",
    )

    pubmed_api_engine = PubMedAPIEngine(api_keys["email"])
    pubmed_search_tool = StructuredTool.from_function(
        func=pubmed_api_engine.run,
        name="pubmed_search_tool",
        description="Searches PubMed for the provided query",
    )

    openai_web_engine = OpenAIWebSearchEngine(api_keys["openai"])
    openai_web_search_tool = StructuredTool.from_function(
        func=openai_web_engine.run,
        name="openai_web_search_tool",
        description=(
            "General web search via OpenAI Responses API. Returns a concise summary with citations. "
            "Use for up-to-date information on tools, datasets, and non-academic sources."
        ),
    )

    return [
        google_scholar_search_tool,
        pubmed_search_tool,
        # query_cellxgene_single_cell_tool,
        # retrieve_cellxgene_single_cell_tool,
        openai_web_search_tool,
    ]

