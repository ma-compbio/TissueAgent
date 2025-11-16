import nbformat as nbf
import nbformat.v4 as nbfv4
from pathlib import Path
from typing import Optional, Union

from langchain.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import DATA_DIR, NOTEBOOK_DIR


generate_jupyternb_text_prompt = """\
The following snippet of code is a Jupyter notebook cell. Given the context that
follows, generate a markdown-formatted description that will be put before the
code cell. If the code has errors, make a note of this in the description. DO
NOT INCLUDE CODE IN YOUR RESPONSE. KEEP YOUR DESCRIPTION SHORT. ONLY INCLUDE
HIGH-LEVEL IDEAS.

### Examples
  - Plot a UMAP of gene expressions from Lohoff et. al colored by cell type.
  - Spatial coexpression analysis between mesodermal cells.
""".strip()

generate_jupyternb_code_prompt = """\
The following text consists of multiple snippets of Python code and their
corresponding outputs. Consolidate all of them into a single code fragment
by removing redundant code and removing code that resulted in errors. Print all
images and figures as figures in Jupyter notebook format. DO NOT SAVE IMAGES TO
FILES. ONLY RESPOND WITH CODE. DO NOT INCLUDE THE OUTPUT.
""".strip()

def _normalize_filename(filename: Optional[Union[Path, str]]) -> Path:
    if filename is None:
        target = NOTEBOOK_DIR / "report.ipynb"
    else:
        target = Path(filename)

    if not target.is_absolute():
        target = (DATA_DIR / target).resolve()
    else:
        target = target.resolve()

    try:
        target.relative_to(DATA_DIR)
    except ValueError as exc:
        raise RuntimeError(
            f"Notebook path '{target}' must be inside DATA_DIR '{DATA_DIR}'."
        ) from exc

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to create parent directory for notebook '{target}': {exc}"
        ) from exc

    return target

def generate_jupyternb(filename: Optional[Union[Path, str]]=None) -> str:
    # Since we removed the execution history tracking, create a basic empty notebook
    nb = nbfv4.new_notebook()
    
    # Add a simple markdown cell explaining the situation
    markdown_cell = nbfv4.new_markdown_cell(
        "# Analysis Session\n\n"
        "This notebook was generated from a coding session. "
        "Execution history tracking has been simplified, so this notebook contains only basic structure."
    )
    nb.cells.append(markdown_cell)
    
    # Add a simple code cell
    code_cell = nbfv4.new_code_cell(
        "# Add your analysis code here\n"
        "print('Analysis session started')"
    )
    nb.cells.append(code_cell)

    # if not filename:
    #     filename = DATA_DIR / "report.ipynb"
    try:
        # nbf.write(nb, filename)
        filename_path = _normalize_filename(filename)
    except Exception as exc:
        return f"Error: {exc}"
    try:
        nbf.write(nb, filename_path)
    except Exception as e:
        return f"Error: notebook export failed with error `{e}`"
    return f"Success: notebook successfully exported to {filename_path}"

jupyternb_generator_tool = StructuredTool.from_function(
    func=generate_jupyternb,
    name="jupyternb_generator_tool",
    description="generates a Jupyter notebook that summarizes all executed commands"
)