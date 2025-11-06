import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Sequence, cast

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix


class TutorialIndex:
    """Index for tutorial files that returns entire file content.
    """

    def _norm(self, x: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-9
        return x / n

    def __init__(
        self,
        tutorial_directories: Dict[str, Path],
        *,
        embedder_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        show_progress: bool = False,
    ):
        """Builds index from tutorial markdown files.
        
        Args:
            tutorial_directories: Dictionary mapping library names to paths to tutorial directories
                containing markdown files.
            embedder_name: SentenceTransformer model name for dense embeddings.
        """

        entries = []
        self._library_mapping = {}  # Maps entry index to library name
        entry_index = 0
        
        for library_name, tutorial_dir in tutorial_directories.items():
            # Find all markdown files in the tutorial directory
            md_files = list(tutorial_dir.glob("*.md"))
            
            for md_file in md_files:
                with md_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                # Try to parse frontmatter for title/keywords
                fm = self._parse_frontmatter(content)
                title = fm.get("title") or self._extract_title(content)
                keywords = fm.get("keywords") or []

                entry = {
                    "filename": md_file.name,
                    "content": content,
                    "title": title,
                    "keywords": keywords,
                }
                entries.append(entry)
                self._library_mapping[entry_index] = library_name
                entry_index += 1

        self._docs: List[Dict[str, Any]] = []
        self._texts: List[str] = []
        for entry in entries:
            self._docs.append(entry)
            # Include keywords in the searchable text to boost matches
            kw_text = " ".join(entry.get("keywords", []))
            search_text = f"{entry['title']} | {kw_text} | {entry['content'][:500]}"
            self._texts.append(search_text)

        self._model = SentenceTransformer(embedder_name)
        self._embedder = self._norm(self._model.encode(
            self._texts, 
            convert_to_numpy=True,
            batch_size=64,
            show_progress_bar=show_progress,
        ))

        self._vect = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.9)
        self._tfidf = self._vect.fit_transform(self._texts)

    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content (first line with # heading)."""
        lines = content.split('\n')
        if lines and lines[0].strip().startswith('# '):
            return lines[0].strip()[2:].strip()
        for line in lines:
            if line.strip().startswith('# '):
                return line.strip()[2:].strip()
        return "Untitled"

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse minimal YAML frontmatter block and return a dict with optional
        'title' and 'keywords'. Avoids external YAML dependency by handling the
        common subset we use in tutorials.
        """
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return {}
        # Find the end of the frontmatter
        end_idx = None
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            return {}
        fm_lines = lines[1:end_idx]
        result: Dict[str, Any] = {}
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
                    # Title may be quoted or not; if empty, try next line
                    if val:
                        result["title"] = val.strip('"')
                    else:
                        # Next non-empty line could be the title
                        j = i + 1
                        while j < len(fm_lines) and not fm_lines[j].strip():
                            j += 1
                        if j < len(fm_lines):
                            result["title"] = fm_lines[j].strip().strip('"')
                            i = j
                elif key == "keywords":
                    # Parse list starting at next lines with leading '-'
                    kws: List[str] = []
                    j = i + 1
                    while j < len(fm_lines):
                        item = fm_lines[j].strip()
                        if item.startswith("-"):
                            kw = item[1:].strip()
                            kw = kw.strip('"')
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
                else:
                    # Unused key; skip
                    pass
            i += 1
        return result

    def list_tutorial_names(self, *, library: str | None = None) -> List[str]:
        """Return the list of tutorial titles.
        
        Args:
            library: Optional library name to filter results (e.g., 'liana', 'squidpy').
        
        Returns:
            A sorted list of tutorial titles.
        """
        names: List[str] = []
        for i, doc in enumerate(self._docs):
            if library is not None and self._library_mapping[i] != library:
                continue
            names.append(doc["title"])
        return sorted(names)

    def list_keywords(self, *, library: str | None = None) -> List[str]:
        """Return a sorted list of unique keywords across tutorials.
        
        Args:
            library: Optional library filter.
        """
        seen = set()
        for i, doc in enumerate(self._docs):
            if library is not None and self._library_mapping[i] != library:
                continue
            for kw in doc.get("keywords", []) or []:
                seen.add(kw)
        return sorted(seen, key=lambda s: s.lower())

    def get_tutorial_by_name(self, name: str, *, library: str | None = None) -> Dict[str, Any] | None:
        """Retrieve a tutorial by its title.
        
        Args:
            name: Exact title of the tutorial (as extracted from the markdown).
            library: Optional library name to filter results.
        
        Returns:
            A dictionary with keys 'doc' and 'library' if found, otherwise None.
        """
        for i, doc in enumerate(self._docs):
            if library is not None and self._library_mapping[i] != library:
                continue
            if doc["title"] == name:
                return {"doc": doc, "library": self._library_mapping[i]}
        return None

    def get_tutorials_by_keyword(self, keyword: str, *, library: str | None = None) -> List[Dict[str, Any]]:
        """Retrieve tutorials whose frontmatter keywords match a query.
        Matching is case-insensitive and accepts substring matches within a keyword.
        
        Returns a list of {doc, library} dictionaries.
        """
        if not keyword:
            return []
        q = keyword.lower().strip()
        results: List[Dict[str, Any]] = []
        for i, doc in enumerate(self._docs):
            if library is not None and self._library_mapping[i] != library:
                continue
            kws = [k for k in (doc.get("keywords", []) or [])]
            for kw in kws:
                if q in kw.lower():
                    results.append({"doc": doc, "library": self._library_mapping[i]})
                    break
        return results

    def search(
        self,
        query_text: str,
        *,
        library: str | None = None,
        k: int = 8,
        alpha: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """Runs hybrid retrieval over tutorial content.
        
        Args:
            query_text: Natural language or token-style query.
            library: Optional library name to filter results (e.g., 'liana', 'squidpy').
            k: Number of results to return.
            alpha: Blend weight for dense vs. sparse scores in [0,1].
        
        Returns:
            A list of {score, doc, library} dictionaries ordered by relevance.
            The doc contains the entire file content.
        """

        qv = self._norm(self._model.encode([query_text], convert_to_numpy=True))
        dense_scores = (self._embedder @ qv.T).ravel()

        sparse_vec = cast(csr_matrix, self._vect.transform([query_text]))
        sparse_scores = (self._tfidf @ sparse_vec.T).toarray().ravel()
        if sparse_scores.max() > 0:
            sparse_scores = sparse_scores / sparse_scores.max()

        scores = alpha * dense_scores + (1 - alpha) * sparse_scores
        
        if library is not None:
            filtered_indices = [i for i, lib in self._library_mapping.items() if lib == library]
            if not filtered_indices:
                return []  # No results for this library
            filtered_scores = np.array([scores[i] for i in filtered_indices])
            idx = np.argsort(-filtered_scores)
            idx = [filtered_indices[i] for i in idx]
        else:
            idx = np.argsort(-scores)
        
        out = []
        for i in idx:
            entry_library = self._library_mapping[i]
            out.append({
                "score": float(scores[i]), 
                "doc": self._docs[i],
                "library": entry_library
            })
            if len(out) >= k:
                break
        return out
