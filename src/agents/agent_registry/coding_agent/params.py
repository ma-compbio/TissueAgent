from functools import partial
from pathlib import Path
from langchain_openai import ChatOpenAI

# Model constructor configuration
model_ctor = partial(ChatOpenAI, model="gpt-5", reasoning_effort="medium")
# reasoning_effort: "low", "medium", "high"
# note: reasoning tokens are counted in API cost

# Documentation file paths - mapping library names to their JSON files
doc_filepaths = {
    "scanpy": Path(__file__).resolve().parent / "docs/scanpy_docs.json",
    "squidpy": Path(__file__).resolve().parent / "docs/squidpy_docs.json",
    "liana": Path(__file__).resolve().parent / "docs/liana_docs.json",
    "hotspot": Path(__file__).resolve().parent / "docs/hotspot_docs.json",
}

# Tutorial directories - mapping library names to their tutorial directories
tutorial_directories = {
    "liana": Path(__file__).resolve().parent / "tutorials/liana-examples",
    "squidpy": Path(__file__).resolve().parent / "tutorials/squidpy_examples"
}