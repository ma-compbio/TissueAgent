"""Google Scholar search engine backed by SerpAPI."""

import os
from pydantic import SecretStr
from serpapi import GoogleSearch
from typing import Optional


class GoogleScholarAPIEngine:
    """Search engine that queries Google Scholar through the SerpAPI service."""

    def __init__(
        self,
        serp_api_key: Optional[SecretStr] = None,
        top_k_results: int = 40,
        hl: str = "en",
        lr: str = "lang_en",
    ):
        """Initialize with SerpAPI credentials and search parameters.

        Args:
            serp_api_key: SerpAPI key. Falls back to the SERP_API_KEY env var.
            top_k_results: Maximum number of results to return (capped at 40).
            hl: Host language for the Google Scholar interface.
            lr: Language restriction for results.
        """
        if serp_api_key is None:
            self._serp_api_key = SecretStr(os.getenv("SERP_API_KEY", ""))
        else:
            self._serp_api_key = serp_api_key
        self._top_k_results = top_k_results
        self._hl = hl
        self._lr = lr

    def run(self, query: str) -> str:
        """Execute a Google Scholar search and return formatted results.

        Args:
            query: Search query string.

        Returns:
            Newline-separated entries with title, authors, summary, and link for each result,
            or an error message if no results are found.
        """
        search = GoogleSearch(
            {
                "engine": "google_scholar",
                "q": query,
                "api_key": self._serp_api_key.get_secret_value(),
                "hl": self._hl,
                "lr": self._lr,
                "num": min(self._top_k_results, 40),
            }
        )
        results = search.get_dict().get("organic_results", [])
        if not results:
            return "Error: No good Google Scholar Result was found."
        formatted = []
        for result in results:
            pub_info = result.get("publication_info", {})
            authors = ", ".join(
                a.get("name") for a in pub_info.get("authors", [])
            )
            entry = (
                f"Title: {result.get('title', '')}\n"
                f"Authors: {authors}\n"
                f"Summary: {result.get('snippet', '')}\n"
                f"Link: {result.get('link', '')}"
            )
            formatted.append(entry)
        return "\n\n".join(formatted)
