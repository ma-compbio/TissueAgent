import logging
import os
import re

from pathlib import Path
from pydantic import SecretStr

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.tools import StructuredTool

from config import CHROMADB_DIR, RAG_DOCUMENT_DIR
from api_keys import APIKeys
from logger import logger


class CodeRAGTool:
    def __init__(
        self,
        openai_api_key: SecretStr,
        chromadb_dirpath: Path,
        embedding_model: str = "text-embedding-3-small",
    ):
        self._chromadb_dirpath = chromadb_dirpath
        self._embedder = OpenAIEmbeddings(api_key=openai_api_key, model=embedding_model)

        self._names = []
        self._values = []
        self._db = None

    def parse_files(self, documentation_dirpath: Path):
        values = []
        names = []
        for dirpath, _, filenames in os.walk(str(documentation_dirpath)):
            for filename in filenames:
                path = Path(dirpath) / filename
                with path.open("r") as file:
                    documentation = file.read()
                names.append(filename)
                values.append(documentation)

        logger.info(f"Tracking RAG embeddings for: {names}")
        self._names = names
        self._values = list(map(lambda text: re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text), values))

    def save_to_chromadb(self):
        # if self._chromadb_dirpath.exists():
        #     shutil.rmtree(self._chromadb_dirpath)
        # self._chromadb_dirpath.mkdir()

        self._db = Chroma.from_texts(
            self._values,
            persist_directory=str(self._chromadb_dirpath),
            embedding=self._embedder,
            collection_name="code_rag",
        )

        logger.info(f"Embedded {len(self._values)} entries.")

    def query(self, query_text: str, relevance_th: float = 0.12) -> str:
        try:
            if self._db is None:
                self._db = Chroma(
                    persist_directory=str(self._chromadb_dirpath),
                    embedding_function=self._embedder,
                    collection_name="code_rag",
                )

            results = self._db.similarity_search_with_relevance_scores(
                query_text, k=5, score_threshold=relevance_th
            )
            if len(results) == 0:
                return "Unable to find matching results"

            context_text = "\n\n - -\n\n".join([document.page_content for document, _ in results])
            return context_text
        except Exception as e:
            return f"Error: {str(e)}"


def create_code_rag_tool(api_keys: APIKeys):
    code_rag_tool = CodeRAGTool(api_keys["openai"], CHROMADB_DIR)
    if not CHROMADB_DIR.exists():
        logging.info("ChromaDB folder for code RAG tool not found, recreating database.")
        code_rag_tool.parse_files(RAG_DOCUMENT_DIR)
        code_rag_tool.save_to_chromadb()
    else:
        logging.info("ChromaDB folder for code RAG tool found, using cached values.")

    code_rag_tool_description = """
A tool that semantically searches for relevant functions to a given task. Input
a simple task description (e.g. "plot spatial co-occurence) and the function will
output a list of descriptions of functions from scanpy or squidpy that match the
task.
"""

    return StructuredTool.from_function(
        func=code_rag_tool.query,
        name="code_rag_tool",
        description=code_rag_tool_description,
    )
