from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from agents.reporter_agent.tools_impl.jupyternb_generator_tool import create_generate_jupyternb
from api_keys import APIKeys

### computed at load time for render_conversation_history in app_utils
ReporterToolNames = ["file_retriever_tool", "jupyternb_generator_tool"]


def create_reporter_tools(api_keys: APIKeys):
    jupyternb_generator_tool = StructuredTool.from_function(
        func=create_generate_jupyternb(api_keys),
        name="jupyternb_generator_tool",
        description="generates a Jupyter notebook that summarizes all executed commands"
    )

    return [
        jupyternb_generator_tool,
        file_retriever_tool,
    ]
