"""Request-scoped task information for tissue-niche annotation."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any

_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("tissue_niche_context", default=None)


@contextmanager
def bind_tissue_niche_context(context: Mapping[str, Any]) -> Iterator[None]:
    """Carry the original request through nested graph and tool invocations."""
    token = _CONTEXT.set(deepcopy(dict(context)))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def get_tissue_niche_context() -> dict[str, Any]:
    """Return the bound task without allowing a caller to mutate it."""
    return deepcopy(_CONTEXT.get() or {})
