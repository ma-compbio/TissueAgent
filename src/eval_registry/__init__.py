"""Eval registry: reusable metrics + offline benchmarks for TissueAgent.

Two halves (see ``knowledge/docs/eval_registry.md`` for the full design):

- :mod:`eval_registry.metrics` — a decorator-collected registry of named, versioned
  scoring functions, referenced by name from benchmark specs (and, later, per-run gates).
- ``eval_registry.benchmarks`` (phase 1+) — markdown-specced benchmarks and a runner that
  materializes a fixture (prompt + inputs + run config), drives the real graph or a tool
  directly, and scores artifacts against golden outputs using the metric registry.
"""

from eval_registry.metrics import (  # noqa: F401
    REGISTRY,
    MetricResult,
    MetricSpec,
    evaluate_threshold,
    get_metric,
    metric,
)
