"""Model and parameter configuration for the coding agent."""

from knowledge import DOCS_DIR
from models import model_ctor_for_role

coding_agent_model_ctor = model_ctor_for_role("worker")

doc_filepaths = {
    "scanpy": DOCS_DIR / "scanpy_docs.json",
    "squidpy": DOCS_DIR / "squidpy_docs.json",
    "liana": DOCS_DIR / "liana_docs.json",
}
