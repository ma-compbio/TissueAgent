"""Name + keyword retrieval index over spatial transcriptomics library documentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.agent_registry.coding_agent_cache.tools_impl.retrieval_index import RetrievalIndex


class DocumentationIndex(RetrievalIndex):
    """Retrieval over JSON documentation entries by method name or keyword."""

    def __init__(self, doc_filepaths: dict[str, Path]):
        """Load JSON docs and build the entry list.

        Args:
            doc_filepaths: Mapping of library names to JSON file paths.
                Each JSON file contains a list of entries with at least
                ``method``, ``keywords``, ``signature``, ``description``,
                ``params``, and ``misc`` fields.
        """
        self._entries: list[dict[str, Any]] = []
        self._library_mapping: dict[int, str] = {}
        idx = 0
        for library_name, p in doc_filepaths.items():
            with p.open("r") as f:
                entries = json.load(f)
            for entry in entries:
                self._entries.append(entry)
                self._library_mapping[idx] = library_name
                idx += 1

    def _get_name(self, entry: dict[str, Any]) -> str:
        return entry["method"]

    def _get_keywords(self, entry: dict[str, Any]) -> list[str]:
        return entry.get("keywords", [])

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entry_verbose(entry: dict[str, Any], library: str) -> str:
        """Full detail for a single entry (name lookup)."""
        parts = [
            f"[{library}] {entry['method']}",
            f"  Signature: {entry['signature']}",
            f"  Description: {entry['description']}",
        ]
        for p in entry.get("params", []):
            ptype = f" ({p['type']})" if p.get("type") else ""
            parts.append(f"  - {p['name']}{ptype}: {p.get('desc', '')}")
        if entry.get("misc"):
            parts.append(f"  Notes: {entry['misc']}")
        return "\n".join(parts)

    @staticmethod
    def _format_entry_compact(entry: dict[str, Any], library: str) -> str:
        """Compact summary for keyword search results."""
        return f"[{library}] {entry['method']} — {entry['description']}"

    def format_results(self, results: list[dict[str, Any]], *, verbose: bool) -> str:
        """Render a list of results as a readable string."""
        if not results:
            return "No results found."
        formatter = self._format_entry_verbose if verbose else self._format_entry_compact
        blocks = [formatter(r["entry"], r["library"]) for r in results]
        return "\n\n".join(blocks)
