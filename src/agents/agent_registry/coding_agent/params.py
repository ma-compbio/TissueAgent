"""Model and parameter configuration for the coding agent."""
from functools import partial
from pathlib import Path
from langchain_openai import ChatOpenAI

# reasoning_effort: "low", "medium", "high"
retrieval_agent_model_ctor = partial(ChatOpenAI, model="gpt-5", reasoning_effort = "low")
execution_agent_model_ctor = partial(ChatOpenAI, model="gpt-5")

doc_filepaths = {
    "scanpy": Path(__file__).resolve().parent / "docs/scanpy_docs.json",
    "squidpy": Path(__file__).resolve().parent / "docs/squidpy_docs.json",
    "liana": Path(__file__).resolve().parent / "docs/liana_docs.json",
}

tutorial_directories = {
    "liana": Path(__file__).resolve().parent / "tutorials/liana-examples",
    "squidpy": Path(__file__).resolve().parent / "tutorials/squidpy_examples",
}
