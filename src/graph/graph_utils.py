# graph/graph_utils.py
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langchain.tools import StructuredTool
from queue import Queue
from typing import Any, Callable, List, Tuple

from agents.agent_utils import PythonREPLObj
from graph.state import AgentState
from logger import logger


def standardize_message_format(message: AIMessage) -> AIMessage:
    """
    Normalize AIMessage to ensure .tool_calls are present and content is readable,
    without throwing on non-text parts (e.g., images).
    """
    if isinstance(message.content, list):
        text_parts = []
        tool_calls = []
        other_parts = []

        for item in message.content:
            itype = item.get("type")
            if itype in ("text", "output_text"):
                text_parts.append(item.get("text", ""))
            elif itype in ("tool_use", "tool_call"):
                tool_call = {
                    "name": item.get("name"),
                    "args": item.get("input") or item.get("args") or {},
                    "id":   item.get("id"),
                    "type": "tool_call",
                }
                tool_calls.append(tool_call)
            else:
                # image_url, image, etc.
                other_parts.append(item)

        # If there are non-text parts, keep the original list so downstream can use them.
        if other_parts:
            return AIMessage(message.content, id=message.id, tool_calls=tool_calls)

        # Otherwise collapse to plain text for simplicity.
        return AIMessage("\n".join(text_parts).strip(), id=message.id, tool_calls=tool_calls)

    return message


def _stringify_content(content: Any) -> List[str]:
    """
    Turn content into printable lines for logging.
    Handles str or multimodal (list) content.
    """
    lines: List[str] = []
    if isinstance(content, str):
        lines.extend(content.splitlines())
    elif isinstance(content, list):
        for idx, part in enumerate(content, 1):
            ptype = part.get("type")
            if ptype in ("text", "output_text"):
                lines.append(f"[{idx}] (text) {part.get('text','')}")
            elif ptype in ("image_url", "image"):
                url = part.get("image_url")
                if isinstance(url, dict):
                    url = url.get("url")
                lines.append(f"[{idx}] (image) {str(url)[:80]}{'...' if url and len(str(url))>80 else ''}")
            elif ptype in ("tool_use", "tool_call"):
                lines.append(f"[{idx}] (tool_call) {part.get('name')}")
            else:
                lines.append(f"[{idx}] ({ptype}) {part}")
    else:
        lines.append(str(content))
    return lines


def log_message(message: BaseMessage):
    # Some message types may not have .name; default to None
    msg_type   = getattr(message, "type", type(message).__name__)
    msg_name   = getattr(message, "name", None)
    msg_id     = getattr(message, "id", None)
    content    = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", [])

    lines = [
        f"Message Info",
        f"Type: {msg_type}\n",
        f"Name: {msg_name}\n",
        f"ID:   {msg_id}\n"
    ]

    if content is not None:
        lines.append("Content:")
        lines += _stringify_content(content)

    if tool_calls:
        lines.append("ToolCalls:")
        for idx, tc in enumerate(tool_calls, 1):
            lines.append(f"  {idx}. {tc}")

    full_message = "\n".join(lines)
    logger.info(full_message)


def create_agent_node(
    agent_name: str, 
    agent_model: BaseChatModel, 
    prompt: str
) -> Callable[[AgentState], AgentState]:

    def agent_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        system_prompt = SystemMessage(prompt)
        response = agent_model.invoke([system_prompt] + messages)
        response = standardize_message_format(response)
        response.name = agent_name

        log_message(response)
        return {"messages": response}

    def data_analysis_agent_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        system_prompt = SystemMessage(prompt)
        response = agent_model.invoke([system_prompt] + messages)
        response = standardize_message_format(response)
        response.name = agent_name

        log_message(response)

        # hook output of data analysis agent to Python REPL log,
        # used for report generation.
        PythonREPLObj.add_text(f"[Agent]: {response}")

        return {"messages": response}

    return (data_analysis_agent_node
            if agent_name == "data_analysis_agent" else agent_node)


def create_tool_node(tools: List[StructuredTool]) -> Callable[[AgentState], AgentState]:
    tools_by_name = {tool.name: tool for tool in tools}

    def tool_node(state: AgentState) -> AgentState:
        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            message = ToolMessage(content=observation,
                                  tool_call_id=tool_call["id"])
            message.name = tool_call["name"]
            log_message(message)
            result.append(message)
        return {"messages": result}
    return tool_node


def create_agent_transition(tool_node_id: str, exit_node_id: str):
    def agent_transition(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]
        if getattr(last_message, "tool_calls", []):
            return tool_node_id
        return exit_node_id
    return agent_transition


def create_agent_invocation_tool(agent_node_id: str, agent_name: str,
                                 agent: CompiledStateGraph,
                                 state_queue: Queue):
    def agent_invocation_tool(prompt: str) -> str:
        logging.info(f"Invoking agent `{agent_node_id}`")
        final_state = agent.invoke({"messages": [HumanMessage(prompt)]})
        state_queue.put((agent_name, final_state))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{agent_node_id}_transfer_tool",
        description=f"Transfer control to {agent_name}",
    )
