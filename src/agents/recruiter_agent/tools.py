from langchain.tools import StructuredTool

from agents.agent_utils import file_retriever_tool
# from agents.planner_agent.tools_impl.jupyternb_generator_tool import create_generate_jupyternb
from api_keys import APIKeys

### computed at load time for render_conversation_history in app_utils
PlannerToolNames = ["file_retriever_tool"]

def create_recruiter_tools(api_keys: APIKeys):
    return [
        file_retriever_tool,
    ]

