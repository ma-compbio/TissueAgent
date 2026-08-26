"""The executor failure budget must survive interleaved successes.

``MAX_EXECUTOR_RETRIES`` counts *consecutive* failures and is zeroed by any
success, so it never fires on the failure mode that actually kills runs: a
debug-thrash loop (execute -> fail -> glob -> read -> execute -> fail ...).
Such a step ran until LangGraph's ``recursion_limit`` aborted it, discarding the
sub-agent's context and its partial work. ``MAX_EXECUTOR_STEP_ERRORS`` is the
per-step ceiling that stops it.

Observed in logs/2026-08-13_22-30-50: 52 python executions, 33 errors, two
``GraphRecursionError``s — and the consecutive guard never once fired.
"""

from config import MAX_EXECUTOR_RETRIES, MAX_EXECUTOR_STEP_ERRORS
from agents.agent_registry.coding_agent.model import (
    apply_failure_budgets,
    new_exec_state,
)


def _drive(failures: list[bool]) -> tuple[str | None, int]:
    """Feed a pass/fail sequence through the budgets.

    Returns the first stop-directive and the 1-based execution that produced it,
    or ``(None, len(failures))`` if no budget tripped.
    """
    state = new_exec_state()
    for i, had_error in enumerate(failures, start=1):
        notice = apply_failure_budgets(state, had_error=had_error)
        if notice is not None:
            return notice, i
    return None, len(failures)


def test_unbroken_failure_streak_trips_the_fast_guard() -> None:
    """A hard stuck loop still fails fast on the consecutive budget."""
    notice, at = _drive([True] * (MAX_EXECUTOR_RETRIES + 10))
    assert notice is not None
    assert "consecutive" in notice
    assert at == MAX_EXECUTOR_RETRIES


def test_interleaved_successes_no_longer_grant_unlimited_retries() -> None:
    """fail/succeed thrash must terminate — this is the regression under test."""
    # Never two failures in a row, so ``consecutive_errors`` never exceeds 1
    # and the old guard could not fire no matter how long this ran.
    notice, at = _drive([True, False] * (MAX_EXECUTOR_STEP_ERRORS + 20))
    assert notice is not None, "thrash loop ran without tripping any budget"
    assert "during this step" in notice
    assert "do not refund" in notice
    # Trips on the Nth failure, which is every other execution.
    assert at == MAX_EXECUTOR_STEP_ERRORS * 2 - 1


def test_consecutive_counter_is_still_reset_by_success() -> None:
    """The fast guard keeps its streak semantics; only the step budget is absolute."""
    state = new_exec_state()
    for _ in range(MAX_EXECUTOR_RETRIES - 1):
        assert apply_failure_budgets(state, had_error=True) is None
    assert apply_failure_budgets(state, had_error=False) is None
    assert state["consecutive_errors"] == 0
    # Failures accumulated before the success are NOT refunded.
    assert state["step_errors"] == MAX_EXECUTOR_RETRIES - 1


def test_healthy_debugging_is_not_penalised() -> None:
    """A step that fails a few times, then works, must not trip anything."""
    notice, _ = _drive([True] * (MAX_EXECUTOR_RETRIES - 1) + [False] * 30)
    assert notice is None


def test_budgets_reset_between_step_invocations() -> None:
    """Budgets are per step: a fresh invocation starts clean."""
    state = new_exec_state()
    for _ in range(MAX_EXECUTOR_STEP_ERRORS - 1):
        apply_failure_budgets(state, had_error=True)
    assert state["step_errors"] == MAX_EXECUTOR_STEP_ERRORS - 1

    state.update(new_exec_state())  # what _agent_invocation_tool does per step
    assert state["step_errors"] == 0
    assert apply_failure_budgets(state, had_error=True) is None


def test_step_ceiling_sits_above_the_consecutive_one() -> None:
    """A legitimately long debug session must hit the fast guard first."""
    assert MAX_EXECUTOR_STEP_ERRORS > MAX_EXECUTOR_RETRIES
