"""Tools available to the Recruiter agent."""

from agents.agent_utils import file_retriever_tool

# from agents.planner_agent.tools_impl.jupyternb_generator_tool import create_generate_jupyternb
from api_keys import APIKeys

### computed at load time for render_conversation_history in app_utils
PlannerToolNames = ["file_retriever_tool"]


def create_recruiter_tools(api_keys: APIKeys):
    """Return the list of tools available to the Recruiter agent.

    Args:
        api_keys: Application API keys (kept for signature symmetry).

    Returns:
        List of LangChain tools for the recruiter.
    """
    return [
        file_retriever_tool,
    ]
