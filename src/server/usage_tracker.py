"""Session-wide usage tracker for API tokens and wall-clock time per agent and per plan step.

Provides a thread-safe singleton that accumulates token counts (input/output) and elapsed time for
each LLM invocation, attributed to the calling agent and (when applicable) the plan step that the
agent is executing on behalf of the manager.

Timing covers only the wall-clock duration of ``agent_model.invoke()`` calls. Time the planner
spends waiting for user input/confirmation in copilot mode is therefore naturally excluded — copilot
pauses live between graph invocations, not inside them.
"""

import threading
from dataclasses import dataclass


@dataclass
class AgentMetrics:
    """Per-agent accumulated metrics across a session."""

    input_tokens: int = 0
    output_tokens: int = 0
    time_seconds: float = 0.0
    llm_calls: int = 0


@dataclass
class StepMetrics:
    """Per-plan-step accumulated metrics across a session."""

    step_id: int
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    time_seconds: float = 0.0
    llm_calls: int = 0


class UsageTracker:
    """Thread-safe accumulator for per-agent and per-step API usage metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.agents: dict[str, AgentMetrics] = {}
        self.steps: dict[int, StepMetrics] = {}

    def record_llm_call(
        self,
        agent_name: str,
        step_id: int | None,
        usage_metadata: dict | None,
        elapsed_seconds: float,
    ) -> None:
        """Record one LLM call's token usage and elapsed wall-clock time.

        ``usage_metadata`` is LangChain's cross-provider ``AIMessage.usage_metadata`` dict, with
        ``input_tokens`` / ``output_tokens`` keys populated for both Anthropic and OpenAI chat
        models. ``None`` (or a missing key) is treated as zero rather than raising — some retry
        wrappers strip metadata on failure paths.
        """
        meta = usage_metadata or {}
        input_tokens = int(meta.get("input_tokens", 0) or 0)
        output_tokens = int(meta.get("output_tokens", 0) or 0)

        with self._lock:
            agent = self.agents.setdefault(agent_name, AgentMetrics())
            agent.input_tokens += input_tokens
            agent.output_tokens += output_tokens
            agent.time_seconds += elapsed_seconds
            agent.llm_calls += 1

            if step_id is not None:
                step = self.steps.setdefault(
                    step_id, StepMetrics(step_id=step_id, agent_name=agent_name)
                )
                step.input_tokens += input_tokens
                step.output_tokens += output_tokens
                step.time_seconds += elapsed_seconds
                step.llm_calls += 1

    def reset(self) -> None:
        """Clear all accumulated metrics. Called on session reset."""
        with self._lock:
            self.agents.clear()
            self.steps.clear()

    def to_dict(self) -> dict:
        """Serialize for JSON transport.

        Steps are returned as a list sorted by ``step_id`` so the UI gets stable ordering without
        having to re-sort. Times are rounded to 2 decimals; token counts are exact.
        """
        with self._lock:
            agents = {
                name: {
                    "input_tokens": m.input_tokens,
                    "output_tokens": m.output_tokens,
                    "time_seconds": round(m.time_seconds, 2),
                    "llm_calls": m.llm_calls,
                }
                for name, m in self.agents.items()
            }
            steps = [
                {
                    "step_id": s.step_id,
                    "agent_name": s.agent_name,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "time_seconds": round(s.time_seconds, 2),
                    "llm_calls": s.llm_calls,
                }
                for s in sorted(self.steps.values(), key=lambda s: s.step_id)
            ]
            return {"agents": agents, "steps": steps}


usage_tracker = UsageTracker()
