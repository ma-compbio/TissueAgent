"""LLM-judge recovery scoring for the hypothesis-recovery prototype.

Reads a generated `hypotheses.json` and the withheld `ground_truth.md`, then
asks an LLM to score recovery against the rubric encoded in ground_truth.md.
Intentionally thin — refine the rubric and the prompt after seeing the first
prototype outputs.

Usage:
    python eval_hypothesis_recovery.py --dataset farah \
        --hypotheses ../data/hypotheses/hypotheses.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass


_JUDGE_PROMPT = """You are an expert spatial transcriptomics reviewer scoring
a retrospective hypothesis-recovery benchmark.

The hypothesis agent was given a dataset and a limited background, with the
original paper's target claim deliberately withheld. The agent then explored
the data and proposed hypotheses grounded in what it observed.

You will see:
1. The withheld ground-truth target (what the agent was supposed to recover).
2. The agent's generated hypotheses (final hypotheses.json).

Score each hypothesis against the rubric in the ground-truth file, then pick
the best-matching hypothesis and assign aggregate scores.

Return JSON ONLY in this exact schema:

{
  "best_hypothesis_id": "<H1|H2|...>",
  "per_aspect_scores": {
    "spatial_locus":           {"score": 0|1|2, "evidence": "<quote>"},
    "celltype_composition":    {"score": 0|1|2, "evidence": "<quote>"},
    "functional_interp":       {"score": 0|1|2, "evidence": "<quote>"},
    "specificity":             {"score": 0|1|2, "evidence": "<quote>"}
  },
  "total_score": <0-8>,
  "recovery_class": "<full|partial|miss>",
  "rationale": "<2-3 sentences explaining the call>"
}

---
GROUND TRUTH (withheld from agent):

{ground_truth}

---
AGENT'S HYPOTHESES (hypotheses.json contents):

{hypotheses}
"""


def _judge(ground_truth_text: str, hypotheses_text: str) -> dict:
    """Call the LLM judge. Returns parsed JSON dict."""
    from langchain_openai import ChatOpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set — required for the LLM judge.")

    # The judge prompt embeds literal JSON braces, so .format() chokes on
    # them; use literal substitution instead.
    prompt = (
        _JUDGE_PROMPT
        .replace("{ground_truth}", ground_truth_text)
        .replace("{hypotheses}", hypotheses_text)
    )
    model = ChatOpenAI(model="gpt-5", reasoning_effort="high")
    response = model.invoke(prompt)
    content = str(response.content).strip()

    # The model should return JSON only, but strip optional code fences.
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[len("json"):].strip()
    return json.loads(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        required=True,
        help="Recovery target id (e.g., 'farah'). Looks up "
        "demo/data/<dataset>_ground_truth.md.",
    )
    parser.add_argument(
        "--hypotheses",
        required=True,
        type=Path,
        help="Path to the generated hypotheses.json.",
    )
    args = parser.parse_args()

    demo_data = Path(__file__).resolve().parent / "data"
    gt_path = demo_data / f"{args.dataset}_ground_truth.md"
    if not gt_path.is_file():
        raise SystemExit(f"Ground-truth file missing: {gt_path}")
    if not args.hypotheses.is_file():
        raise SystemExit(f"Hypotheses file missing: {args.hypotheses}")

    ground_truth_text = gt_path.read_text(encoding="utf-8")
    hypotheses_text = args.hypotheses.read_text(encoding="utf-8")

    result = _judge(ground_truth_text, hypotheses_text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
