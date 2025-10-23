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
                    
                entry = {
                    "filename": md_file.name,
                    "content": content,
                    "title": self._extract_title(content)
                }
                entries.append(entry)
                self._library_mapping[entry_index] = library_name
                entry_index += 1

        self._docs: List[Dict[str, Any]] = []
        self._texts: List[str] = []
        for entry in entries:
            self._docs.append(entry)
            search_text = f"{entry['title']} | {entry['content'][:500]}"
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

    def search(
        self,
        query_text: str,
        *,
        library: str | None = None,
        k: int = 8,
        alpha: float = 0.6,
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
