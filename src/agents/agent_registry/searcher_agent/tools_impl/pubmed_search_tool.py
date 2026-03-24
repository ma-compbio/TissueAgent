"""PubMed search engine backed by the pymed library."""

from pymed import PubMed
from pymed.article import PubMedArticle
from typing import Optional


class PubMedAPIEngine:
    """Search engine that queries PubMed via the pymed library."""

    def __init__(
        self,
        email: Optional[str] = None,
        top_k_results: int = 20,
    ):
        """Initialize with PubMed API credentials.

        Args:
            email: Contact email for NCBI rate-limiting. Defaults to empty string.
            top_k_results: Maximum number of articles to return.
        """
        self._pubmed = PubMed(tool="TissueAgent", email=email or "")
        self._top_k_results = top_k_results

    def run(self, query: str) -> str:
        """Execute a PubMed search and return formatted results.

        Args:
            query: Search query string.

        Returns:
            Newline-separated entries with title, abstract, and DOI for each article.
        """
        search_results = self._pubmed.query(query, max_results=self._top_k_results)

        entries = []
        for search_result in search_results:
            if not isinstance(search_result, PubMedArticle):
                continue
            entries.append(
                "\n".join(
                    [
                        f"Title: {search_result.title}",
                        f"Abstract: {search_result.abstract}",
                        f"DOI: {search_result.doi.split()[0]}",
                    ]
                )
            )
        return "\n\n".join(entries)
