from pymed import PubMed
from pymed.article import PubMedArticle
from typing import Optional

class PubMedAPIEngine:
    def __init__(self,
                 email: Optional[str]=None,
                 top_k_results: int=20):
        if email:
            self._pubmed = PubMed(tool="SpatialAgent",
                                  email=email)
        else:
            self._pubmed = PubMed(tool="SpatialAgent")
        self._top_k_results = top_k_results


    def run(self, query: str) -> str:
        search_results = self._pubmed.query(query, max_results=self._top_k_results)

        entries = []
        for search_result in search_results:
            if not isinstance(search_result, PubMedArticle):
                continue
            entries.append("\n".join([
                f"Title: {search_result.title}",
                f"Abstract: {search_result.abstract}",
                f"DOI: {search_result.doi.split()[0]}",
            ]))
        return "\n\n".join(entries)
