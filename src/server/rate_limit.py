"""Header-driven retry wrapper for chat models (strategy 1A).

The provider-default :meth:`with_retry` uses blind exponential backoff,
which can sleep too long (or too short) compared to the actual rate-limit
window. This module wraps a model so that on a rate-limit error we:

1. Parse the provider's hint from the exception or its HTTP response:
   - OpenAI:    ``Retry-After`` header (seconds, possibly fractional)
   - Anthropic: ``retry-after`` (seconds) or ``retry-after-ms``
2. Sleep that long (plus a small jitter), then retry.
3. Fall back to exponential backoff (with caps) if no header is present.
4. Stop after ``max_attempts`` and let the original exception propagate.

We do NOT depend on internal LangChain retry plumbing; the wrapper sits
above :meth:`BaseChatModel.invoke` / ``ainvoke`` so the same retry policy
applies wherever the bound model is called.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Any, Optional, Tuple

import anthropic
import openai
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig

RETRIABLE = (openai.RateLimitError, anthropic.RateLimitError)

# Safety caps so a misbehaving server can't pin us forever.
_HEADER_WAIT_MAX_SEC = 120.0
_BACKOFF_BASE_SEC = 4.0
_BACKOFF_MAX_SEC = 60.0
_JITTER_FRAC = 0.15


def _extract_retry_after(exc: BaseException) -> Optional[float]:
    """Best-effort extraction of the provider's wait hint, in seconds.

    Both OpenAI and Anthropic surface the underlying HTTPX response on the exception via
    ``.response``. We also scan the error message for explicit "try again in 8s" or
    "in 800ms" phrasings used by OpenAI's body text.
    """
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)

    if headers:
        # Anthropic prefers milliseconds when available.
        ms = headers.get("retry-after-ms") or headers.get("Retry-After-Ms")
        if ms:
            try:
                return max(0.0, float(ms) / 1000.0)
            except ValueError:
                pass
        secs = headers.get("retry-after") or headers.get("Retry-After")
        if secs:
            try:
                return max(0.0, float(secs))
            except ValueError:
                # HTTP-date form is unusual on 429s; ignore.
                pass

    # OpenAI's 429 body often includes a free-text hint like
    # "Please try again in 8.4s." or "Please try again in 200ms."
    msg = str(exc)
    m = re.search(r"try again in\s+([0-9]*\.?[0-9]+)\s*(ms|s)\b", msg, re.IGNORECASE)
    if m:
        amount = float(m.group(1))
        unit = m.group(2).lower()
        return amount / 1000.0 if unit == "ms" else amount

    return None


def _compute_wait(exc: BaseException, attempt: int) -> Tuple[float, str]:
    """Decide how long to sleep before the next retry.

    Returns ``(seconds, reason)`` where *reason* is a short tag for logs.
    """
    hint = _extract_retry_after(exc)
    if hint is not None:
        wait = min(hint, _HEADER_WAIT_MAX_SEC)
        # Small upward jitter so multiple concurrent runs don't wake in unison.
        wait += wait * _JITTER_FRAC * random.random()
        return wait, "retry-after"

    # Fallback: capped exponential backoff with jitter.
    base = min(_BACKOFF_BASE_SEC * (2 ** (attempt - 1)), _BACKOFF_MAX_SEC)
    wait = base * (1.0 + _JITTER_FRAC * random.random())
    return wait, "backoff"


def _is_non_retriable_rate_limit(exc: BaseException) -> bool:
    """Return whether a 429 reports a billing or quota condition that waiting cannot fix."""
    codes = {
        "billing_hard_limit_reached",
        "billing_not_active",
        "insufficient_quota",
    }
    direct_code = getattr(exc, "code", None)
    if direct_code in codes:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict) and error.get("code") in codes:
            return True
    return any(f"'code': '{code}'" in str(exc) for code in codes)


class _RetryWrapper(Runnable):
    """Wraps a chat model with header-driven rate-limit retries."""

    def __init__(self, inner: Runnable, max_attempts: int = 6) -> None:
        self._inner = inner
        self._max_attempts = max_attempts

    # Required for LangGraph / LangChain interop.
    def bind_tools(self, *args: Any, **kwargs: Any) -> "_RetryWrapper":
        return _RetryWrapper(self._inner.bind_tools(*args, **kwargs), self._max_attempts)  # type: ignore[attr-defined]

    def with_structured_output(self, *args: Any, **kwargs: Any) -> "_RetryWrapper":
        return _RetryWrapper(
            self._inner.with_structured_output(*args, **kwargs),  # type: ignore[attr-defined]
            self._max_attempts,
        )

    def __getattr__(self, name: str) -> Any:
        # Forward unknown attributes (e.g. .name, .model_name) to the inner runnable
        # so callers that introspect the model still work.
        return getattr(self._inner, name)

    def invoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Any:
        # Guard against being called from a live event loop — the time.sleep
        # below would block it and starve every other client. Callers that
        # need to run under asyncio must use ``ainvoke`` instead.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "_RetryWrapper.invoke() cannot be called from a running event "
                "loop — use ainvoke() to avoid blocking the loop on time.sleep."
            )
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._inner.invoke(input, config=config, **kwargs)
            except RETRIABLE as exc:
                if _is_non_retriable_rate_limit(exc):
                    logging.warning("Non-retriable provider quota error; giving up immediately.")
                    raise
                if attempt >= self._max_attempts:
                    logging.warning(
                        "Rate limit: exhausted %d attempts, giving up.",
                        self._max_attempts,
                    )
                    raise
                wait, reason = _compute_wait(exc, attempt)
                logging.warning(
                    "Rate limit on attempt %d/%d; sleeping %.2fs (%s).",
                    attempt,
                    self._max_attempts,
                    wait,
                    reason,
                )
                time.sleep(wait)
        # Unreachable; the loop either returns or raises.
        raise RuntimeError("retry loop fell through")

    async def ainvoke(
        self, input: Any, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Any:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._inner.ainvoke(input, config=config, **kwargs)
            except RETRIABLE as exc:
                if _is_non_retriable_rate_limit(exc):
                    logging.warning("Non-retriable provider quota error; giving up immediately.")
                    raise
                if attempt >= self._max_attempts:
                    logging.warning(
                        "Rate limit: exhausted %d attempts, giving up.",
                        self._max_attempts,
                    )
                    raise
                wait, reason = _compute_wait(exc, attempt)
                logging.warning(
                    "Rate limit on attempt %d/%d; sleeping %.2fs (%s).",
                    attempt,
                    self._max_attempts,
                    wait,
                    reason,
                )
                await asyncio.sleep(wait)
        raise RuntimeError("retry loop fell through")


def with_header_retry(model: BaseChatModel, max_attempts: int = 6) -> Runnable:
    """Return *model* wrapped with header-aware rate-limit retries."""
    return _RetryWrapper(model, max_attempts=max_attempts)
