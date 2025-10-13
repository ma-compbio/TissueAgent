from typing import Tuple

from langchain.tools import StructuredTool

from config import DATA_DIR
from agents.agent_utils import PythonREPLObj
from pydantic import BaseModel
# from agents.data_analysis_agent.tools_impl.repl_funcs import REPLFuncs

PYTHON_REPL_EXEC_ID = "python_repl_exec_tool"
PYTHON_REPL_LOG_ID = "python_repl_log_tool"

python_repl_exec_description = f"""\
A Python REPL shell tool used to execute data analysis code.

IMPORTANT:
  - Use `print()` to see the value of variables and objects
  - Perform all operations in custom code in `DATA_DIR`. You can reference
    this directly in the code (e.g. `print(DATA_DIR) works`)
  - Variables and values persist across tool calls. Use the `{PYTHON_REPL_LOG_ID}`
    tool to get a log of all previous executions. DO NOT WRITE REDUNDANT CODE.
""".strip()

python_repl_log_description = f"""\
A Python REPL shell tool to retrieve all previous operations used, desigend to be
used in tandom with the `{PYTHON_REPL_EXEC_ID}` tool.
"""

def create_python_repl_tool() -> Tuple[StructuredTool, StructuredTool]:
    str_import_dict = {
        "ad" : "anndata",
        "np" : "numpy",
        "nx" : "networkx",
        "pd" : "pandas",
        "plt": "matplotlib.pyplot",
        "sc" : "scanpy",
        "sns": "seaborn",
        "sp" : "scipy",
        "sq" : "squidpy",
    }

    partial_import_dict = {
        "anndata": ["AnnData"],
        "pathlib": ["Path"],
        "typing": ["Dict", "Optional", "Sequence", "Union"],
    }

    import_code_block = "\n".join(
        [f"import {library} as {lib}"
            for lib, library in str_import_dict.items()] +
        [f"from {library} import {', '.join(imports)}"
            for library, imports in partial_import_dict.items()]
    )

    python_repl = PythonREPLObj
    # Ensure headless plotting works in non-GUI environments
    python_repl.run_command(
        "\n".join([
            "import matplotlib",
            "matplotlib.use('Agg', force=True)",
            "del matplotlib"
        ])
    )
    python_repl.run_command(
        "\n".join([
            "import warnings",
            "warnings.filterwarnings(\"ignore\", category=RuntimeWarning)",
            "del warnings"
        ])
    )

    python_repl.add_and_run_command(import_code_block)

    python_repl.add_and_run_command(f"DATA_DIR = Path(\"{DATA_DIR}\")")

    python_repl.run_command(
        "\n".join([
            "import os",
            "os.makedirs(DATA_DIR, exist_ok=True)",
            "os.chdir(DATA_DIR)",
            "del os",
        ])
    )

    # func_descriptions = ""
    # for category, funcs in REPLFuncs.items():
    #     func_descriptions += f"{category}\n"
    #     func_descriptions += "\n".join(
    #         [f"- {repl_func.name}:\n{textwrap.indent(repl_func.description, '      ')}"
    #                                    for repl_func in funcs]
    #     )

    python_repl_exec_tool = StructuredTool.from_function(
        func=python_repl.add_and_run_command,
        name=PYTHON_REPL_EXEC_ID,
        description=python_repl_exec_description
    )

    # --- log tool: NO ARGS + empty schema (prevents tuple enforcement) ---
    class _NoArgs(BaseModel):
        pass

    def _python_repl_log() -> str:
        # join safely in case any entries are not strings
        return "\n\n".join(map(str, python_repl.command_log))

    python_repl_log_tool = StructuredTool.from_function(
        func=lambda *args: "\n\n".join(python_repl.command_log),
        name=PYTHON_REPL_LOG_ID,
        description=python_repl_log_description,
        args_schema=_NoArgs, 
    )

    return python_repl_exec_tool, python_repl_log_tool
