"""Session-wide tracker for Layer-1 executor retries (the coding agent's code cells).

The innermost of the three execution-control loops (``config.py:135-153``): a code
cell raises, times out, or the kernel is unreachable, and the coding agent tries
again. Its counter — ``_exec_state["consecutive_errors"]`` in
``coding_agent/model.py`` — is **reset on every success and at the start of every
step**, so at run end it holds no history at all. Nothing else records the loop:
``usage_tracker`` counts LLM calls, not executions.

This module accumulates the history that counter destroys, from the same
structured ``ExecutionResult.error`` flag the retry logic itself uses
(``sandbox.py:67``) — no sniffing of traceback text, and immune to the
``MAX_OUTPUT_CHARS`` truncation that can hide an exception type.

Definitions, chosen so a raw failure count can't be mistaken for a diagnosis:

* **episode** — one unbroken run of failures: the agent hit an error and started
  trying to fix it. This, not the raw failure count, is the unit comparable to
  the other two layers' "attempts" — five failures while fixing one bug is one
  debugging attempt, not five.
* **recovered** — an episode that ended in a success *within the same step*.
  Distinguishes "erred twice then got it right" from "erred twice and gave up".
* **max_consecutive** — the deepest hole dug in any one step; the number that
  approaches ``MAX_EXECUTOR_RETRIES``.
* **limit_hits** — steps where the consecutive budget was actually spent, which
  is when the agent is told to stop running code and hand back.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class StepExecMetrics:
    """Per-plan-step execution counts."""

    step_id: int | None
    executions: int = 0
    failures: int = 0
    episodes: int = 0
    max_consecutive: int = 0
    limit_hits: int = 0


@dataclass
class ExecutorTracker:
    """Thread-safe accumulator for code-execution outcomes across a run."""

    executions: int = 0
    failures: int = 0
    episodes: int = 0
    recovered: int = 0
    limit_hits: int = 0
    max_consecutive: int = 0
    by_language: dict[str, dict[str, int]] = field(default_factory=dict)
    steps: dict[object, StepExecMetrics] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive = 0
        self._limit = None  # resolved lazily from config

    # -- recording ---------------------------------------------------------

    def begin_step(self) -> None:
        """Clear the consecutive-failure run at a step boundary.

        Mirrors the reset in ``coding_agent/model.py`` (the tool closures persist
        across invocations). A run of failures interrupted by a *step* boundary
        is not a recovery — nothing was fixed, the manager moved on.
        """
        with self._lock:
            self._consecutive = 0

    def record_execution(self, language: str, error: bool, step_id=None) -> None:
        """Record one code execution and whether it failed."""
        if self._limit is None:
            try:
                from config import MAX_EXECUTOR_RETRIES

                self._limit = MAX_EXECUTOR_RETRIES
            except Exception:
                self._limit = 15

        with self._lock:
            self.executions += 1
            lang = self.by_language.setdefault(language, {"executions": 0, "failures": 0})
            lang["executions"] += 1

            step = self.steps.get(step_id)
            if step is None:
                step = self.steps[step_id] = StepExecMetrics(step_id=step_id)
            step.executions += 1

            if error:
                self.failures += 1
                lang["failures"] += 1
                step.failures += 1
                if self._consecutive == 0:
                    # First failure after a success (or at a step boundary):
                    # a new debugging episode begins.
                    self.episodes += 1
                    step.episodes += 1
                self._consecutive += 1
                self.max_consecutive = max(self.max_consecutive, self._consecutive)
                step.max_consecutive = max(step.max_consecutive, self._consecutive)
                if self._consecutive == self._limit:
                    # Count the moment the budget is spent, once per run of
                    # failures — not once per execution beyond it.
                    self.limit_hits += 1
                    step.limit_hits += 1
            else:
                if self._consecutive > 0:
                    self.recovered += 1
                self._consecutive = 0

    def reset(self) -> None:
        """Clear all accumulated metrics. Called at the start of each run."""
        with self._lock:
            self.executions = 0
            self.failures = 0
            self.episodes = 0
            self.recovered = 0
            self.limit_hits = 0
            self.max_consecutive = 0
            self.by_language = {}
            self.steps = {}
            self._consecutive = 0

    # -- reporting ---------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize for the run's metrics.json."""
        with self._lock:
            steps = [
                {
                    "step_id": s.step_id,
                    "executions": s.executions,
                    "failures": s.failures,
                    "episodes": s.episodes,
                    "max_consecutive": s.max_consecutive,
                    "limit_hits": s.limit_hits,
                }
                # ``None`` (an execution outside any plan step) sorts first.
                for s in sorted(self.steps.values(), key=lambda s: (s.step_id is not None, s.step_id))
            ]
            return {
                "executions": self.executions,
                "failures": self.failures,
                "successes": self.executions - self.failures,
                "episodes": self.episodes,
                "recovered": self.recovered,
                "limit_hits": self.limit_hits,
                "max_consecutive": self.max_consecutive,
                "by_language": dict(self.by_language),
                "by_step": steps,
            }


executor_tracker = ExecutorTracker()
