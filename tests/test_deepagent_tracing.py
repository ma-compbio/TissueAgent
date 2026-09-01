"""Token-streaming behavior for the canonical DeepAgent coding agent."""

from __future__ import annotations

import asyncio
import importlib
import os
from queue import Empty, Queue
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import ensure_config, var_child_runnable_config


os.environ.setdefault("OPENAI_API_KEY", "dummy")


def _tracing_module():
    try:
        return importlib.import_module("agents.agent_registry.coding_agent.tracing")
    except ModuleNotFoundError:
        pytest.fail("DeepAgent tracing adapter is not implemented")


class FakeAgent:
    """Compiled-agent stand-in that yields predefined v2 stream parts."""

    def __init__(self, parts: list[dict]) -> None:
        """Store the stream parts and capture the eventual call arguments."""
        self.parts = parts
        self.call: dict | None = None

    def stream(self, inputs: dict, **kwargs):
        """Yield the configured stream parts."""
        self.call = {"inputs": inputs, **kwargs}
        yield from self.parts


def _chunk(content, message_id: str | None = "message-1") -> SimpleNamespace:
    return SimpleNamespace(content=content, id=message_id)


def test_stream_adapter_filters_non_visible_chunks_and_returns_root_state() -> None:
    """Only visible text is emitted and the latest root values state is returned."""
    tracing = _tracing_module()
    completed = AIMessage(content="Visible text", id="message-1")
    root_state = {"messages": [completed], "todos": []}
    agent = FakeAgent(
        [
            {
                "type": "messages",
                "ns": (),
                "data": (
                    _chunk(
                        [
                            {"type": "text", "text": "Visible "},
                            {"type": "reasoning", "reasoning": "secret"},
                            {"type": "tool_call_chunk", "args": '{"path":'},
                        ]
                    ),
                    {"langgraph_node": "model"},
                ),
            },
            {
                "type": "messages",
                "ns": (),
                "data": (_chunk("text"), {"langgraph_node": "model"}),
            },
            {
                "type": "updates",
                "ns": (),
                "data": {"model": {"messages": [completed]}},
            },
            {"type": "values", "ns": (), "data": root_state},
        ]
    )
    tokens: list[tuple[str, str, str]] = []
    messages: list[tuple[object, str | None, str]] = []

    result = tracing.consume_deep_agent_stream(
        agent,
        {"messages": []},
        {"recursion_limit": 25},
        on_token=lambda stream_id, source, text: tokens.append((stream_id, source, text)),
        on_message=lambda message, stream_id, source: messages.append(
            (message, stream_id, source)
        ),
    )

    assert result is root_state
    assert [token[2] for token in tokens] == ["Visible ", "text"]
    assert "secret" not in "".join(token[2] for token in tokens)
    assert messages == [(completed, tokens[0][0], "Coding Agent")]
    assert agent.call == {
        "inputs": {"messages": []},
        "config": {"recursion_limit": 25, "configurable": {}},
        "stream_mode": ["messages", "updates", "values"],
        "subgraphs": True,
        "version": "v2",
    }


def test_stream_adapter_separates_nested_streams_and_deduplicates_messages() -> None:
    """Parallel namespaces cannot share drafts and completed messages emit once."""
    tracing = _tracing_module()
    root = AIMessage(content="root", id="same-id")
    nested = AIMessage(content="nested", id="same-id")
    tool = ToolMessage(content="done", id="tool-1", tool_call_id="call-1")
    nested_ns = ("tools:run-1", "researcher:run-2")
    agent = FakeAgent(
        [
            {
                "type": "messages",
                "ns": (),
                "data": (_chunk("root", "same-id"), {}),
            },
            {
                "type": "messages",
                "ns": nested_ns,
                "data": (_chunk("nested", "same-id"), {}),
            },
            {
                "type": "updates",
                "ns": (),
                "data": {"model": {"messages": [root]}},
            },
            {
                "type": "updates",
                "ns": (),
                "data": {"model": {"messages": [root]}},
            },
            {
                "type": "updates",
                "ns": nested_ns,
                "data": {"model": {"messages": [nested]}, "tools": {"messages": [tool]}},
            },
            {"type": "values", "ns": nested_ns, "data": {"messages": [nested]}},
            {"type": "values", "ns": (), "data": {"messages": [root, tool]}},
        ]
    )
    tokens: list[tuple[str, str, str]] = []
    messages: list[tuple[object, str | None, str]] = []

    tracing.consume_deep_agent_stream(
        agent,
        {},
        {},
        on_token=lambda *event: tokens.append(event),
        on_message=lambda *event: messages.append(event),
    )

    assert tokens[0][0] != tokens[1][0]
    assert tokens[0][1] == "Coding Agent"
    assert tokens[1][1] == "researcher"
    assert [event[0] for event in messages] == [root, nested, tool]
    assert messages[0][1] == tokens[0][0]
    assert messages[1][1] == tokens[1][0]


def test_stream_adapter_requires_a_root_final_state() -> None:
    """A stream without root values must fail instead of invoking twice."""
    tracing = _tracing_module()
    agent = FakeAgent(
        [{"type": "values", "ns": ("researcher:run-1",), "data": {"messages": []}}]
    )

    with pytest.raises(RuntimeError, match="root final state"):
        tracing.consume_deep_agent_stream(
            agent,
            {},
            {},
            on_token=lambda *args: None,
            on_message=lambda *args: None,
        )


def test_stream_adapter_detaches_from_parent_checkpoint_namespace() -> None:
    """The inner DeepAgent root must not inherit the manager graph namespace."""
    tracing = _tracing_module()
    root_state = {"messages": [AIMessage(content="done")]}

    class ConfigAwareAgent:
        def stream(self, inputs: dict, **kwargs):
            effective = ensure_config(kwargs["config"])
            checkpoint_ns = effective["configurable"].get("checkpoint_ns", "")
            namespace = tuple(checkpoint_ns.split("|")) if checkpoint_ns else ()
            yield {"type": "values", "ns": namespace, "data": root_state}

    token = var_child_runnable_config.set({"configurable": {"checkpoint_ns": "manager|tools"}})
    try:
        result = tracing.consume_deep_agent_stream(
            ConfigAwareAgent(),
            {},
            {"recursion_limit": 25},
            on_token=lambda *args: None,
            on_message=lambda *args: None,
        )
    finally:
        var_child_runnable_config.reset(token)

    assert result is root_state


def test_ui_event_emitters_attach_active_invocation_metadata() -> None:
    """Token drafts and their completed message carry one stream identity."""
    from graph.ui_events import (
        emit_message,
        emit_subagent_token,
        register_ui_event_queue,
        subagent_invocation,
    )
    from server.session_manager import session

    queue: Queue = Queue()
    register_ui_event_queue(queue)
    message = AIMessage(content="hello", id="message-1")

    with subagent_invocation("Coding Agent") as invocation_id:
        start = queue.get_nowait()
        emit_subagent_token("root/message-1", "Coding Agent", "hel")
        emit_message(
            message,
            stream_id="root/message-1",
            source="Coding Agent",
        )
        token = queue.get_nowait()
        completed = queue.get_nowait()

    assert start[0] == "subagent_start"
    assert token == (
        "subagent_token",
        {
            "invocation_id": invocation_id,
            "agent_name": "Coding Agent",
            "stream_id": "root/message-1",
            "source": "Coding Agent",
            "text": "hel",
        },
    )
    assert completed[0] == "subagent_message"
    assert completed[1]["message"] is message
    assert completed[1]["stream_id"] == "root/message-1"
    register_ui_event_queue(session.ui_event_queue)


def test_token_event_reaches_websocket_without_entering_session_history(monkeypatch) -> None:
    """The transient event is forwarded verbatim and never becomes persisted state."""
    from server.routes import chat as chat_module
    from server.session_manager import session

    class FakeWebSocket:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.sent.append(payload)

    while not session.ui_event_queue.empty():
        session.ui_event_queue.get_nowait()
    while not session.state_queue.empty():
        session.state_queue.get_nowait()
    original_states = dict(session.subagent_states)
    payload = {
        "invocation_id": "inv-1",
        "agent_name": "Coding Agent",
        "stream_id": "root/message-1",
        "source": "Coding Agent",
        "text": "hello",
    }
    session.ui_event_queue.put(("subagent_token", payload))
    completed = AIMessage(content="hello", id="message-1")
    session.ui_event_queue.put(
        (
            "subagent_message",
            {
                "invocation_id": "inv-1",
                "agent_name": "Coding Agent",
                "message": completed,
                "stream_id": "root/message-1",
                "source": "Coding Agent",
            },
        )
    )
    ws = FakeWebSocket()
    monkeypatch.setattr(chat_module, "_ws_connected", lambda _: True)

    asyncio.run(chat_module._drain_queues(ws))

    assert ws.sent == [
        {"type": "subagent_token", "data": payload},
        {
            "type": "subagent_message",
            "data": {
                "invocation_id": "inv-1",
                "agent_name": "Coding Agent",
                "message": {
                    "id": "message-1",
                    "type": "ai",
                    "name": None,
                    "content": "hello",
                    "avatar": "🤖",
                    "label": "Assistant",
                    "route": None,
                    "body": "hello",
                    "tags": None,
                },
                "stream_id": "root/message-1",
                "source": "Coding Agent",
            },
        },
    ]
    assert session.subagent_states == original_states
    with pytest.raises(Empty):
        session.state_queue.get_nowait()
