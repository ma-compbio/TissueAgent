import os
from pydantic import SecretStr
from serpapi import GoogleSearch
from typing import Optional

class GoogleScholarAPIEngine:
    def __init__(self,
                 serp_api_key: Optional[SecretStr] = None,
                 top_k_results: int=40,
                 hl: str="en",
                 lr: str="lang_en"):
        if serp_api_key is None:
            self._serp_api_key = SecretStr(os.getenv("SERP_API_KEY", ""))
        else:
            self._serp_api_key = serp_api_key
        self._top_k_results = top_k_results
        self._hl = hl
        self._lr = lr

    def run(self, query: str) -> str:
        search = GoogleSearch({
            "engine": "google_scholar",
            "q": query,

            "api_key": self._serp_api_key.get_secret_value(),
            "hl": self._hl,
            "lr": self._lr,
            "num": min(self._top_k_results, 40),
        })
        results = search.get_dict().get("organic_results", [])
        if not results:
            return "Error: No good Google Scholar Result was found."
        return "\n\n".join([
            f"Title: {result.get('title', '')}\n"
            f"Authors: {', '.join([a.get('name') for a in result.get('publication_info', {}).get('authors', [])])}\n"
            f"Summary: {result.get('snippet', '')}\n"
            f"Link: {result.get('link', '')}"
                for result in results
        ])
