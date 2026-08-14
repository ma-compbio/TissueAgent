"""Message sanitization, normalization, and content-formatting utilities."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# additional_kwargs keys that carry provider-specific data the API rejects on
# a return trip (e.g. reasoning traces). Everything else — including UI-only
# payloads like plan_payload / validation_payload — must survive sanitize.
_STRIP_AI_KWARG_KEYS = frozenset({
    "reasoning",
    "reasoning_content",
    "thinking",
    "signature",
    "cache_control",
    "tool_use_id",
    "refusal",
})


def normalize_trailing_assistant(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Fold a trailing assistant turn into a user turn for prefill-free providers.

    Anthropic removed assistant-turn prefill starting with the 4.6 generation: a
    ``messages`` array whose last entry is ``role: "assistant"`` returns a 400. Our
    LangGraph nodes append each agent's ``AIMessage`` to state, and several filters
    (notably :func:`message_filters.filter_for_recruiter`) project histories that end
    on exactly that shape — so every Anthropic run 400s without this normalization.
    OpenAI accepts the trailing assistant turn, which is why this only runs on the
    Anthropic path.

    Two shapes are deliberately left alone:

    * A trailing ``AIMessage`` *with* ``tool_calls`` — that is a mid-tool-loop state
      whose ToolMessages have not been appended yet. Rewriting it would orphan the
      tool_call ids and break the tool protocol.
    * An empty list — callers such as ``filter_for_manager`` already inject their own
      synthetic ``HumanMessage``; adding a second one here would double it up.

    Returns a new list; the input is never mutated (LangGraph shares state refs).
    """
    if not messages:
        return messages
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return messages
    if getattr(last, "tool_calls", None):
        return messages

    text = last.content if isinstance(last.content, str) else str(last.content)
    text = text.strip()
    if not text:
        # Nothing to carry forward — drop the empty turn rather than sending an
        # empty user message, which providers also reject.
        return list(messages[:-1])

    # Preserve the content as context rather than discarding it: downstream agents
    # (e.g. the recruiter reading the planner's plan) depend on this text.
    carried = HumanMessage(
        content=(
            f"Output from the previous agent"
            f"{f' ({last.name})' if getattr(last, 'name', None) else ''}:\n\n{text}"
        )
    )
    return list(messages[:-1]) + [carried]


def sanitize_message(message: BaseMessage) -> BaseMessage:
    """Ensure a message's content is safe to send back to the OpenAI API.

    Reasoning models (e.g. GPT-5) may return content lists or additional_kwargs entries with
    non-standard types that the API rejects on subsequent turns. This strips those to plain text.

    Returns a *new* message (via ``model_copy``) rather than mutating the input, since
    LangGraph passes shared references through the state channel.
    """
    if isinstance(message, AIMessage):
        content = message.content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") in ("text", "output_text"):
                        text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            content = "\n".join(text_parts).strip()
        # Preserve additional_kwargs but drop provider-specific keys the API
        # rejects on the return trip. UI-only keys (plan_payload,
        # validation_payload, …) are kept intact so downstream serializers can
        # still see them.
        original_kwargs = getattr(message, "additional_kwargs", None) or {}
        filtered_kwargs = {
            k: v for k, v in original_kwargs.items() if k not in _STRIP_AI_KWARG_KEYS
        }
        return AIMessage(
            content=content,
            id=message.id,
            tool_calls=message.tool_calls or [],
            name=getattr(message, "name", None),
            additional_kwargs=filtered_kwargs,
            # Preserved for the same reason as in standardize_message_format:
            # rebuilding the message must not silently discard token accounting.
            usage_metadata=getattr(message, "usage_metadata", None),
        )
    if isinstance(message.content, list):
        # For non-AI messages (Human/Tool), ensure list items have type.
        # Copy the message so we don't mutate a reference shared elsewhere.
        sanitized_content = []
        for item in message.content:
            if isinstance(item, dict):
                if "type" in item:
                    sanitized_content.append(item)
                elif "text" in item:
                    sanitized_content.append({"type": "text", "text": item["text"]})
            elif isinstance(item, str):
                sanitized_content.append({"type": "text", "text": item})
            else:
                sanitized_content.append(item)
        return message.model_copy(update={"content": sanitized_content})
    return message


def standardize_message_format(message: AIMessage) -> AIMessage:
    """Normalize an AI message into a consistent text + tool_calls format.

    Provider responses may encode tool calls inline within the content list. This function separates
    text parts from tool-call parts and returns a new :class:`AIMessage` with plain-text content and
    an explicit ``tool_calls`` list.

    Args:
        message: The raw AI message to normalize.

    Returns:
        A new :class:`AIMessage` with standardized content, or the original message unchanged if
        content is already a string.
    """
    if isinstance(message.content, list):
        text_parts = []
        tool_calls = []
        other_parts = []

        for item in message.content:
            if not isinstance(item, dict):
                other_parts.append(item)
                continue
            itype = item.get("type")
            if itype in ("text", "output_text"):
                text_parts.append(item.get("text", ""))
            elif itype in ("tool_use", "tool_call"):
                tool_call = {
                    "name": item.get("name"),
                    "args": item.get("input") or item.get("args") or {},
                    "id": item.get("id"),
                    "type": "tool_call",
                }
                tool_calls.append(tool_call)
            else:
                other_parts.append(item)

        combined_tool_calls = tool_calls or message.tool_calls or []
        # Carry usage_metadata across the rebuild. Anthropic returns list content on
        # every thinking-enabled response, so dropping it here zeroed out token
        # accounting for whole agents (planner/recruiter reported 0 tokens despite
        # real calls) and made metrics.json undercount the run.
        return AIMessage(
            "\n".join(text_parts).strip(),
            id=message.id,
            tool_calls=combined_tool_calls,
            usage_metadata=getattr(message, "usage_metadata", None),
            response_metadata=getattr(message, "response_metadata", None) or {},
        )
    return message


# See https://reference.langchain.com/python/langchain-core/messages/base/BaseMessage
type MessageContent = str | list[str | dict] | None


def stringify_content(content: MessageContent) -> list[str]:
    """Turn content into printable lines for logging.

    Handles str or multimodal (list) content.
    """
    lines: list[str] = []
    if isinstance(content, str):
        lines.extend(content.splitlines())
    elif isinstance(content, list):
        for idx, part in enumerate(content, 1):
            if not isinstance(part, dict):
                lines.append(f"[{idx}] {part}")
                continue
            ptype = part.get("type")
            if ptype in ("text", "output_text"):
                lines.append(f"[{idx}] (text) {part.get('text', '')}")
            elif ptype in ("image_url", "image"):
                url = part.get("image_url")
                if isinstance(url, dict):
                    url = url.get("url")
                lines.append(
                    f"[{idx}] (image) {str(url)[:80]}{'...' if url and len(str(url)) > 80 else ''}"
                )
            elif ptype in ("tool_use", "tool_call"):
                lines.append(f"[{idx}] (tool_call) {part.get('name')}")
            else:
                lines.append(f"[{idx}] ({ptype}) {part}")
    else:
        lines.append(str(content))
    return lines
