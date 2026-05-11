"""Model and parameter configuration for the coding agent."""
from pathlib import Path

from models import model_ctor_for_role

# Coding agent is a worker sub-agent; resolves the worker model at call time.
model_ctor = model_ctor_for_role("worker")

# Documentation file paths - mapping library names to their JSON files
doc_filepaths = {
    "scanpy": Path(__file__).resolve().parent / "docs/scanpy_docs.json",
    "squidpy": Path(__file__).resolve().parent / "docs/squidpy_docs.json",
    "liana": Path(__file__).resolve().parent / "docs/liana_docs.json",
}

# Tutorial directories - mapping library names to their tutorial directories
tutorial_directories = {
    "liana": Path(__file__).resolve().parent / "tutorials/liana-examples",
    "squidpy": Path(__file__).resolve().parent / "tutorials/squidpy_examples",
}
