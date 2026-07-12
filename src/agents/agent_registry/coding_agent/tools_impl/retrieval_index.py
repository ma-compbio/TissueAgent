"""Base class for name + keyword retrieval indexes."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class RetrievalIndex(ABC):
    """Abstract base for indexes that support name lookup and keyword search."""

    _entries: list[dict[str, Any]]
    _library_mapping: dict[int, str]

    @abstractmethod
    def _get_name(self, entry: dict[str, Any]) -> str:
        """Return the canonical name for an entry."""

    @abstractmethod
    def _get_keywords(self, entry: dict[str, Any]) -> list[str]:
        """Return the keywords list for an entry."""

    # ------------------------------------------------------------------
    # Levenshtein helper (reused from the old DocumentationIndex)
    # ------------------------------------------------------------------

    @staticmethod
    def _levenshtein_ratio(a: str, b: str) -> float:
        """Compute normalized Levenshtein similarity ratio in [0,1]."""
        if a == b:
            return 1.0
        la, lb = len(a), len(b)
        if la == 0 or lb == 0:
            return 0.0
        if lb < la:
            a, b = b, a
            la, lb = lb, la
        prev_row = list(range(lb + 1))
        for i in range(1, la + 1):
            current = [i] + [0] * lb
            ca = a[i - 1]
            for j in range(1, lb + 1):
                cost = 0 if ca == b[j - 1] else 1
                current[j] = min(
                    current[j - 1] + 1,
                    prev_row[j] + 1,
                    prev_row[j - 1] + cost,
                )
            prev_row = current
        dist = prev_row[lb]
        return 1.0 - (dist / max(la, lb))

    # ------------------------------------------------------------------
    # Lookup by name — 4-tier cascade
    # ------------------------------------------------------------------

    def _candidate_indices(self, library: str | None) -> list[int]:
        if library is not None:
            return [i for i, lib in self._library_mapping.items() if lib == library]
        return list(range(len(self._entries)))

    def lookup_by_name(
        self,
        name: str,
        *,
        library: str | None = None,
        k: int = 5,
        fuzzy_threshold: float = 0.75,
    ) -> list[dict[str, Any]]:
        """Find entries by name with a 4-tier matching cascade.

        1. Exact match
        2. Case-insensitive exact match
        3. Unique suffix match
        4. Levenshtein fuzzy match (threshold, top-k)
        """
        raw = name.strip()
        query = raw.split("(", 1)[0].strip()
        candidates = self._candidate_indices(library)

        def _result(idx: int, score: float) -> dict[str, Any]:
            return {
                "score": score,
                "entry": self._entries[idx],
                "library": self._library_mapping[idx],
            }

        # 1) Exact match
        for i in candidates:
            if self._get_name(self._entries[i]) == query:
                return [_result(i, 1.0)]

        # 2) Case-insensitive exact match
        lc = query.lower()
        for i in candidates:
            if self._get_name(self._entries[i]).lower() == lc:
                return [_result(i, 0.999)]

        # 3) Unique suffix match
        suffix_matches = [
            i
            for i in candidates
            if self._get_name(self._entries[i]).endswith("." + query)
            or self._get_name(self._entries[i]) == query
        ]
        if len(suffix_matches) == 1:
            return [_result(suffix_matches[0], 0.995)]

        # 4) Fuzzy match
        if not candidates:
            return []
        scored = [
            (i, self._levenshtein_ratio(query, self._get_name(self._entries[i])))
            for i in candidates
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        results = []
        for i, sim in scored:
            if sim < fuzzy_threshold:
                break
            results.append(_result(i, sim))
            if len(results) >= k:
                break
        return results

    # ------------------------------------------------------------------
    # Search by keyword — case-insensitive substring
    # ------------------------------------------------------------------

    def search_by_keyword(
        self, keyword: str, *, library: str | None = None
    ) -> list[dict[str, Any]]:
        """Find entries whose name or keywords contain all query tokens.

        The query is split on whitespace, ``_``, and ``.``; every token must
        appear as a case-insensitive substring in the entry's name or one of
        its keywords. This lets multi-token queries like ``rank_aggregate``
        match entries even when the underlying keyword list stores the tokens
        separately (e.g. ``["rank", "aggregate"]``).
        """
        if not keyword:
            return []
        tokens = [t for t in re.split(r"[\s_.]+", keyword.lower().strip()) if t]
        if not tokens:
            return []
        candidates = self._candidate_indices(library)
        results: list[dict[str, Any]] = []
        for i in candidates:
            entry = self._entries[i]
            haystack = self._get_name(entry).lower() + " " + " ".join(
                kw.lower() for kw in self._get_keywords(entry)
            )
            if all(t in haystack for t in tokens):
                results.append(
                    {
                        "entry": entry,
                        "library": self._library_mapping[i],
                    }
                )
        return results
