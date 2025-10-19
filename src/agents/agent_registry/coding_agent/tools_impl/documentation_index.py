import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Sequence

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer


class DocumentationIndex:
    """Hybrid embedding and token-level retrieval over documentation.
    """

    def _norm(self, x: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-9
        return x / n

    def __init__(
        self,
        doc_filepaths: Sequence[Path],
        *,
        embedder_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        show_progress: bool = False,
    ):
        """Builds dense and sparse indexes from JSON docs.
        
        Args:
            doc_filepaths: Paths to JSON files, each containing a list of 
                entries with keys including method and description.
            embedder_name: SentenceTransformer model name for dense embeddings.
        """

        entries = []
        for p in doc_filepaths:
            with p.open("r") as f:
                entries.extend(json.load(f))

        self._docs: List[Dict[str, Any]] = []
        self._texts: List[str] = []
        for entry in entries:
            self._docs.append(entry)
            self._texts.append(f"{entry['method']} | {entry['description']}")

        self._model = SentenceTransformer(embedder_name)
        self._embedder = self._norm(self._model.encode(
            self._texts, 
            convert_to_numpy=True,
            batch_size=64,
            show_progress_bar=show_progress,
        ))

        self._vect = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.9)
        self._tfidf = self._vect.fit_transform(self._texts)

    def search(
        self,
        query_text: str,
        *,
        k: int       = 8,
        alpha: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Runs hybrid retrieval over method/description.
        
        Args:
            query_text: Natural language or token-style query.
            k: Number of results to return.
            alpha: Blend weight for dense vs. sparse scores in [0,1].
        
        Returns:
            A list of {score, doc} dictionaries ordered by relevance.
        """

        qv = self._norm(self._model.encode([query_text], convert_to_numpy=True))
        dense_scores = (self._embedder @ qv.T).ravel()

        sparse_vec = self._vect.transform([query_text])
        sparse_scores = (self._tfidf @ sparse_vec.T).toarray().ravel()
        if sparse_scores.max() > 0:
            sparse_scores = sparse_scores / sparse_scores.max()

        scores = alpha * dense_scores + (1 - alpha) * sparse_scores
        idx = np.argsort(-scores)
        out = []
        for i in idx:
            out.append({"score": float(scores[i]), "doc": self._docs[i]})
            if len(out) >= k:
                break
        return out