"""Tools available to the Recruiter agent."""

from typing import List

from langchain.tools import StructuredTool

from agents.agent_utils import file_read_tools
from agents.recruiter_agent.tools_impl.read_skill_tool import read_skill_tool

### computed at load time for render_conversation_history in app_utils
RecruiterToolNames = ["glob", "grep", "read", "read_skill"]

RecruiterTools: List[StructuredTool] = [
    *file_read_tools,
    read_skill_tool,
]
