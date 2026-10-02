"""LLM compatibility shim for in-process external agents.

Many community research agents (e.g. GeneAgent from NCBI) were written
against the legacy ``openai==0.28`` API: they call ``openai.ChatCompletion.
create(...)``, hard-code Azure-style ``engine=...`` arguments, and read
their credentials from module-level ``openai.api_key`` assignments.

Modern TissueAgent ships ``openai>=1.73``, which removed
``openai.ChatCompletion`` entirely. Without a shim those external agents
will not import.

This module provides :func:`patch_openai_legacy_api`, a context manager
that monkey-patches the ``openai`` module for the duration of a single
external-agent invocation:

* ``openai.api_type``, ``openai.api_base``, ``openai.api_version``, and
  ``openai.api_key`` are turned into write-accept-only no-op attributes.
* ``openai.ChatCompletion.create(...)`` and
  ``openai.Completion.create(...)`` proxy to the modern
  ``OpenAI().chat.completions.create(...)`` interface.
* ``engine=`` (Azure terminology) and ``model=`` arguments are both
  ignored and replaced with a single pinned model id chosen by the
  caller (e.g. ``"gpt-5.1"``). The whole point is that the external
  agent's hard-coded model choice does not leak into TissueAgent.

The patch is per-invocation so different external agents can each pin
their own model, and a missing OpenAI key is reported with a clear
error rather than silently producing 401s.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Iterator

# Defined at module scope so its identity is stable and it exists *before*
# ``patch_openai_legacy_api`` runs. The previous version referenced
# ``_SENTINEL`` from inside the function body while defining it below the
# function — only worked because Python resolved the free name lazily.
_SENTINEL = object()

# Serialize the openai-module monkey-patch so two concurrent external agents
# can't observe each other's API key or shim while inside the context.
_PATCH_LOCK = threading.Lock()


def _resolve_openai_key() -> str | None:
    """Look up the OpenAI API key from TissueAgent's runtime registry.

    Falls back to the environment variable when the registry is not importable (e.g. during unit tests).
    """
    try:
        from models import get_api_key  # local import to avoid cycles
        key = get_api_key("openai")
    except Exception:
        key = None
    if key:
        return key
    env = os.environ.get("OPENAI_API_KEY")
    return env.strip() if env and env.strip() else None


class _MutableAttrShim:
    """Object that swallows attribute writes (Azure config no-ops)."""

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: D401
        # Accept but ignore; legacy code does ``openai.api_type = "azure"``.
        pass

    def __getattr__(self, name: str) -> Any:
        return ""


def _build_legacy_chat_completion(client: Any, pinned_model: str):
    """Return a `ChatCompletion`-shaped object proxying to the new client."""

    class _ChatCompletionShim:
        @staticmethod
        def create(*args: Any, **kwargs: Any) -> Any:
            # Drop Azure-specific 'engine' and any caller-supplied model.
            kwargs.pop("engine", None)
            kwargs.pop("model", None)
            # Strip kwargs the new SDK no longer accepts.
            for legacy in ("api_key", "api_base", "api_version", "api_type"):
                kwargs.pop(legacy, None)

            # Modern models require tools/tool messages instead of the retired
            # functions/function-role protocol used by the upstream agents.
            functions = kwargs.pop("functions", None)
            if functions is not None:
                kwargs["tools"] = [{"type": "function", "function": fn} for fn in functions]
                kwargs["parallel_tool_calls"] = False  # legacy consumers dispatch one call
            function_choice = kwargs.pop("function_call", None)
            if function_choice is not None:
                kwargs["tool_choice"] = (
                    {"type": "function", "function": function_choice}
                    if isinstance(function_choice, dict) else function_choice
                )
            if "messages" in kwargs:
                kwargs["messages"] = _modernize_legacy_messages(kwargs["messages"])

            response = client.chat.completions.create(
                model=pinned_model, **kwargs
            )
            # The legacy code accesses .choices[0]["message"]["content"]
            # and .choices[0]["message"]. Wrap the modern objects so both
            # subscript and attribute access work.
            return _LegacyResponseProxy(response)

    return _ChatCompletionShim


def _modernize_legacy_messages(messages: list[dict]) -> list[dict]:
    """Convert complete legacy call/result exchanges without mutating history."""
    converted = []
    pending_call = None
    for index, original in enumerate(messages):
        message = dict(original)
        function_call = message.pop("function_call", None)
        if message.get("role") == "assistant" and function_call is not None:
            call_id = f"legacy_call_{index}"
            message["tool_calls"] = [{
                "id": call_id, "type": "function", "function": function_call,
            }]
            pending_call = (call_id, function_call["name"])
        elif message.get("role") == "function":
            if pending_call is None or pending_call[1] != message.get("name"):
                raise ValueError("Legacy function result is missing its preceding assistant call.")
            message = {"role": "tool", "tool_call_id": pending_call[0],
                       "content": message.get("content", "")}
            pending_call = None
        converted.append(message)
    return converted


class _LegacyResponseProxy:
    """Wrap a modern Chat completion so legacy ``[…]`` access still works."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.choices = [_LegacyChoiceProxy(c) for c in response.choices]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)


class _LegacyChoiceProxy:
    """Choice that supports both attribute and dict-style access."""

    def __init__(self, choice: Any) -> None:
        self._choice = choice
        # legacy: choice["message"]["content"]
        msg = choice.message
        self._message = {
            "role": getattr(msg, "role", "assistant"),
            "content": getattr(msg, "content", "") or "",
        }
        # GeneAgent dispatches verification tools by testing membership of this
        # key. Dropping it turns valid function calls into empty assistant replies.
        # Omit it for text-only replies: a present-but-None value also breaks the
        # legacy dispatch branch.
        function_call = getattr(msg, "function_call", None)
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            if len(tool_calls) != 1 or tool_calls[0].type != "function":
                raise ValueError("Legacy agents require exactly one function tool call per response.")
            function_call = tool_calls[0].function
        if function_call is not None:
            self._message["function_call"] = {
                "name": function_call.name,
                "arguments": function_call.arguments,
            }

    def __getitem__(self, key: str) -> Any:
        if key == "message":
            return self._message
        if key == "text":
            return self._message["content"]
        if key == "finish_reason":
            return getattr(self._choice, "finish_reason", None)
        if key == "index":
            return getattr(self._choice, "index", 0)
        raise KeyError(key)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._choice, name)


@contextmanager
def patch_openai_legacy_api(pinned_model: str) -> Iterator[None]:
    """Temporarily patch the ``openai`` module for legacy callers.

    Use this as a context manager around any code that imports and
    invokes an external agent expecting ``openai==0.28``-style APIs.

    Args:
        pinned_model: The OpenAI model id to call regardless of any
            ``engine=`` / ``model=`` the legacy code passes (e.g.
            ``"gpt-5.1"``).

    Raises:
        RuntimeError: if no OpenAI API key is available.
    """
    import openai  # the modern SDK

    key = _resolve_openai_key()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. The external agent requires an "
            "OpenAI key (either as the OPENAI_API_KEY environment variable "
            "or pasted into the UI's API keys panel)."
        )

    # Build a modern client bound to the resolved key.
    from openai import OpenAI

    client = OpenAI(api_key=key)

    # ``openai.api_key`` is a module global; two threads entering this
    # patch at the same time would race, and the second thread's key could
    # leak into the first thread's finally-restore. Serialize the whole
    # patched section so patches nest linearly.
    with _PATCH_LOCK:
        # Save originals so we can restore on exit.
        saved: dict = {}
        for attr in ("api_type", "api_base", "api_version", "api_key", "ChatCompletion", "Completion"):
            saved[attr] = getattr(openai, attr, _SENTINEL)

        # Install no-op attribute targets for the Azure config lines.
        # The legacy module does ``openai.api_type = "azure"`` at import time;
        # since we'll re-import the legacy module *under* this patch, we just
        # need to be sure those assignments don't blow up the modern SDK.
        try:
            openai.api_type = ""  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            openai.api_base = ""  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            openai.api_version = ""  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            openai.api_key = key  # type: ignore[attr-defined]
        except Exception:
            pass

        # Install the legacy-shaped ChatCompletion / Completion shims.
        chat_shim = _build_legacy_chat_completion(client, pinned_model)
        openai.ChatCompletion = chat_shim  # type: ignore[attr-defined]
        openai.Completion = chat_shim  # type: ignore[attr-defined]

        try:
            yield
        finally:
            # Restore whatever was there before, deleting attributes that
            # didn't exist originally.
            for attr, val in saved.items():
                if val is _SENTINEL:
                    try:
                        delattr(openai, attr)
                    except AttributeError:
                        pass
                else:
                    try:
                        setattr(openai, attr, val)
                    except Exception:
                        pass
