"""Message sanitization, normalization, and content-formatting utilities."""

from typing import Any, List

from langchain_core.messages import AIMessage, BaseMessage


def sanitize_message(message: BaseMessage) -> BaseMessage:
    """Ensure a message's content is safe to send back to the OpenAI API.

    Reasoning models (e.g. GPT-5) may return content lists or additional_kwargs entries with non-standard types that the
    API rejects on subsequent turns. This strips those to plain text.
    """
    if isinstance(message, AIMessage):
        content = message.content
        # If content is a list, reduce to plain text
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") in ("text", "output_text"):
                        text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            content = "\n".join(text_parts).strip()
        # Rebuild AIMessage without problematic additional_kwargs
        sanitized = AIMessage(
            content=content,
            id=message.id,
            tool_calls=message.tool_calls or [],
            name=getattr(message, "name", None),
        )
        return sanitized
    if isinstance(message.content, list):
        # For non-AI messages (Human/Tool), ensure list items have type
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
        message.content = sanitized_content
    return message


def standardize_message_format(message: AIMessage) -> AIMessage:
    """Normalize an AI message into a consistent text + tool_calls format.

    Provider responses may encode tool calls inline within the content
    list.  This function separates text parts from tool-call parts and
    returns a new :class:`AIMessage` with plain-text content and an
    explicit ``tool_calls`` list.

    Args:
        message: The raw AI message to normalize.

    Returns:
        A new :class:`AIMessage` with standardized content, or the
        original message unchanged if content is already a string.
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
        return AIMessage(
            "\n".join(text_parts).strip(), id=message.id, tool_calls=combined_tool_calls
        )
    return message


def stringify_content(content: Any) -> List[str]:
    """Turn content into printable lines for logging.

    Handles str or multimodal (list) content.
    """
    lines: List[str] = []
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


def content_to_text(content: Any) -> str:
    """Best-effort flatten of LangChain message content to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                # multimodal content parts: {"type": "text", "text": "..."}
                text = chunk.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)
