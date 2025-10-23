import re
from langchain.tools import StructuredTool
from typing import Dict, Optional

from config import DATA_DIR

def format_agent_id_descriptions(agent_id_descriptions: Dict[str, str]):
    return "\n".join([
        f" - {id}: {description}" for id, description in agent_id_descriptions.items()
    ])


def extract_block(
    pattern: str,
    text: str
) -> Optional[str]:
    complete_matches = list(
        re.finditer(r'(?is)<' + pattern + r'(?:\s[^>]*)?>(.*?)</' + pattern + '>', text)
    )
    if len(complete_matches) == 1:
        block = complete_matches[0].group(1).strip()
        return block or None
    
    if len(complete_matches) == 0:
        open_matches = list(
            re.finditer(r'(?is)<' + pattern + r'(?:\s[^>]*)?>(.*?)$', text)
        )
        if len(open_matches) == 1:
            block = open_matches[0].group(1).strip()
            return block or None
    return None


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