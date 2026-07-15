"""Tests for the header-driven retry wrapper (src/server/rate_limit.py).

Two things are under test here:

1. **Classification** — that the right exception classes retry and the wrong ones
   don't. These assertions are deliberately written against the *installed* SDKs
   (openai, anthropic) rather than mocks, so that an SDK upgrade that renames or
   re-parents an exception fails here instead of silently disabling retries in
   production. That is the main value of this file.
2. **Wait computation** — that provider hints are honoured and that hint-less
   errors fall back to backoff without blowing up.

All sleeps are patched out; these tests must stay fast.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import anthropic
import httpx
import openai
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server.rate_limit import RETRIABLE, _compute_wait, _extract_retry_after, with_header_retry


# --------------------------------------------------------------------------
# Exception construction helpers
#
# The SDK exceptions require real httpx request/response objects. Building them
# here (rather than using Mock) is intentional: if a constructor signature
# changes, these helpers fail loudly.
# --------------------------------------------------------------------------

_REQUEST = httpx.Request("POST", "https://api.example.com/v1/messages")


def _response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code=status, headers=headers or {}, request=_REQUEST)


def _status_error(cls, status: int, headers: dict[str, str] | None = None, msg: str = "boom"):
    return cls(msg, response=_response(status, headers), body=None)


# --------------------------------------------------------------------------
# 1. Classification — which errors retry
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(_status_error(openai.RateLimitError, 429), id="openai-429"),
        pytest.param(_status_error(anthropic.RateLimitError, 429), id="anthropic-429"),
        pytest.param(_status_error(openai.InternalServerError, 500), id="openai-500"),
        pytest.param(_status_error(anthropic.InternalServerError, 500), id="anthropic-500"),
        pytest.param(openai.APIConnectionError(request=_REQUEST), id="openai-connection"),
        pytest.param(anthropic.APIConnectionError(request=_REQUEST), id="anthropic-connection"),
        pytest.param(openai.APITimeoutError(request=_REQUEST), id="openai-timeout"),
        pytest.param(anthropic.APITimeoutError(request=_REQUEST), id="anthropic-timeout"),
    ],
)
def test_transient_errors_are_retriable(exc):
    """Transient failures must retry rather than kill the run."""
    assert isinstance(exc, RETRIABLE)


def test_anthropic_529_overloaded_is_retriable():
    """529 is the case this whole change exists for.

    It maps to a dedicated OverloadedError that does NOT inherit from
    InternalServerError, so it needs its own entry in RETRIABLE. If the SDK stops
    exporting it from the private path, rate_limit.py degrades gracefully — this
    test is what makes that degradation visible.
    """
    from anthropic._exceptions import OverloadedError

    assert not issubclass(OverloadedError, anthropic.InternalServerError), (
        "SDK changed: OverloadedError now inherits from InternalServerError, so the "
        "explicit RETRIABLE entry is redundant and can be dropped."
    )
    assert isinstance(_status_error(OverloadedError, 529), RETRIABLE)


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(_status_error(openai.BadRequestError, 400), id="openai-400"),
        pytest.param(_status_error(anthropic.BadRequestError, 400), id="anthropic-400"),
        pytest.param(_status_error(openai.AuthenticationError, 401), id="openai-401"),
        pytest.param(_status_error(anthropic.AuthenticationError, 401), id="anthropic-401"),
        pytest.param(_status_error(openai.PermissionDeniedError, 403), id="openai-403"),
        pytest.param(_status_error(openai.NotFoundError, 404), id="openai-404"),
        pytest.param(_status_error(openai.UnprocessableEntityError, 422), id="openai-422"),
    ],
)
def test_deterministic_errors_are_not_retriable(exc):
    """Deterministic failures must surface immediately.

    Retrying these burns quota to fail identically. Guards against anyone
    'simplifying' RETRIABLE down to APIStatusError, which would catch them all.
    """
    assert not isinstance(exc, RETRIABLE)


# --------------------------------------------------------------------------
# 2. Wait computation
# --------------------------------------------------------------------------


def test_extract_retry_after_prefers_milliseconds():
    """Anthropic sends retry-after-ms; it wins over the coarser seconds header."""
    exc = _status_error(anthropic.RateLimitError, 429, {"retry-after-ms": "1500"})
    assert _extract_retry_after(exc) == pytest.approx(1.5)


def test_extract_retry_after_seconds_header():
    """The standard Retry-After header is honoured."""
    exc = _status_error(openai.RateLimitError, 429, {"retry-after": "3"})
    assert _extract_retry_after(exc) == pytest.approx(3.0)


def test_extract_retry_after_parses_openai_body_text():
    """OpenAI often puts the hint only in the body prose, not a header."""
    exc = _status_error(openai.RateLimitError, 429, msg="Please try again in 8.4s.")
    assert _extract_retry_after(exc) == pytest.approx(8.4)


def test_extract_retry_after_returns_none_for_hintless_error():
    """A hint-less error yields None rather than crashing.

    APITimeoutError has no .response at all — _extract_retry_after must survive
    the getattr chain and return None so backoff kicks in.
    """
    assert _extract_retry_after(openai.APITimeoutError(request=_REQUEST)) is None


def test_hintless_errors_use_backoff_not_zero_wait():
    """Hint-less errors must wait, not spin.

    The errors newly added to RETRIABLE mostly carry no retry-after hint, so the
    backoff path — previously the fallback — is now the common path.
    """
    exc = openai.APITimeoutError(request=_REQUEST)
    wait, reason = _compute_wait(exc, attempt=1)
    assert reason == "backoff"
    assert wait >= 4.0  # _BACKOFF_BASE_SEC, plus jitter


def test_backoff_grows_and_is_capped():
    """Backoff escalates across attempts but never exceeds the safety cap."""
    exc = anthropic.APIConnectionError(request=_REQUEST)
    first, _ = _compute_wait(exc, attempt=1)
    later, _ = _compute_wait(exc, attempt=3)
    assert later > first
    huge, _ = _compute_wait(exc, attempt=20)
    assert huge <= 60.0 * 1.15 + 0.01  # _BACKOFF_MAX_SEC + max jitter


def test_header_wait_is_capped():
    """A misbehaving server cannot pin us forever via an absurd Retry-After."""
    exc = _status_error(anthropic.RateLimitError, 429, {"retry-after": "99999"})
    wait, reason = _compute_wait(exc, attempt=1)
    assert reason == "retry-after"
    assert wait <= 120.0 * 1.15 + 0.01  # _HEADER_WAIT_MAX_SEC + max jitter


# --------------------------------------------------------------------------
# 3. Retry loop behaviour
# --------------------------------------------------------------------------


class _FakeModel:
    """Minimal Runnable stand-in that raises a scripted sequence, then succeeds."""

    def __init__(self, failures: list[BaseException]):
        self._failures = list(failures)
        self.calls = 0

    def invoke(self, input, config=None, **kwargs):
        self.calls += 1
        if self._failures:
            raise self._failures.pop(0)
        return "ok"

    async def ainvoke(self, input, config=None, **kwargs):
        return self.invoke(input, config=config, **kwargs)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Patch both sleep paths so the retry loop runs instantly."""
    monkeypatch.setattr("server.rate_limit.time.sleep", lambda _s: None)

    async def _fake_async_sleep(_s):
        return None

    monkeypatch.setattr("server.rate_limit.asyncio.sleep", _fake_async_sleep)


def test_retries_500_then_succeeds():
    """A transient 5xx is absorbed; the caller never sees it."""
    model = _FakeModel([_status_error(openai.InternalServerError, 500)])
    assert with_header_retry(model, max_attempts=3).invoke("hi") == "ok"
    assert model.calls == 2


def test_retries_529_overloaded_then_succeeds():
    """End-to-end proof for 529 — the case that motivated widening RETRIABLE."""
    from anthropic._exceptions import OverloadedError

    model = _FakeModel([_status_error(OverloadedError, 529)])
    assert with_header_retry(model, max_attempts=3).invoke("hi") == "ok"
    assert model.calls == 2


def test_bad_request_raises_immediately_without_retrying():
    """A malformed request fails the same way six times; surface it at once."""
    model = _FakeModel([_status_error(anthropic.BadRequestError, 400)])
    with pytest.raises(anthropic.BadRequestError):
        with_header_retry(model, max_attempts=6).invoke("hi")
    assert model.calls == 1, "a 400 must not be retried"


def test_exhaustion_reraises_original_exception():
    """After max_attempts the provider's own error propagates, not a wrapper."""
    failures = [_status_error(anthropic.InternalServerError, 500) for _ in range(5)]
    model = _FakeModel(failures)
    with pytest.raises(anthropic.InternalServerError):
        with_header_retry(model, max_attempts=3).invoke("hi")
    assert model.calls == 3


def test_timeout_retries_via_backoff_path():
    """End-to-end for the hint-less case: must not crash in _extract_retry_after."""
    model = _FakeModel([openai.APITimeoutError(request=_REQUEST)])
    assert with_header_retry(model, max_attempts=3).invoke("hi") == "ok"
    assert model.calls == 2


def test_async_path_retries_too():
    """The async path shares the retry policy — the server calls ainvoke."""
    model = _FakeModel([_status_error(anthropic.InternalServerError, 500)])
    wrapped = with_header_retry(model, max_attempts=3)
    assert asyncio.run(wrapped.ainvoke("hi")) == "ok"
    assert model.calls == 2


def test_sync_invoke_refuses_to_run_inside_event_loop():
    """time.sleep in a live loop would starve every other client."""
    wrapped = with_header_retry(_FakeModel([]), max_attempts=2)

    async def _call():
        return wrapped.invoke("hi")

    with pytest.raises(RuntimeError, match="cannot be called from a running event"):
        asyncio.run(_call())
