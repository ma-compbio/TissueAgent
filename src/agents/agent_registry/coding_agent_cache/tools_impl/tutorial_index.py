"""Name + keyword retrieval index over tutorial markdown files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.agent_registry.coding_agent_cache.tools_impl.retrieval_index import RetrievalIndex


class TutorialIndex(RetrievalIndex):
    """Retrieval over tutorial markdown files by title or keyword."""

    def __init__(self, tutorial_directories: dict[str, Path]):
        """Load markdown tutorials and build the entry list.

        Args:
            tutorial_directories: Mapping of library names to directories
                containing markdown tutorial files with YAML frontmatter.
        """
        self._entries: list[dict[str, Any]] = []
        self._library_mapping: dict[int, str] = {}
        idx = 0
        for library_name, tutorial_dir in tutorial_directories.items():
            for md_file in sorted(tutorial_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                fm = self._parse_frontmatter(content)
                title = fm.get("title") or self._extract_title(content)
                keywords = fm.get("keywords") or []
                self._entries.append(
                    {
                        "filename": md_file.name,
                        "title": title,
                        "keywords": keywords,
                        "content": content,
                    }
                )
                self._library_mapping[idx] = library_name
                idx += 1

    def _get_name(self, entry: dict[str, Any]) -> str:
        return entry["title"]

    def _get_keywords(self, entry: dict[str, Any]) -> list[str]:
        return entry.get("keywords", [])

    # ------------------------------------------------------------------
    # Frontmatter / title helpers (carried over from the old index)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract title from the first ``# Heading`` line."""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return "Untitled"

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, Any]:
        """Parse a minimal YAML frontmatter block (``---`` delimited)."""
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return {}
        end_idx = None
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            return {}
        fm_lines = lines[1:end_idx]
        result: dict[str, Any] = {}
        i = 0
        while i < len(fm_lines):
            line = fm_lines[i]
            if not line.strip():
                i += 1
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"')
                if key == "title":
                    if val:
                        result["title"] = val.strip('"')
                    else:
                        j = i + 1
                        while j < len(fm_lines) and not fm_lines[j].strip():
                            j += 1
                        if j < len(fm_lines):
                            result["title"] = fm_lines[j].strip().strip('"')
                            i = j
                elif key == "keywords":
                    kws: list[str] = []
                    j = i + 1
                    while j < len(fm_lines):
                        item = fm_lines[j].strip()
                        if item.startswith("-"):
                            kw = item[1:].strip().strip('"')
                            if kw:
                                kws.append(kw)
                            j += 1
                        elif not item:
                            j += 1
                        else:
                            break
                    if kws:
                        result["keywords"] = kws
                    i = j - 1
            i += 1
        return result

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entry_verbose(entry: dict[str, Any], library: str) -> str:
        """Full tutorial content (name lookup)."""
        return f"[{library}] {entry['title']}\n\n{entry['content']}"

    @staticmethod
    def _format_entry_compact(entry: dict[str, Any], library: str) -> str:
        """Compact summary for keyword search results."""
        kws = ", ".join(entry.get("keywords", []))
        # First ~200 chars of content after frontmatter
        content = entry["content"]
        # Skip past frontmatter if present
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        snippet = content[:200].replace("\n", " ").strip()
        return f"[{library}] {entry['title']}\n  Keywords: {kws}\n  {snippet}..."

    def format_results(self, results: list[dict[str, Any]], *, verbose: bool) -> str:
        """Render a list of results as a readable string."""
        if not results:
            return "No results found."
        formatter = self._format_entry_verbose if verbose else self._format_entry_compact
        blocks = [formatter(r["entry"], r["library"]) for r in results]
        return "\n\n".join(blocks)
