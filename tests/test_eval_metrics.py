"""Self-contained tests for the eval_registry metric registry and built-in metrics.

Run from the repo root::

    cd src && python ../tests/test_eval_metrics.py

Deliberately pytest-free (matching the other tests in this directory) so it runs before the
project commits to a test framework. Pure and deterministic — no graph, no LLM, no external
data.
"""

import math
import sys
import tempfile
from pathlib import Path

import pandas as pd

from eval_registry.metrics import (
    REGISTRY,
    evaluate_threshold,
    get_metric,
    metric,
    score,
)

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        _failures.append(msg)


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def expect_raises(exc_type, fn, msg: str) -> None:
    try:
        fn()
    except exc_type:
        print(f"  ok: {msg}")
        return
    except Exception as e:  # wrong exception type
        print(f"  FAIL: {msg} (raised {type(e).__name__})")
        _failures.append(msg)
        return
    print(f"  FAIL: {msg} (no exception)")
    _failures.append(msg)


# --- registry core --------------------------------------------------------


def test_registry_core():
    print("test_registry_core")
    for name in [
        "file_exists", "csv_nonempty", "ari", "f1_macro",
        "abundance_jsd", "mean_prediction_confidence",
    ]:
        check(name in REGISTRY, f"{name} registered on import")

    expect_raises(KeyError, lambda: get_metric("nope"), "get_metric unknown raises KeyError")

    def dup():
        @metric("file_exists", kind="artifact")
        def _d():
            return True

    expect_raises(ValueError, dup, "duplicate registration raises")

    def bad_kind():
        @metric("bogus_kind_metric", kind="not_a_kind")
        def _b():
            return 0.0

    expect_raises(ValueError, bad_kind, "unknown kind raises")


# --- threshold evaluation -------------------------------------------------


def test_thresholds():
    print("test_thresholds")
    cases = [
        (0.7, {"gte": 0.6}, True),
        (0.5, {"gte": 0.6}, False),
        (0.1, {"lte": 0.15}, True),
        (0.2, {"lte": 0.15}, False),
        (True, {"eq": True}, True),
        (False, {"eq": True}, False),
        (0.5, None, None),
        (0.5, {}, None),
    ]
    for value, thr, expected in cases:
        check(evaluate_threshold(value, thr) is expected, f"threshold {value} {thr} -> {expected}")

    expect_raises(ValueError, lambda: evaluate_threshold(0.5, {"gte": 1, "lte": 2}),
                  "two-key threshold raises")
    expect_raises(ValueError, lambda: evaluate_threshold(0.5, {"weird": 1}),
                  "unknown operator raises")


# --- composition ----------------------------------------------------------


def test_composition():
    print("test_composition")
    pred = ["A", "A", "B", "B"]
    truth = ["A", "A", "B", "B"]
    check(approx(get_metric("ari").fn(pred, truth), 1.0), "ari perfect = 1.0")

    res = score("ari", pred, truth, threshold={"gte": 0.6})
    check(approx(res.value, 1.0) and res.passed is True and res.error is None,
          "score() ari passes threshold")

    check(approx(get_metric("f1_macro").fn(pred, truth), 1.0), "f1_macro perfect = 1.0")

    df = pd.DataFrame({"T": [0.5, 0.2], "B": [0.5, 0.8]}, index=["s1", "s2"])
    check(approx(get_metric("abundance_jsd").fn(df, df.copy()), 0.0), "jsd identical = 0")

    # Same compositions as pred, but rows and columns supplied in a different order,
    # plus an extra column the metric must drop. After alignment JSD must be 0.
    #   pred:  s1 -> T=0.9,B=0.1 ; s2 -> T=0.1,B=0.9
    pred_df = pd.DataFrame({"T": [0.9, 0.1], "B": [0.1, 0.9]}, index=["s1", "s2"])
    golden = pd.DataFrame(
        {"B": [0.9, 0.1], "T": [0.1, 0.9], "X": [1.0, 1.0]},  # rows are s2 then s1
        index=["s2", "s1"],
    )
    check(approx(get_metric("abundance_jsd").fn(pred_df, golden), 0.0),
          "jsd aligns rows/cols + drops extras = 0")

    r = score("abundance_jsd", pd.DataFrame({"T": [1.0]}, index=["a"]),
              pd.DataFrame({"B": [1.0]}, index=["z"]), threshold={"lte": 0.15})
    check(r.error is not None and math.isnan(r.value), "jsd no-overlap captured as error")


# --- confidence -----------------------------------------------------------


def test_confidence():
    print("test_confidence")
    check(approx(get_metric("mean_prediction_confidence").fn([1.0, 0.5, 0.0]), 0.5),
          "mean confidence = 0.5")
    check(approx(get_metric("frac_low_confidence").fn([0.9, 0.4, 0.3, 0.8], 0.5), 0.5),
          "frac_low_confidence = 0.5")


# --- coverage -------------------------------------------------------------


def test_coverage():
    print("test_coverage")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        p = tmp / "out.txt"
        check(get_metric("file_exists").fn(p) is False, "file_exists false when absent")
        p.write_text("hi")
        check(get_metric("file_exists").fn(p) is True, "file_exists true when present")

        fn = get_metric("csv_nonempty").fn
        (tmp / "empty.csv").write_text("c1,c2\n")
        (tmp / "full.csv").write_text("c1,c2\n1,2\n")
        check(fn(tmp / "empty.csv") is False, "csv_nonempty false header-only")
        check(fn(tmp / "full.csv") is True, "csv_nonempty true with data")
        check(fn(tmp / "missing.csv") is False, "csv_nonempty false missing")

        (tmp / "rows.csv").write_text("a,b\n1,2\n3,4\n\n5,6\n")
        check(get_metric("row_count").fn(tmp / "rows.csv") == 3.0, "row_count ignores blank lines")


def main() -> int:
    test_registry_core()
    test_thresholds()
    test_composition()
    test_confidence()
    test_coverage()
    print()
    if _failures:
        print(f"FAILED: {len(_failures)} check(s)")
        return 1
    print("All eval_registry metric tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
