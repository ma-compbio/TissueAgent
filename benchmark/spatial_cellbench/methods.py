"""Direct and CellVoyager-style generation methods."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Protocol

from pydantic import BaseModel

from benchmark.spatial_cellbench.prompts import (
    DIRECT_SYSTEM,
    SPATIAL_CRITIC_SYSTEM,
    SPATIAL_EXPERT_SYSTEM,
    cv_critic_prompt,
    cv_draft_prompt,
    cv_revision_prompt,
    direct_prompt,
)
from benchmark.spatial_cellbench.schemas import (
    AnalysisProposal,
    CVAnalysis,
    ProposalSet,
    PublicContext,
    proposal_set_schema,
    validate_proposal_count,
)

LENGTH_FINISH_MAX_RETRIES = 0


def register_benchmark_models() -> None:
    """Register paper-protocol models in this process without changing the global catalog."""
    src = Path(__file__).resolve().parents[2] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    import models

    additions = (
        models.ModelSpec(
            id="o3-mini",
            provider="openai",
            api_model="o3-mini",
            label="o3-mini (Spatial CellBench)",
            reasoning_effort="medium",
        ),
        models.ModelSpec(
            id="gpt-4o",
            provider="openai",
            api_model="gpt-4o",
            label="GPT-4o (Spatial CellBench judge)",
        ),
    )
    for spec in additions:
        existing = models._MODELS_BY_ID.get(spec.id)
        if existing is not None and existing != spec:
            raise ValueError(f"Global model definition conflicts with benchmark model {spec.id}")
        models._MODELS_BY_ID[spec.id] = spec


class ModelCall(Protocol):
    """Small interface shared by real and deterministic test callers."""

    def structured(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Return one schema-validated response."""

    def text(self, stage: str, system_prompt: str, user_prompt: str) -> str:
        """Return one plain-text response."""


@dataclass(frozen=True)
class CallTrace:
    """Provider-neutral timing and token trace for one call."""

    stage: str
    kind: str
    elapsed_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class LangChainModelCall:
    """Invoke one configured model without model or semantic fallbacks."""

    def __init__(self, model_id: str) -> None:
        """Create one reusable model client."""
        from models import build_chat_model
        from server.rate_limit import with_header_retry

        register_benchmark_models()
        self.model_id = model_id
        self._model = with_header_retry(build_chat_model(model_id), max_attempts=6)
        self._chains: dict[type[BaseModel], object] = {}
        self._traces: list[CallTrace] = []
        self._failed_attempts: list[dict] = []

    @property
    def call_count(self) -> int:
        """Return successful provider calls."""
        return len(self._traces)

    @property
    def traces(self) -> list[dict]:
        """Return JSON-serializable call traces."""
        return [asdict(trace) for trace in self._traces]

    @property
    def observable_attempt_count(self) -> int:
        """Return successful and failed outer attempts."""
        return len(self._traces) + len(self._failed_attempts)

    @property
    def failed_attempts(self) -> list[dict]:
        """Return failed outer-attempt metadata."""
        return [dict(attempt) for attempt in self._failed_attempts]

    @property
    def length_retry_count(self) -> int:
        """Return zero; the benchmark performs no semantic retry or fallback."""
        return 0

    @staticmethod
    def _usage(message) -> tuple[int | None, int | None, int | None]:
        usage = getattr(message, "usage_metadata", None) or {}
        response = getattr(message, "response_metadata", None) or {}
        provider_usage = response.get("token_usage", {}) if isinstance(response, dict) else {}
        return (
            usage.get("input_tokens", provider_usage.get("prompt_tokens")),
            usage.get("output_tokens", provider_usage.get("completion_tokens")),
            usage.get("total_tokens", provider_usage.get("total_tokens")),
        )

    def _record(self, stage: str, kind: str, started: float, message) -> None:
        input_tokens, output_tokens, total_tokens = self._usage(message)
        self._traces.append(
            CallTrace(
                stage=stage,
                kind=kind,
                elapsed_seconds=time.perf_counter() - started,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        )

    def _record_failure(self, stage: str, kind: str, started: float, exc: Exception) -> None:
        self._failed_attempts.append(
            {
                "stage": stage,
                "kind": kind,
                "elapsed_seconds": time.perf_counter() - started,
                "error_type": type(exc).__name__,
            }
        )

    def structured(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Invoke one structured-output stage."""
        chain = self._chains.get(schema)
        if chain is None:
            chain = self._model.with_structured_output(schema, include_raw=True)
            self._chains[schema] = chain
        started = time.perf_counter()
        try:
            result = chain.invoke([("system", system_prompt), ("human", user_prompt)])
        except Exception as exc:
            self._record_failure(stage, "structured", started, exc)
            raise
        self._record(stage, "structured", started, result["raw"])
        if result["parsed"] is None:
            raise ValueError(f"Structured model output failed at stage {stage}")
        return schema.model_validate(result["parsed"])

    def text(self, stage: str, system_prompt: str, user_prompt: str) -> str:
        """Invoke one unstructured stage."""
        started = time.perf_counter()
        try:
            message = self._model.invoke(
                [("system", system_prompt), ("human", user_prompt)]
            )
        except Exception as exc:
            self._record_failure(stage, "text", started, exc)
            raise
        self._record(stage, "text", started, message)
        if isinstance(message.content, str):
            return message.content
        if isinstance(message.content, list):
            return "\n".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in message.content
            ).strip()
        return str(message.content)


def run_direct(public: PublicContext, count: int, caller: ModelCall) -> ProposalSet:
    """Run the one-call oracle-N baseline."""
    schema = proposal_set_schema(count)
    result = caller.structured(
        "direct",
        DIRECT_SYSTEM,
        direct_prompt(public.context, count),
        schema,
    )
    return validate_proposal_count(result, count)


def run_spatial_cv(
    public: PublicContext,
    overview: str,
    count: int,
    caller: ModelCall,
) -> ProposalSet:
    """Run N sequential Spatial-CV draft, critic, and revision cycles."""
    proposals = []
    past_analyses = ""
    for index in range(1, count + 1):
        draft = CVAnalysis.model_validate(
            caller.structured(
                f"spatial_cv_{index:02d}_draft",
                SPATIAL_EXPERT_SYSTEM,
                cv_draft_prompt(public.context, past_analyses, overview),
                CVAnalysis,
            )
        )
        feedback = caller.text(
            f"spatial_cv_{index:02d}_critic",
            SPATIAL_CRITIC_SYSTEM,
            cv_critic_prompt(public.context, draft, past_analyses, overview),
        )
        revised = CVAnalysis.model_validate(
            caller.structured(
                f"spatial_cv_{index:02d}_revision",
                SPATIAL_EXPERT_SYSTEM,
                cv_revision_prompt(public.context, draft, feedback, past_analyses, overview),
                CVAnalysis,
            )
        )
        proposals.append(AnalysisProposal(title=revised.title, summary=revised.summary))
        past_analyses += revised.summary + "\n\n"
    return validate_proposal_count({"proposals": proposals}, count)
