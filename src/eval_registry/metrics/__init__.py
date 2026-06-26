"""Metric registry: named, versioned scoring functions.

A metric is a plain function registered under a unique name via the :func:`metric`
decorator. Benchmark specs reference metrics by that name, so one definition is reused by
tool-level checks, pipeline-level checks, and (later) per-run gates.

Metric *kinds* declare what inputs a metric needs, which the runner uses to wire arguments:

- ``"reference_based"`` — compares a prediction against a golden/ground-truth value
  (e.g. ``ari(pred_labels, true_labels)``).
- ``"reference_free"`` — scores a prediction alone, no ground truth
  (e.g. ``mean_prediction_confidence(confidences)``).
- ``"artifact"`` — inspects a produced file/path on disk
  (e.g. ``file_exists(path)``).

Thresholds are declared in the spec as a single-key dict — ``{gte: 0.6}``, ``{lte: 0.15}``,
``{eq: true}`` — and checked by :func:`evaluate_threshold`. ``higher_is_better`` is metadata
for reporting/diffing; it does not change threshold semantics.

Importing this package triggers registration of the built-in metric modules so the registry
is populated as a side effect of ``import eval_registry.metrics``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

_VALID_KINDS = frozenset({"reference_based", "reference_free", "artifact"})


@dataclass(frozen=True)
class MetricSpec:
    """A registered metric: its function plus metadata used by the runner and reports."""

    name: str
    fn: Callable[..., float | bool]
    kind: str
    higher_is_better: bool = True
    version: int = 1
    doc: str = ""


@dataclass
class MetricResult:
    """The outcome of scoring one metric against an (optional) threshold."""

    name: str
    value: float | bool
    threshold: dict[str, Any] | None = None
    passed: bool | None = None  # None when no threshold was supplied
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


REGISTRY: dict[str, MetricSpec] = {}


def metric(
    name: str,
    *,
    kind: str,
    higher_is_better: bool = True,
    version: int = 1,
) -> Callable[[Callable[..., float | bool]], Callable[..., float | bool]]:
    """Register *fn* as a metric named *name*.

    Raises ``ValueError`` on an unknown *kind* or a duplicate name, so registration problems
    surface at import time rather than silently shadowing.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"Unknown metric kind {kind!r}; expected one of {sorted(_VALID_KINDS)}.")

    def deco(fn: Callable[..., float | bool]) -> Callable[..., float | bool]:
        if name in REGISTRY:
            raise ValueError(f"Metric {name!r} is already registered.")
        REGISTRY[name] = MetricSpec(
            name=name,
            fn=fn,
            kind=kind,
            higher_is_better=higher_is_better,
            version=version,
            doc=(fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
        )
        return fn

    return deco


def get_metric(name: str) -> MetricSpec:
    """Return the registered metric *name*, or raise ``KeyError`` listing valid names."""
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Metric {name!r} not found. Registered metrics: {sorted(REGISTRY)}"
        ) from None


def evaluate_threshold(value: float | bool, threshold: dict[str, Any] | None) -> bool | None:
    """Check *value* against a single-key *threshold* dict.

    Supported keys: ``gte``, ``lte``, ``gt``, ``lt``, ``eq``. Returns ``None`` when
    *threshold* is falsy (no gate). Raises ``ValueError`` for a malformed threshold.
    """
    if not threshold:
        return None
    if len(threshold) != 1:
        raise ValueError(f"Threshold must have exactly one key, got {threshold!r}.")
    (op, target), = threshold.items()
    if op == "gte":
        return value >= target
    if op == "lte":
        return value <= target
    if op == "gt":
        return value > target
    if op == "lt":
        return value < target
    if op == "eq":
        return value == target
    raise ValueError(f"Unknown threshold operator {op!r} in {threshold!r}.")


def score(
    name: str,
    *args: Any,
    threshold: dict[str, Any] | None = None,
    **kwargs: Any,
) -> MetricResult:
    """Run metric *name* on the given args and compare to *threshold*.

    Captures any exception from the metric body into ``MetricResult.error`` so one bad metric
    doesn't abort a whole benchmark.
    """
    spec = get_metric(name)
    try:
        value = spec.fn(*args, **kwargs)
    except Exception as exc:  # surfaced per-metric, not fatal to the suite
        return MetricResult(name=name, value=float("nan"), threshold=threshold, error=str(exc))
    return MetricResult(
        name=name,
        value=value,
        threshold=threshold,
        passed=evaluate_threshold(value, threshold),
    )


# Importing the built-in metric modules registers their @metric functions as a side effect.
from eval_registry.metrics import composition, confidence, coverage  # noqa: E402,F401
