"""The no-progress (repeat) budget stops a successful-but-looping executor.

The two error budgets only see *failures*. A step whose executions succeed but
make no progress — most often re-running byte-for-byte the same cell — trips
neither, so it spins until the recursion limit aborts the step and discards its
context. ``apply_repeat_budget`` counts executions of each normalized code string
and stops at ``MAX_EXECUTOR_REPEATS``.
"""

from config import MAX_EXECUTOR_REPEATS
from agents.agent_registry.coding_agent.model import (
    apply_repeat_budget,
    new_exec_state,
)


def test_identical_code_trips_at_the_limit():
    state = new_exec_state()
    code = "print(sc.pl.umap(adata))"
    notices = [apply_repeat_budget(state, code) for _ in range(MAX_EXECUTOR_REPEATS)]
    # None until the Nth identical execution, then a stop-directive.
    assert notices[:-1] == [None] * (MAX_EXECUTOR_REPEATS - 1)
    assert notices[-1] is not None
    assert "REPEAT LIMIT" in notices[-1]


def test_whitespace_variants_count_as_the_same_code():
    state = new_exec_state()
    variants = ["a = 1\nprint(a)", "a = 1\n   print(a)  ", "a  =  1\nprint(a)\n"]
    # Three whitespace-different spellings of the same cell. With the limit at 4,
    # a fourth identical-after-normalization run should trip.
    for c in variants:
        assert apply_repeat_budget(state, c) is None
    assert apply_repeat_budget(state, "a = 1\nprint(a)") is not None


def test_distinct_code_never_trips():
    state = new_exec_state()
    for i in range(MAX_EXECUTOR_REPEATS * 3):
        assert apply_repeat_budget(state, f"print({i})") is None


def test_empty_code_is_ignored():
    state = new_exec_state()
    for _ in range(MAX_EXECUTOR_REPEATS + 2):
        assert apply_repeat_budget(state, "   \n  ") is None


def test_counts_reset_between_steps():
    state = new_exec_state()
    code = "run()"
    for _ in range(MAX_EXECUTOR_REPEATS - 1):
        apply_repeat_budget(state, code)
    state.update(new_exec_state())  # what _agent_invocation_tool does per step
    assert apply_repeat_budget(state, code) is None
