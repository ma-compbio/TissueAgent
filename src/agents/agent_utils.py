import ast
import multiprocessing
import re
import sys

from io import StringIO
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Dict, Optional, Tuple

from config import DATA_DIR

def format_agent_id_descriptions(agent_id_descriptions: Dict[str, str]):
    return "\n".join([
        f" - {id}: {description}" for id, description in agent_id_descriptions.items()
    ])


def extract_block(
    pattern: str,
    text: str
) -> Optional[str]:
    matches = list(
        re.finditer(r'(?is)<' + pattern + r'(?:\s[^>]*)?>(.*?)</' + pattern + '>', text)
    )
    if len(matches) != 1:
        return None
    block = matches[0].group(1).strip()
    return block or None


### file retriever tool

def file_retriever() -> str:
    filenames = [str(path)
                 for path in DATA_DIR.rglob('*') if path.is_file()]
    return "\n".join([
      "Files are stored in the DATA_DIR subdirectory.",
      f"DATA_DIR: '{DATA_DIR}'",
      f"File Paths: {filenames}",
    ])

file_retriever_tool = StructuredTool.from_function(
    func=file_retriever,
    name="file_retriever_tool",
    description="Returns a list of file names in the data directory.",
)

### Python REPL tool

class PythonREPL(BaseModel):
    globals: Optional[Dict] = Field(default_factory=dict, alias="_globals")
    locals: Optional[Dict] = None

    @staticmethod
    def sanitize_input(query: str) -> str:
        query = re.sub(r"^(\s|`)*(?i:python)?\s*", "", query)
        query = re.sub(r"(\s|`)*$", "", query)
        return query

    @classmethod
    def worker(cls, command: str, globals: dict, locals: dict, queue: multiprocessing.Queue):
        try:
            cleaned = cls.sanitize_input(command)
            tree = ast.parse(cleaned, mode="exec")

            if tree.body and isinstance(tree.body[-1], ast.Expr):
                expr_node = tree.body[-1].value
                print_call = ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="print", ctx=ast.Load()),
                        args=[expr_node],
                        keywords=[],
                    )
                )
                tree.body[-1] = print_call
            ast.fix_missing_locations(tree)


            code_obj = compile(tree, "<repl>", "exec")

            mystdout = StringIO()
            old_stdout = sys.stdout
            sys.stdout = mystdout

            try:
                exec(code_obj, globals, locals)
            finally:
                sys.stdout = old_stdout

            out = mystdout.getvalue()
        except BaseException as e:
            out = repr(e)
        finally:
            queue.put(out)

    def run(self, command: str, timeout: Optional[int]=None) -> str:
        queue: multiprocessing.Queue = multiprocessing.Queue()

        if timeout is not None:
            p = multiprocessing.Process(
                target=self.worker, args=(command, self.globals, self.locals, queue)
            )

            p.start()
            p.join(timeout)

            if p.is_alive():
                p.terminate()
                return "Execution timed out"
        else:
            self.worker(command, self.globals, self.locals, queue)
        return queue.get()

class PythonREPLWrapper:
    def __init__(self):
        self._python_repl = PythonREPL()
        self._run_cnt = 1
        self._events = []

    def _clear(self):
        self._python_repl = PythonREPL()
        self._run_cnt = 1
        self._events = []

    def run_command(self, command: str):
        return self._python_repl.run(command)

    def add_and_run_command(self, command: str):
        output = self._python_repl.run(command)
        idx = self._run_cnt
        self._run_cnt += 1
        self._events.append((f"# In[{idx}]:\n{command}\n\n"
                             f"# Out[{idx}]:\n{output}", True))
        return output

    def add_text(self, text: str):
        self._events.append((f"# Text: {text}", False))
    
    @property
    def command_log(self):
        return [entry for (entry, command_state) in self._events if command_state]

    @property
    def event_list(self):
        return self._events

PythonREPLObj = PythonREPLWrapper()
