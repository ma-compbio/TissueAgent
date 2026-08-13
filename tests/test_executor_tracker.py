"""Tests for Layer-1 executor accounting (server/executor_tracker.py).

Run from the repo root::

    cd src && python ../tests/test_executor_tracker.py

The coding agent's own counter is reset on every success and every step, so by
run end it holds nothing. These tests pin the history the tracker keeps in its
place — in particular that a *recovery* (failures then a success in the same
step) is distinguished from failures that a step boundary merely interrupted.

Deliberately pytest-free (matching the other tests in this directory).
"""

import sys

from server.executor_tracker import executor_tracker

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        _failures.append(msg)


def run(*outcomes, step_id=1, language="python") -> dict:
    """Record a sequence of executions; True means the cell failed."""
    executor_tracker.reset()
    for failed in outcomes:
        executor_tracker.record_execution(language, failed, step_id)
    return executor_tracker.to_dict()


def test_counts():
    print("test_counts")
    d = run(False, True, False, True, True)
    check(d["executions"] == 5, "every execution counted")
    check(d["failures"] == 3, "failures counted from the structured error flag")
    check(d["successes"] == 2, "successes = executions - failures")


def test_recovery():
    print("test_recovery")
    # Erred twice, then got it right: one recovery, hole depth 2.
    d = run(True, True, False)
    check(d["recovered"] == 1, "a failure run ending in success counts as one recovery")
    check(d["max_consecutive"] == 2, "deepest consecutive run recorded")

    # Two separate holes, both climbed out of.
    d = run(True, False, True, True, False)
    check(d["recovered"] == 2, "each distinct failure run counts once")
    check(d["max_consecutive"] == 2, "max is the deepest hole, not the total")

    # Never recovered — the run ended in failure.
    d = run(True, True)
    check(d["recovered"] == 0, "unrecovered failures are not counted as recoveries")

    d = run(False, False)
    check(d["recovered"] == 0, "successes with no preceding failure are not recoveries")


def test_step_boundary_is_not_a_recovery():
    print("test_step_boundary_is_not_a_recovery")
    # A step that ends mid-failure and is followed by a fresh step: nothing was
    # fixed, so the success in step 2 must not be credited as a recovery of
    # step 1's failures.
    executor_tracker.reset()
    executor_tracker.record_execution("python", True, 1)
    executor_tracker.record_execution("python", True, 1)
    executor_tracker.begin_step()
    executor_tracker.record_execution("python", False, 2)
    d = executor_tracker.to_dict()
    check(d["recovered"] == 0, "a step boundary clears the run without crediting a recovery")
    check(d["max_consecutive"] == 2, "the failure depth from step 1 is still recorded")


def test_episodes_are_the_comparable_unit():
    print("test_episodes_are_the_comparable_unit")
    # Five failures spent fixing one bug is ONE debugging attempt, not five —
    # this is the unit that lines up with a manager retry or a replan.
    d = run(True, True, True, True, True, False)
    check(d["failures"] == 5, "raw failed executions still counted")
    check(d["episodes"] == 1, "one unbroken failure run is one episode")
    check(d["recovered"] == 1, "the episode was recovered")

    d = run(True, False, True, False, True, False)
    check(d["episodes"] == 3, "each failure run after a success is a new episode")
    check(d["recovered"] == 3, "all three recovered")

    d = run(False, False, False)
    check(d["episodes"] == 0, "a clean run has no debugging episodes")

    # A step boundary starts a new episode: it is separate trouble, not the
    # continuation of the abandoned one.
    executor_tracker.reset()
    executor_tracker.record_execution("python", True, 1)
    executor_tracker.begin_step()
    executor_tracker.record_execution("python", True, 2)
    d = executor_tracker.to_dict()
    check(d["episodes"] == 2, "failures either side of a step boundary are separate episodes")


def test_limit_hits():
    print("test_limit_hits")
    from config import MAX_EXECUTOR_RETRIES

    d = run(*([True] * MAX_EXECUTOR_RETRIES))
    check(d["limit_hits"] == 1, "spending the whole budget counts as one limit hit")

    # Failures past the limit must not each re-count the same exhausted budget.
    d = run(*([True] * (MAX_EXECUTOR_RETRIES + 3)))
    check(d["limit_hits"] == 1, "further failures in the same run don't re-count the hit")

    d = run(*([True] * (MAX_EXECUTOR_RETRIES - 1)), False)
    check(d["limit_hits"] == 0, "recovering one short of the budget is not a limit hit")


def test_breakdowns():
    print("test_breakdowns")
    executor_tracker.reset()
    executor_tracker.record_execution("python", False, 1)
    executor_tracker.record_execution("python", True, 2)
    executor_tracker.record_execution("r", True, 2)
    executor_tracker.record_execution("python", False, None)  # outside any plan step
    d = executor_tracker.to_dict()
    check(d["by_language"]["python"] == {"executions": 3, "failures": 1}, "per-language counts kept")
    check(d["by_language"]["r"] == {"executions": 1, "failures": 1}, "R executions tracked too")
    steps = {s["step_id"]: s for s in d["by_step"]}
    check(set(steps) == {None, 1, 2}, "per-step rows, including un-attributed executions")
    check(steps[2]["failures"] == 2, "failures attributed to the dispatching step")
    check(d["by_step"][0]["step_id"] is None, "un-attributed row sorts first without a type error")


def test_reset():
    print("test_reset")
    run(True, True, False)
    executor_tracker.reset()
    d = executor_tracker.to_dict()
    check(d["executions"] == 0 and d["failures"] == 0, "reset clears totals")
    check(d["by_step"] == [] and d["by_language"] == {}, "reset clears breakdowns")
    # A stale consecutive run must not leak into the next run's first success.
    executor_tracker.record_execution("python", False, 1)
    check(executor_tracker.to_dict()["recovered"] == 0, "reset clears the consecutive-failure run")


def main() -> int:
    test_counts()
    test_recovery()
    test_step_boundary_is_not_a_recovery()
    test_episodes_are_the_comparable_unit()
    test_limit_hits()
    test_breakdowns()
    test_reset()
    executor_tracker.reset()

    print()
    if _failures:
        print(f"{len(_failures)} FAILURE(S):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
