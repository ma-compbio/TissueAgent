"""Streamlit helper utilities for rendering agent conversations."""

from __future__ import annotations
import json
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
import streamlit as st
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState 
from agents.manager_agent.tools import ManagerToolNames
 

# ---------------------------------------------------------------------------
# Agent identity metadata
# ---------------------------------------------------------------------------

AvatarLabel = Tuple[str, str]

MAIN_AGENT_BADGES: Dict[str, AvatarLabel] = {
    "planner_agent": ("🧠", "Planner"),
    "recruiter_agent": ("🧑\u200d🤝\u200d🧑", "Recruiter"),
    "manager_agent": ("🧭", "Manager"),
    "evaluator_agent": ("🧪", "Evaluator"),
    "reporter_agent": ("📝", "Reporter"),
}

SUBAGENT_BADGES: Dict[str, str] = {
    "Coding Agent": "💻",
    "Searcher Agent": "🔍",
    "Single Cell Agent": "🧫",
}

DEFAULT_AGENT_AVATAR = "🤖"
DEFAULT_AGENT_LABEL = "Assistant"
SUBAGENT_DEFAULT_AVATAR = "🧩"
USER_AVATAR = "🧑\u200d🔬"


def _lookup_agent_badge(agent_name: Optional[str]) -> AvatarLabel:
    """Return the avatar and label for the given agent name."""

    if not agent_name:
        return DEFAULT_AGENT_AVATAR, DEFAULT_AGENT_LABEL
    if agent_name in MAIN_AGENT_BADGES:
        return MAIN_AGENT_BADGES[agent_name]
    friendly = agent_name.replace("_agent", "").replace("_", " ").title()
    return DEFAULT_AGENT_AVATAR, friendly or DEFAULT_AGENT_LABEL


# ---------------------------------------------------------------------------
# LLM selector metadata (used by the Streamlit settings sidebar)
# ---------------------------------------------------------------------------

LLMOptions = {
    "OpenAI GPT-5 (default)": (ChatOpenAI, "gpt-5"),
    "OpenAI GPT-5-mini": (ChatOpenAI, "gpt-5-mini"),
    "OpenAI GPT-4o": (ChatOpenAI, "gpt-4o"),
    "OpenAI GPT-4.1": (ChatOpenAI, "gpt-4.1"),
    "OpenAI o4-mini": (ChatOpenAI, "o4-mini"),
    "Anthropic Claude Sonnet 4": (ChatAnthropic, "claude-sonnet-4-20250514"),
    "Anthropic Claude Opus 4": (ChatAnthropic, "claude-opus-4-20250514"),
 }
 
# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def _flatten_text_chunks(chunks: Sequence[Any]) -> str:
    """Return human-readable text extracted from LangChain content chunks."""

    texts: List[str] = []
    for part in chunks:
        if isinstance(part, dict):
            if part.get("type") in {"text", "output_text"}:
                texts.append(part.get("text", ""))
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(t for t in texts if t).strip()


def _stringify_chat_content(content: Any) -> str:
    """Convert message content into a plain-text representation."""

    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return _flatten_text_chunks(content)
    if content is None:
        return ""
    return str(content)


def _extract_tool_inputs(
    tool_calls: Optional[Iterable[Mapping[str, Any]]],
    sink: MutableMapping[str, str],
    ) -> List[str]:
    """Collect tool inputs keyed by call id and return a list of tool names."""

    names: List[str] = []
    if not tool_calls:
        return names

    for call in tool_calls:
        name = str(call.get("name", ""))
        tool_id = str(call.get("id", "")) or None
        raw_args = call.get("args", {})

        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = raw_args
        else:
            parsed_args = raw_args

        if tool_id:
            sink[tool_id] = json.dumps(parsed_args, indent=2, ensure_ascii=False)
        names.append(name)
    return names

def _split_route_and_body(content: str) -> Tuple[Optional[str], str]:
    """Separate the optional ROUTE header from the remaining message body."""

    lines = [line for line in content.strip().splitlines() if line.strip()]
    if lines and lines[0].upper().startswith("ROUTE:"):
        route_caption = lines[0].split(":", 1)[-1].strip()
        body = "\n".join(lines[1:]).strip()
        return route_caption or None, body
    return None, content.strip()

def _markdown_with_linebreaks(text: str) -> None:
    """Render Markdown text while preserving single newlines as line breaks."""

    if not text:
        st.markdown("")
        return

    formatted = text.replace("\n", "\n\n") if "\n" in text else text
    st.markdown(formatted)

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_subagent_history(messages: Sequence[BaseMessage]) -> None:
    """Render the message transcript for a recruited sub-agent."""

    tool_input_map: Dict[str, str] = {}
 
    for message in messages:

        content = _stringify_chat_content(message.content)
 
        if isinstance(message, AIMessage):
            agent_name = message.name or "Agent"
            tool_names = _extract_tool_inputs(message.tool_calls, tool_input_map)

            if tool_names:
                tool_list = ", ".join(tool_names)
                _markdown_with_linebreaks(f"**[{agent_name}]** → `{tool_list}`")
            elif content:
                _markdown_with_linebreaks(f"**[{agent_name}]**:\n\n{content}")
 
        elif isinstance(message, ToolMessage):
            tool_call_id = getattr(message, "tool_call_id", None)
            tool_input = tool_input_map.get(tool_call_id, "No captured input")
            tool_output = _stringify_chat_content(message.content)

            with st.expander(f"Tool Call · {message.name}", expanded=False):
                st.write("**Input**")
                st.code(tool_input or "<empty>", language="json")
                st.write("**Output**")
                st.code(tool_output or "<empty>")

 
def _render_manager_tool_message(message: ToolMessage) -> None:
    """Render a manager tool invocation with an expandable output block."""

    avatar, role_label = _lookup_agent_badge("manager_agent")
    with st.chat_message("assistant", avatar=avatar):
        _markdown_with_linebreaks(f"**{role_label} Tool:** `{message.name}`")
        tool_output = _stringify_chat_content(message.content)
        with st.expander("Output", expanded=False):
            st.code(tool_output or "<empty>")


def _render_subagent_tool_message(
    message: ToolMessage,
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
) -> None:
    """Render the transcript for a tool executed by a recruited sub-agent."""
    agent_name, agent_state = subagent_state.get(message.id, ("Unknown Agent", None))
    avatar = SUBAGENT_BADGES.get(agent_name, SUBAGENT_DEFAULT_AVATAR)

    with st.chat_message("assistant", avatar=avatar):
        _markdown_with_linebreaks(f"**{agent_name}**")

        if isinstance(agent_state, Mapping) and agent_state.get("messages"):
            render_subagent_history(agent_state["messages"])
        else:
            st.warning(f"{agent_name}: {agent_state}", icon="⚠️")

def render_conversation_history(
    messages: Sequence[BaseMessage],
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
    *,
    enable_debug: bool = True,
) -> None:
    """Render the full chat transcript for the Streamlit UI."""
    for message in messages:
        content = _stringify_chat_content(message.content)

        if isinstance(message, HumanMessage):

            with st.chat_message("user", avatar=USER_AVATAR):
                _markdown_with_linebreaks(content or "")
            continue
 
        if isinstance(message, AIMessage):
            if not content:
                continue
            avatar, role_label = _lookup_agent_badge(message.name)
            with st.chat_message("assistant", avatar=avatar):
                _markdown_with_linebreaks(f"**{role_label}**")
                route_caption, body = _split_route_and_body(content)
                _markdown_with_linebreaks(body)
                if route_caption:
                    st.caption(f"Route → {route_caption}")
            continue

        if isinstance(message, ToolMessage) and enable_debug:
            if message.name in ManagerToolNames:
                _render_manager_tool_message(message)
            else:
                _render_subagent_tool_message(message, subagent_state)
 
 


# import json
# import streamlit as st
# from typing import Dict, List, Tuple

# from langgraph.graph import MessagesState
# from langchain_anthropic import ChatAnthropic
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
# from langchain_openai import ChatOpenAI

# from agents.manager_agent.tools import ManagerToolNames

# LLMOptions = {
#     "OpenAI GPT-5 (default)":            (ChatOpenAI, "gpt-5"),
#     "OpenAI GPT-5-mini":            (ChatOpenAI, "gpt-5-mini"),
#     "OpenAI GPT-4o":   (ChatOpenAI, "gpt-4o"),
#     "OpenAI GPT-4.1":            (ChatOpenAI, "gpt-4.1"),
#     "OpenAI o4-mini":            (ChatOpenAI, "o4-mini"),
#     "Anthropic Claude Sonnet 4": (ChatAnthropic, "claude-sonnet-4-20250514"),
#     "Anthropic Claude Opus 4":   (ChatAnthropic, "claude-opus-4-20250514"),
# }

# def render_subagent_history(messages: List[BaseMessage]):
#     tool_input_map = {}

#     for message in messages:
#         content = message.content

#         if isinstance(message, AIMessage):
#             agent_name = message.name
#             if tool_calls := message.tool_calls:
#                 tool_names = []
#                 for tool_call in tool_calls:
#                     try:
#                         arguments_json = tool_call.get('args', '{}')
#                         tool_input = arguments_json 
#                         tool_call_id = tool_call.get("id")
#                         if tool_call_id:
#                             tool_input_map[tool_call_id] = tool_input
#                     except json.JSONDecodeError:
#                         tool_input_map[tool_call.get("id", "unknown")] = "Error decoding tool input."

#                     tool_names.append(tool_call["name"])

#                 output_str = ", ".join(tool_names)
#                 st.text(f"**[{agent_name}]**: {output_str}")
#             else:
#                 agent_name = message.name
#                 st.text(f"**[{agent_name}]**: {content}")

#         elif isinstance(message, ToolMessage):
#             tool_output = message.content
#             tool_call_id = getattr(message, "tool_call_id", None)
#             tool_input = tool_input_map.get(tool_call_id, "No matching tool input found")

#             with st.expander(f"**Tool Call**: {message.name}", expanded=False):
#                 st.code(tool_input or "No tool input available", language="python")
#                 st.write("**Tool Output:**")
#                 st.code(tool_output)

# def render_conversation_history(messages: List[BaseMessage],
#                                 subagent_state: Dict[str, Tuple[str, MessagesState]],
#                                 enable_debug: bool=True):
#     for message in messages:
#         content = message.content
#         if isinstance(message, HumanMessage):
#             with st.chat_message("user"):
#                 st.text(content)
#         elif isinstance(message, AIMessage):
#             # if content := message.content:
#             #     with st.chat_message("assistant"):
#             #         st.text(content)
#             if content := message.content:
#                 with st.chat_message("assistant"): 
#                     # Remove "ROUTE:" header if present
#                     # 1. Split the content into lines.
#                     lines = content.strip().split('\n')
                    
#                     # 2. Check if the first line starts with "ROUTE:".
#                     if lines and lines[0].upper().startswith("ROUTE:"):
#                         # Remove the first line (the ROUTE)
#                         display_content = '\n'.join(lines[1:]).strip()
#                     else:
#                         # Use the original content if no ROUTE header is found
#                         display_content = content.strip()
#                     # ═══════════════════════════════
                    
#                     # 3. Use st.text() to display the remaining content, preserving newlines.
#                     st.text(display_content)
#         elif isinstance(message, ToolMessage) and enable_debug:
#             if message.name in ManagerToolNames:
#                 tool_output = message.content
#                 with st.expander(f"Tool Call: {message.name}", expanded=False):
#                     st.code("No tool input available", language="python")
#                     st.write("**Tool Output:**")
#                     st.code(tool_output)

#             else:
#                 agent_name, agent_state = subagent_state[message.id]
#                 if not isinstance(agent_state, str) and agent_state:
#                     with st.expander(f"Subagent Invocation: {agent_name}"):
#                         render_subagent_history(agent_state["messages"])
#                 else:
#                     st.warning(f"{agent_name}: {agent_state}", icon = "⚠️")


