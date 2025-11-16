import logging
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from logger import logger


def standardize_message_format(
    message: AIMessage
) -> AIMessage:
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
                other_parts.append(item)

        if other_parts:
            return AIMessage(message.content, id=message.id, tool_calls=tool_calls)
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
    agent_node_id: str,
    agent_model: BaseChatModel,
    prompt: str,
    tool_node_id: str,
    exit_node_id: Optional[str] = None,
    exit_node_id_fn: Optional[Callable[[AIMessage, MessagesState], str]] = None,
    state_update_fn: Optional[Callable[[AIMessage, MessagesState], Optional[Dict[str, Any]]]] = None,
) -> Callable[[MessagesState], Command]:
    
    def agent_node(state: MessagesState) -> Command:
        messages = state["messages"]
        system_prompt = SystemMessage(prompt)
        response = agent_model.invoke([system_prompt] + messages)
        response = standardize_message_format(response)
        response.name = agent_node_id
        log_message(response)

        extra_update: Dict[str, Any] = {}
        if state_update_fn:
            maybe_update = state_update_fn(response, state) or {}
            if maybe_update:
                extra_update.update(maybe_update)

        next_node = tool_node_id if getattr(response, "tool_calls", []) else None
        if not next_node:
            if exit_node_id:
                next_node = exit_node_id
            elif exit_node_id_fn:
                next_node = exit_node_id_fn(response, state)
            else:
                next_node = None

        update_payload: Dict[str, Any] = {"messages": [response]}
        if extra_update:
            update_payload.update(extra_update)
        return Command(goto=next_node, update=update_payload)
    return agent_node

def create_tool_node(
    tools: List[StructuredTool]
) -> Callable[[MessagesState], MessagesState]:
    tools_by_name = {tool.name: tool for tool in tools}

    def tool_node(state: MessagesState) -> MessagesState:
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

def create_agent_invocation_tool(
    agent_node_id: str,
    agent_name: str,
    agent: CompiledStateGraph,
    state_queue: Queue,
    supports_pdf: bool = False
):
    if supports_pdf:
        def agent_invocation_tool(prompt: str, pdf_file_ids: str = "") -> str:
            """
            Invoke agent with optional PDF file IDs.

            Args:
                prompt: Task instructions for the agent
                pdf_file_ids: Comma-separated list of OpenAI file IDs (e.g. "file-abc123,file-def456")

            Returns:
                Agent's response
            """
            logging.info(f"Invoking PDF-capable agent `{agent_node_id}`")

            # Build multimodal content if PDFs provided
            content = [{"type": "text", "text": prompt}]

            if pdf_file_ids and pdf_file_ids.strip():
                file_ids = [fid.strip() for fid in pdf_file_ids.split(",") if fid.strip()]
                logging.info(f"Attaching {len(file_ids)} PDF file(s) to agent invocation")
                for file_id in file_ids:
                    content.append({
                        "type": "file",
                        "file": {"file_id": file_id}
                    })

            final_state = agent.invoke({"messages": [HumanMessage(content=content)]})
            state_queue.put((agent_name, final_state))
            logging.info(f"Finished invoking PDF-capable agent `{agent_node_id}`")
            return final_state["messages"][-1].content
    else:
        def agent_invocation_tool(prompt: str) -> str:
            logging.info(f"Invoking agent `{agent_node_id}`")
            final_state = agent.invoke({"messages": [HumanMessage(prompt)]})
            state_queue.put((agent_name, final_state))
            logging.info(f"Finished invoking agent `{agent_node_id}`")
            return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{agent_node_id}_transfer_tool",
        description=f"Transfer control to {agent_name}",
    )
