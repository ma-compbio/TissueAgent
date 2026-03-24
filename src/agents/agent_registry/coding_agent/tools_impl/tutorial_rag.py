"""Chunk-based RAG retrieval over tutorial markdown files."""

import numpy as np
from pathlib import Path
from typing import Any, Dict, List, cast

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix


class TutorialRAG:
    """RAG system for tutorial files that returns relevant chunks of content."""

    def _norm(self, x: np.ndarray) -> np.ndarray:
        """L2-normalize row vectors."""
        n = np.linalg.norm(x, axis=1, keepdims=True) + 1e-9
        return x / n

    def __init__(
        self,
        tutorial_directories: Dict[str, Path],
        *,
        embedder_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        show_progress: bool = False,
    ):
        """Build RAG index from tutorial markdown files with chunking.

        Args:
            tutorial_directories: Dictionary mapping library names to paths to tutorial directories
                containing markdown files.
            embedder_name: SentenceTransformer model name for dense embeddings.
            chunk_size: Maximum size of each text chunk.
            chunk_overlap: Number of characters to overlap between chunks.
            show_progress: Whether to display a progress bar during encoding.
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

                # Split content into chunks
                chunks = self._split_into_chunks(content, chunk_size, chunk_overlap)

                for chunk_idx, chunk in enumerate(chunks):
                    # Create entry for each chunk
                    entry = {
                        "filename": md_file.name,
                        "chunk_index": chunk_idx,
                        "content": chunk,
                        "title": self._extract_title(content),
                        "full_content": content,  # Keep reference to full content
                    }
                    entries.append(entry)
                    self._library_mapping[entry_index] = library_name
                    entry_index += 1

        self._docs: List[Dict[str, Any]] = []
        self._texts: List[str] = []
        for entry in entries:
            self._docs.append(entry)
            # Use title and chunk content for search indexing
            search_text = f"{entry['title']} | {entry['content']}"
            self._texts.append(search_text)

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

    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content (first # heading)."""
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
        return "Untitled"

    def _split_into_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at a sentence boundary if possible
            if end < len(text):
                # Look for sentence endings within the last 100 characters
                search_start = max(start + chunk_size - 100, start)
                sentence_end = text.rfind(".", search_start, end)
                if sentence_end > search_start:
                    end = sentence_end + 1
                else:
                    # Look for paragraph breaks
                    para_end = text.rfind("\n\n", search_start, end)
                    if para_end > search_start:
                        end = para_end + 2
                    else:
                        # Look for line breaks
                        line_end = text.rfind("\n", search_start, end)
                        if line_end > search_start:
                            end = line_end + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - chunk_overlap
            if start >= len(text):
                break

        return chunks

    def search(
        self,
        query_text: str,
        *,
        library: str | None = None,
        k: int = 8,
        alpha: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Runs hybrid retrieval over tutorial chunks.

        Args:
            query_text: Natural language or token-style query.
            library: Optional library name to filter results (e.g., 'liana', 'squidpy').
            k: Number of results to return.
            alpha: Blend weight for dense vs. sparse scores in [0,1].

        Returns:
            A list of {score, doc, library} dictionaries ordered by relevance.
            The doc contains the relevant chunk content.
        """
        qv = self._norm(self._model.encode([query_text], convert_to_numpy=True))
        dense_scores = (self._embedder @ qv.T).ravel()

        sparse_vec = cast(csr_matrix, self._vect.transform([query_text]))
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
