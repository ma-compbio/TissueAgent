"""Translate DeepAgent stream parts into TissueAgent trace events."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

TokenCallback = Callable[[str, str, str], None]
MessageCallback = Callable[[BaseMessage, str | None, str], None]


def _namespace(part: Mapping[str, Any]) -> tuple[str, ...]:
    raw = part.get("ns", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(segment) for segment in raw)


def _source(namespace: tuple[str, ...]) -> str:
    if not namespace:
        return "Coding Agent"
    for segment in reversed(namespace):
        name = segment.split(":", 1)[0]
        if name != "tools":
            return name.replace("_", " ")
    return "delegated agent"


def _visible_text(chunk: Any) -> str:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text: list[str] = []
    for block in content:
        if isinstance(block, str):
            text.append(block)
        elif isinstance(block, Mapping) and block.get("type") in ("text", "text_delta"):
            value = block.get("text")
            if isinstance(value, str):
                text.append(value)
    return "".join(text)


def _message_id(message: Any, metadata: Mapping[str, Any] | None = None) -> str | None:
    value = getattr(message, "id", None)
    if value:
        return str(value)
    if metadata:
        for key in ("run_id", "checkpoint_ns", "langgraph_node"):
            value = metadata.get(key)
            if value:
                return str(value)
    return None


def _stream_id(namespace: tuple[str, ...], message_id: str) -> str:
    scope = "/".join(namespace) if namespace else "root"
    return f"{scope}/{message_id}"


def _iter_completed_messages(value: Any):
    if isinstance(value, (AIMessage, ToolMessage)):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_completed_messages(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_completed_messages(nested)


def _dedup_key(namespace: tuple[str, ...], message: BaseMessage) -> tuple[Any, ...]:
    message_id = getattr(message, "id", None)
    if message_id:
        return namespace, message.type, str(message_id)
    return (
        namespace,
        message.type,
        getattr(message, "name", None),
        getattr(message, "tool_call_id", None),
        repr(message.content),
    )


def consume_deep_agent_stream(
    agent: Any,
    inputs: dict[str, Any],
    config: dict[str, Any],
    *,
    on_token: TokenCallback,
    on_message: MessageCallback,
) -> dict[str, Any]:
    """Consume one DeepAgent run and return its latest root state."""
    final_state: dict[str, Any] | None = None
    seen_messages: set[tuple[Any, ...]] = set()
    known_streams: dict[tuple[tuple[str, ...], str], str] = {}

    # This runs inside the manager graph; an implicit configurable inherits its checkpoint_ns.
    stream_config = dict(config)
    configurable = config.get("configurable")
    stream_config["configurable"] = dict(configurable) if isinstance(configurable, Mapping) else {}

    parts = agent.stream(
        inputs,
        config=stream_config,
        stream_mode=["messages", "updates", "values"],
        subgraphs=True,
        version="v2",
    )
    for part in parts:
        if not isinstance(part, Mapping):
            logging.debug("Ignoring malformed DeepAgent stream part: %r", part)
            continue
        part_type = part.get("type")
        namespace = _namespace(part)
        data = part.get("data")

        if part_type == "messages":
            if not isinstance(data, (list, tuple)) or len(data) != 2:
                logging.debug("Ignoring malformed DeepAgent message part: %r", data)
                continue
            chunk, raw_metadata = data
            metadata = raw_metadata if isinstance(raw_metadata, Mapping) else {}
            text = _visible_text(chunk)
            message_id = _message_id(chunk, metadata)
            if not text or not message_id:
                continue
            stream_id = _stream_id(namespace, message_id)
            known_streams[(namespace, message_id)] = stream_id
            on_token(stream_id, _source(namespace), text)
            continue

        if part_type == "updates":
            for message in _iter_completed_messages(data):
                key = _dedup_key(namespace, message)
                if key in seen_messages:
                    continue
                seen_messages.add(key)
                message_id = _message_id(message)
                stream_id = (
                    known_streams.get((namespace, message_id)) if message_id is not None else None
                )
                on_message(message, stream_id, _source(namespace))
            continue

        if part_type == "values" and not namespace and isinstance(data, dict):
            final_state = data

    if final_state is None:
        raise RuntimeError("DeepAgent stream ended without a root final state")
    return final_state
