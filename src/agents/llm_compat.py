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
from contextlib import contextmanager
from typing import Any, Iterator


def _resolve_openai_key() -> str | None:
    """Look up the OpenAI API key from TissueAgent's runtime registry.

    Falls back to the environment variable when the registry is not
    importable (e.g. during unit tests).
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

            response = client.chat.completions.create(
                model=pinned_model, **kwargs
            )
            # The legacy code accesses .choices[0]["message"]["content"]
            # and .choices[0]["message"]. Wrap the modern objects so both
            # subscript and attribute access work.
            return _LegacyResponseProxy(response)

    return _ChatCompletionShim


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


_SENTINEL = object()
