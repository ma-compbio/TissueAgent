from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
from api_keys import APIKeys

### computed at load time for render_conversation_history in app_utils
ManagerToolNames = ["file_retriever_tool"]


def create_manager_tools(api_keys: APIKeys):
    return [
        file_retriever_tool,
    ]
