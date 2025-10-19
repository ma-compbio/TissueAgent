import json
import streamlit as st
from typing import Dict, List, Tuple

from langgraph.graph import MessagesState
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from agents.manager_agent.tools import ManagerToolNames

LLMOptions = {
    "OpenAI GPT-5 (default)":            (ChatOpenAI, "gpt-5"),
    "OpenAI GPT-5-mini":            (ChatOpenAI, "gpt-5-mini"),
    "OpenAI GPT-4o":   (ChatOpenAI, "gpt-4o"),
    "OpenAI GPT-4.1":            (ChatOpenAI, "gpt-4.1"),
    "OpenAI o4-mini":            (ChatOpenAI, "o4-mini"),
    "Anthropic Claude Sonnet 4": (ChatAnthropic, "claude-sonnet-4-20250514"),
    "Anthropic Claude Opus 4":   (ChatAnthropic, "claude-opus-4-20250514"),
}

def render_subagent_history(messages: List[BaseMessage]):
    tool_input_map = {}

    for message in messages:
        content = message.content

        if isinstance(message, AIMessage):
            agent_name = message.name
            if tool_calls := message.tool_calls:
                tool_names = []
                for tool_call in tool_calls:
                    try:
                        arguments_json = tool_call.get('args', '{}')
                        tool_input = arguments_json 
                        tool_call_id = tool_call.get("id")
                        if tool_call_id:
                            tool_input_map[tool_call_id] = tool_input
                    except json.JSONDecodeError:
                        tool_input_map[tool_call.get("id", "unknown")] = "Error decoding tool input."

                    tool_names.append(tool_call["name"])

                output_str = ", ".join(tool_names)
                st.text(f"**[{agent_name}]**: {output_str}")
            else:
                agent_name = message.name
                st.text(f"**[{agent_name}]**: {content}")

        elif isinstance(message, ToolMessage):
            tool_output = message.content
            tool_call_id = getattr(message, "tool_call_id", None)
            tool_input = tool_input_map.get(tool_call_id, "No matching tool input found")

            with st.expander(f"**Tool Call**: {message.name}", expanded=False):
                st.code(tool_input or "No tool input available", language="python")
                st.write("**Tool Output:**")
                st.code(tool_output)

def render_conversation_history(messages: List[BaseMessage],
                                subagent_state: Dict[str, Tuple[str, MessagesState]],
                                enable_debug: bool=True):
    for message in messages:
        content = message.content
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.text(content)
        elif isinstance(message, AIMessage):
            # if content := message.content:
            #     with st.chat_message("assistant"):
            #         st.text(content)
            if content := message.content:
                with st.chat_message("assistant"): 
                    # Remove "ROUTE:" header if present
                    # 1. Split the content into lines.
                    lines = content.strip().split('\n')
                    
                    # 2. Check if the first line starts with "ROUTE:".
                    if lines and lines[0].upper().startswith("ROUTE:"):
                        # Remove the first line (the ROUTE)
                        display_content = '\n'.join(lines[1:]).strip()
                    else:
                        # Use the original content if no ROUTE header is found
                        display_content = content.strip()
                    # ═══════════════════════════════
                    
                    # 3. Use st.text() to display the remaining content, preserving newlines.
                    st.text(display_content)
        elif isinstance(message, ToolMessage) and enable_debug:
            if message.name in ManagerToolNames:
                tool_output = message.content
                with st.expander(f"Tool Call: {message.name}", expanded=False):
                    st.code("No tool input available", language="python")
                    st.write("**Tool Output:**")
                    st.code(tool_output)

            else:
                agent_name, agent_state = subagent_state[message.id]
                if not isinstance(agent_state, str) and agent_state:
                    with st.expander(f"Subagent Invocation: {agent_name}"):
                        render_subagent_history(agent_state["messages"])
                else:
                    st.warning(f"{agent_name}: {agent_state}", icon = "⚠️")


