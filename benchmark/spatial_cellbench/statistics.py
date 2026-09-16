"""Paper-level summaries for repeated spatial benchmark runs."""

from __future__ import annotations

import random
from collections import defaultdict
from statistics import mean

EXPECTED_REPLICATES = frozenset({1, 2, 3})


def paper_arm_means(rows: list[dict], metric: str) -> dict[str, dict[str, float]]:
    """Average replicates within paper and arm before comparison."""
    grouped = defaultdict(dict)
    for row in rows:
        key = (row["eval_id"], row["arm"])
        replicate = int(row["replicate"])
        if replicate in grouped[key]:
            raise ValueError(f"Duplicate replicate {replicate} for {key}")
        if replicate not in EXPECTED_REPLICATES:
            raise ValueError(f"Unexpected replicate {replicate} for {key}")
        grouped[key][replicate] = float(row["metrics"][metric])
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for (eval_id, arm), by_replicate in grouped.items():
        if set(by_replicate) == EXPECTED_REPLICATES:
            result[eval_id][arm] = mean(by_replicate.values())
    return dict(result)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def paired_summary(
    rows: list[dict],
    metric: str,
    treatment: str,
    baseline: str,
    bootstrap_samples: int = 10_000,
    seed: int = 20260720,
) -> dict:
    """Return a paired paper-level estimate and percentile-bootstrap interval."""
    means = paper_arm_means(rows, metric)
    all_ids = sorted({row["eval_id"] for row in rows})
    paired_ids = [
        eval_id
        for eval_id in all_ids
        if treatment in means.get(eval_id, {}) and baseline in means.get(eval_id, {})
    ]
    if not paired_ids:
        raise ValueError(f"No complete paired papers for {treatment} versus {baseline}")
    deltas = [means[eval_id][treatment] - means[eval_id][baseline] for eval_id in paired_ids]
    estimate = mean(deltas)
    rng = random.Random(seed)
    bootstrapped = [
        mean(rng.choice(deltas) for _ in deltas) for _ in range(bootstrap_samples)
    ]
    return {
        "metric": metric,
        "treatment": treatment,
        "baseline": baseline,
        "paper_count": len(paired_ids),
        "estimate": estimate,
        "ci95": [_percentile(bootstrapped, 0.025), _percentile(bootstrapped, 0.975)],
        "ci_method": "paired_paper_percentile_bootstrap",
        "bootstrap_samples": bootstrap_samples,
        "seed": seed,
        "paper_deltas": dict(zip(paired_ids, deltas, strict=True)),
        "excluded_incomplete_papers": [
            eval_id for eval_id in all_ids if eval_id not in paired_ids
        ],
    }
