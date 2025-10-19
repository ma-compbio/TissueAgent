# src/agents/searcher_agent/tools.py
from typing import List, Optional, Iterable, Union
from langchain.tools import StructuredTool

from agents.agent_registry.searcher_agent.tools_impl.google_scholar_search_tool import GoogleScholarAPIEngine
from agents.agent_registry.searcher_agent.tools_impl.pubmed_search_tool import PubMedAPIEngine
from agents.agent_registry.searcher_agent.tools_impl.openai_web_search_tool import OpenAIWebSearchEngine

def create_google_scholar_search_tool() -> StructuredTool:
    google_scholar_api_engine = GoogleScholarAPIEngine()
    return StructuredTool.from_function(
        func=google_scholar_api_engine.run,
        name="google_scholar_search_tool",
        description="Searches Google Scholar for the provided query",
    )

def create_pubmed_search_tool() -> StructuredTool:
    pubmed_api_engine = PubMedAPIEngine()
    return StructuredTool.from_function(
        func=pubmed_api_engine.run,
        name="pubmed_search_tool",
        description="Searches PubMed for the provided query",
    )

def create_openai_web_search_tool() -> StructuredTool:
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