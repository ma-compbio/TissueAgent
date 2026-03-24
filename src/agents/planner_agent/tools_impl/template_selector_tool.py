"""Tool that scores plan templates against a user query and recommends USE, ADAPT, or NEW."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

# Get the default registry directory relative to this file
DEFAULT_REGISTRY_DIR = Path(__file__).parent.parent / "plan_registry"


# ---------- internals ----------

_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "by",
    "with",
    "from",
    "at",
    "between",
    "into",
    "over",
    "about",
    "as",
    "is",
    "are",
    "be",
    "this",
    "that",
    "these",
    "those",
    "using",
    "use",
    "based",
    "figure",
    "plot",
    "result",
    "results",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens, excluding stop words."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


def _jaccard(a: List[str], b: List[str]) -> float:
    """Compute Jaccard similarity between two token lists."""
    A, B = set(a), set(b)
    if not A and not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))


def _recency_score(last_updated: Optional[str]) -> float:
    """Return a [0,1] score that decays with age from a YYYY-MM-DD date string."""
    if not last_updated:
        return 0.5
    try:
        dt = datetime.strptime(last_updated, "%Y-%m-%d")
    except Exception:
        return 0.5
    days = max(0, (datetime.utcnow() - dt).days)
    return max(0.0, min(1.0, 1.0 / (1.0 + days / 365.0)))


def _load_templates(registry_dir: Path) -> List[Dict[str, Any]]:
    """Load all YAML plan templates from the given directory."""
    if not registry_dir.exists():
        return []
    docs: List[Dict[str, Any]] = []
    for p in sorted(registry_dir.glob("*.yaml")):
        docs.append(yaml.safe_load(p.read_text()))
    return docs


def _score_template(
    tpl: Dict[str, Any],
    query_text: str,
    inputs_available: Optional[List[str]],
    weights: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """Compute a weighted relevance score for a single template against a query."""
    q = _tokens(query_text)
    tags_text = " ".join(str(x) for x in tpl.get("tags", []))
    io_text = (
        " ".join(str(x) for x in tpl.get("inputs", []))
        + " "
        + " ".join(str(x) for x in tpl.get("outputs", []))
    )
    tag_toks = _tokens(tags_text)
    key_toks = _tokens(f"{tpl.get('title', '')} {tpl.get('step_sketch', '')} {io_text}")

    s_tags = _jaccard(q, tag_toks)
    s_keywords = _jaccard(q, key_toks)

    s_io = 0.5
    if inputs_available:
        avail = {a.lower() for a in inputs_available}
        reqs = {str(r).lower() for r in tpl.get("inputs", [])}
        if reqs:
            matched = sum(any(r in a or a in r for a in avail) for r in reqs)
            s_io = matched / max(1, len(reqs))

    s_recency = _recency_score(
        str(tpl.get("last_updated", "")) if tpl.get("last_updated") else None
    )

    total = (
        weights["tags"] * s_tags
        + weights["keywords"] * s_keywords
        + weights["io"] * s_io
        + weights["recency"] * s_recency
    )
    return total, {
        "tags": s_tags,
        "keywords": s_keywords,
        "io": s_io,
        "recency": s_recency,
    }


# ---------- tool ----------


class TemplateSelectorArgs(BaseModel):
    """Input schema for the template selector tool."""

    query_text: str = Field(..., description="User's task description.")
    registry_dir: str = Field(
        default=str(DEFAULT_REGISTRY_DIR), description="Directory of YAML templates."
    )
    inputs_available: Optional[List[str]] = Field(
        default=None,
        description='Optional hints like ["AnnData(.h5ad)", "obsm:spatial", "obs:x,y"].',
    )


def _template_selector_tool(
    *,
    query_text: str,
    registry_dir: str = None,
    inputs_available: Optional[List[str]] = None,
) -> str:
    """Decide whether to USE an existing template, ADAPT one, or create a NEW plan.

    Returns a JSON string with keys: decision, template_id, score, scores, why, ranked.
    """
    if registry_dir is None:
        registry_dir = str(DEFAULT_REGISTRY_DIR)

    weights = {"tags": 0.40, "keywords": 0.40, "io": 0.10, "recency": 0.10}
    thresholds = {"high": 0.2, "mid": 0.15}

    templates = _load_templates(Path(registry_dir))
    if not templates:
        return json.dumps(
            {
                "decision": "NEW",
                "template_id": None,
                "score": 0.0,
                "scores": {},
                "why": "No templates in registry",
                "ranked": [],
            },
            indent=2,
        )

    scored = []
    for t in templates:
        total, comps = _score_template(t, query_text, inputs_available, weights)
        scored.append((t, total, comps))
    scored.sort(key=lambda x: x[1], reverse=True)

    top_tpl, top_score, comps = scored[0]
    high, mid = thresholds["high"], thresholds["mid"]

    if top_score >= high:
        decision, why = "USE", f"Strong match (score={top_score:.2f})."
    elif top_score >= mid:
        decision, why = (
            "ADAPT",
            f"Partial match (score={top_score:.2f}); adapt parameters/IO.",
        )
    else:
        decision, why = (
            "NEW",
            f"No sufficient match (score={top_score:.2f}); create new plan.",
        )

    ranked = [(t.get("template_id", "<missing_id>"), round(s, 3)) for t, s, _ in scored[:5]]

    return json.dumps(
        {
            "decision": decision,
            "template_id": top_tpl.get("template_id") if decision in {"USE", "ADAPT"} else None,
            "score": round(top_score, 3),
            "scores": {k: round(v, 3) for k, v in comps.items()},
            "why": why,
            "ranked": ranked,
        },
        indent=2,
    )


template_selector_tool = StructuredTool.from_function(
    name="template_selector_tool",
    func=_template_selector_tool,
    args_schema=TemplateSelectorArgs,
    description=(
        "Score templates in the plan registry against a user query and return a decision: "
        "USE (strong match), ADAPT (closest), or NEW (no match). Includes rationale and top candidates."
    ),
    return_direct=False,
)
