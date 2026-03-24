"""Hybrid dense+sparse retrieval index over spatial transcriptomics library documentation."""

import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, cast

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix


class DocumentationIndex:
    """Hybrid embedding and token-level retrieval over documentation."""

    def _norm(self, x: np.ndarray) -> np.ndarray:
        """L2-normalize row vectors."""
        n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-9
        return x / n

    def _levenshtein_ratio(self, a: str, b: str) -> float:
        """Compute normalized Levenshtein similarity ratio in [0,1]."""
        if a == b:
            return 1.0
        la, lb = len(a), len(b)
        if la == 0 or lb == 0:
            return 0.0
        # Use O(min(la, lb)) space
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
                    current[j - 1] + 1,  # insertion
                    prev_row[j] + 1,  # deletion
                    prev_row[j - 1] + cost,  # substitution
                )
            prev_row = current
        dist = prev_row[lb]
        return 1.0 - (dist / max(la, lb))

    def __init__(
        self,
        doc_filepaths: Dict[str, Path],
        *,
        embedder_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        show_progress: bool = False,
    ):
        """Build dense and sparse indexes from JSON docs.

        Args:
            doc_filepaths: Dictionary mapping library names to paths to JSON files,
                each containing a list of entries with keys including method and description.
            embedder_name: SentenceTransformer model name for dense embeddings.
            show_progress: Whether to display a progress bar during encoding.
        """
        entries = []
        self._library_mapping = {}  # Maps entry index to library name
        entry_index = 0

        for library_name, p in doc_filepaths.items():
            with p.open("r") as f:
                library_entries = json.load(f)
                entries.extend(library_entries)
                # Map each entry to its library
                for _ in library_entries:
                    self._library_mapping[entry_index] = library_name
                    entry_index += 1

        self._docs: List[Dict[str, Any]] = []
        self._texts: List[str] = []
        for entry in entries:
            self._docs.append(entry)
            self._texts.append(f"{entry['method']} | {entry['description']}")

        self._model = SentenceTransformer(embedder_name)
        self._embedder = self._norm(
            self._model.encode(
                self._texts,
                convert_to_numpy=True,
                batch_size=64,
                show_progress_bar=show_progress,
            )
        )

        self._vect = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.9)
        self._tfidf = self._vect.fit_transform(self._texts)

    def search(
        self,
        query_text: str,
        *,
        library: str | None = None,
        k: int = 8,
        alpha: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """Runs hybrid retrieval over method/description.

        Args:
            query_text: Natural language or token-style query.
            library: Optional library name to filter results (e.g., 'scanpy', 'squidpy').
            k: Number of results to return.
            alpha: Blend weight for dense vs. sparse scores in [0,1].

        Returns:
            A list of {score, doc, library} dictionaries ordered by relevance.
        """
        # Normalize query for exact / near-exact matching on method name
        raw_query = query_text.strip()
        query_core = raw_query.split("(", 1)[0].strip()

        # If library filter is set, restrict indices accordingly
        if library is not None:
            candidate_indices = [i for i, lib in self._library_mapping.items() if lib == library]
        else:
            candidate_indices = list(range(len(self._docs)))

        # 1) Exact match on method string
        for i in candidate_indices:
            if self._docs[i]["method"] == query_core:
                return [
                    {
                        "score": 1.0,
                        "doc": self._docs[i],
                        "library": self._library_mapping[i],
                    }
                ]

        # 2) Case-insensitive exact match
        lc_query = query_core.lower()
        for i in candidate_indices:
            if self._docs[i]["method"].lower() == lc_query:
                return [
                    {
                        "score": 0.999,
                        "doc": self._docs[i],
                        "library": self._library_mapping[i],
                    }
                ]

        # 3) Unique suffix match (query is unqualified tail)
        suffix_matches = [
            i
            for i in candidate_indices
            if self._docs[i]["method"].endswith("." + query_core)
            or self._docs[i]["method"] == query_core
        ]
        if len(suffix_matches) == 1:
            i = suffix_matches[0]
            return [
                {
                    "score": 0.995,
                    "doc": self._docs[i],
                    "library": self._library_mapping[i],
                }
            ]

        # 4) Near-exact string similarity on method string
        if candidate_indices:
            sims = [
                (i, self._levenshtein_ratio(query_core, self._docs[i]["method"]))
                for i in candidate_indices
            ]
            best_i, best_sim = max(sims, key=lambda t: t[1])
            if best_sim >= 0.985:
                return [
                    {
                        "score": float(best_sim),
                        "doc": self._docs[best_i],
                        "library": self._library_mapping[best_i],
                    }
                ]

        # Fall back to hybrid retrieval
        qv = self._norm(self._model.encode([raw_query], convert_to_numpy=True))
        dense_scores = (self._embedder @ qv.T).ravel()

        sparse_vec = cast(csr_matrix, self._vect.transform([raw_query]))
        sparse_scores = (self._tfidf @ sparse_vec.T).toarray().ravel()
        if sparse_scores.max() > 0:
            sparse_scores = sparse_scores / sparse_scores.max()

        scores = alpha * dense_scores + (1 - alpha) * sparse_scores

        # Filter by library if specified
        if library is not None:
            filtered_indices = [i for i, lib in self._library_mapping.items() if lib == library]
            if not filtered_indices:
                return []  # No results for this library
            # Only consider scores for the filtered library
            filtered_scores = np.array([scores[i] for i in filtered_indices])
            idx = np.argsort(-filtered_scores)
            # Map back to original indices
            idx = [filtered_indices[i] for i in idx]
        else:
            idx = np.argsort(-scores)

        out = []
        for i in idx:
            entry_library = self._library_mapping[i]
            out.append(
                {
                    "score": float(scores[i]),
                    "doc": self._docs[i],
                    "library": entry_library,
                }
            )
            if len(out) >= k:
                break
        return out
