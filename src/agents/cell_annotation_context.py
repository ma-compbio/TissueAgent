"""Request-scoped biological context for adaptive cell annotation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


_BOUND_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "cell_annotation_context",
    default=None,
)


@contextmanager
def bind_cell_annotation_context(
    context: Mapping[str, Any] | None,
) -> Iterator[None]:
    """Bind immutable orchestrator context for one delegated agent invocation."""
    value = dict(context) if context is not None else None
    token = _BOUND_CONTEXT.set(value)
    try:
        yield
    finally:
        _BOUND_CONTEXT.reset(token)


def get_bound_cell_annotation_context() -> dict[str, Any] | None:
    """Return a copy of the currently bound annotation context, if any."""
    context = _BOUND_CONTEXT.get()
    return dict(context) if context is not None else None
