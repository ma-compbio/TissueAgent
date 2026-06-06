"""Model and parameter configuration for the coding agent."""
from pathlib import Path

from knowledge import DOCS_DIR
from models import model_ctor_for_role

# Coding agent uses the worker model; separate constructors for each phase.
retrieval_agent_model_ctor = model_ctor_for_role("worker")
execution_agent_model_ctor = model_ctor_for_role("worker")

doc_filepaths = {
    "scanpy": DOCS_DIR / "scanpy_docs.json",
    "squidpy": DOCS_DIR / "squidpy_docs.json",
    "liana": DOCS_DIR / "liana_docs.json",
}

tutorial_directories = {
    "liana": Path(__file__).resolve().parent / "tutorials/liana-examples",
    "squidpy": Path(__file__).resolve().parent / "tutorials/squidpy_examples",
}
