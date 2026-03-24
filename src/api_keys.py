"""Typed dictionary defining the API keys required by TissueAgent."""

from pydantic import SecretStr
from typing_extensions import TypedDict


class APIKeys(TypedDict):
    """Container for external service API keys used across the agent system.

    Attributes:
        llm: Secret key for the primary LLM provider.
        openai: Secret key for the OpenAI API.
        serp: Secret key for the SerpAPI search service.
        email: Plain-text email address used for PubMed/Entrez queries.
    """

    llm: SecretStr
    openai: SecretStr
    serp: SecretStr
    email: str
