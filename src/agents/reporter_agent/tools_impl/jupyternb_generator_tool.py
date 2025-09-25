import nbformat as nbf
import nbformat.v4 as nbfv4

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from pathlib import Path
from typing import Optional, Union

from agents.agent_utils import PythonREPL, PythonREPLObj
from api_keys import APIKeys
from config import DATA_DIR


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

def create_generate_jupyternb(api_keys: APIKeys, model: str="o4-mini"):

    def generate_jupyternb(filename: Optional[Union[Path, str]]=None) -> str:
        event_list = PythonREPLObj.event_list

        merged_event_list = []
        for (entry, state) in event_list:
            if not merged_event_list or state != merged_event_list[-1][1]:
                merged_event_list.append([entry, state])
            else:
                merged_event_list[-1][0] += f"\n\n{entry}"

        nb = nbfv4.new_notebook()
        model = ChatOpenAI(api_key=api_keys["openai"])
        for (entry, state) in merged_event_list:
            if not state:
                continue

            code_message = HumanMessage(content=f"{generate_jupyternb_code_prompt}\n\n{entry}")
            code_output = model.invoke([code_message]).content

            text_message = HumanMessage(content=f"{generate_jupyternb_text_prompt}\n\n{entry}")
            text_output = model.invoke([text_message]).content

            text_cell = nbfv4.new_markdown_cell(text_output)
            code_cell = nbfv4.new_code_cell(PythonREPL.sanitize_input(code_output))
            nb.cells.append(text_cell)
            nb.cells.append(code_cell)

        if not filename:
            filename = DATA_DIR / "report.ipynb"
        try:
            nbf.write(nb, filename)
        except Exception as e:
            return f"Error: notebook export failed with error `{e}`"
        return f"Success: notebook successfully exported to {filename}"

    return generate_jupyternb
