"""LLM-judge that scores hypothesis QUALITY on the 5 criteria the
manuscript revision response committed to (Reviewer #1 Comment #7):

  - Derivability  (logically follows from background / observed data)
  - Novelty       (not a restatement of common knowledge)
  - Feasibility   (testable with the available data)
  - Specificity   (concrete enough to admit a clear test)
  - Falsifiability (both positive and negative outcomes interpretable)

This complements the recovery-match rubric in `eval_hypothesis_recovery.py`,
which scores whether the hypothesis matches the withheld author claim. The
two rubrics answer different questions:
  - recovery_match — did the agent rediscover the paper's finding?
  - hypothesis_quality — is the hypothesis well-formed as a scientific claim?

The quality rubric is ground-truth-free; it only needs the hypothesis text
and the biological background the agent was given.

Usage:
    python eval_hypothesis_quality.py --dataset farah \\
        --hypotheses demo/outputs/farah_recovery_v3_multiseed/seed1/hypotheses.json
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


_QUALITY_PROMPT = """You are an expert spatial transcriptomics reviewer scoring
the QUALITY of an agent-generated hypothesis, independent of whether it
recovers any specific author finding.

You will see:
1. The biological background the agent was given (NOT a ground-truth claim).
2. The agent's generated hypotheses (JSON or notebook excerpt).

For each hypothesis (or for the single best hypothesis if there are many),
score on the FIVE criteria the manuscript revision response commits to:

  - **derivability** (0-10): logically follows from the background and/or
    any observations the hypothesis explicitly cites. A 10 means the
    hypothesis is a clearly defensible inference; a 0 means it is unrelated
    or contradictory to the background.
  - **novelty** (0-10): not a trivial restatement of common knowledge,
    paraphrase of the background, or a well-known textbook claim. A 10
    means surprising/non-obvious within the field; a 0 means trivially
    obvious.
  - **feasibility** (0-10): testable with the available spatial
    transcriptomics dataset alone (no new experiments, no external
    datasets). A 10 means clearly doable with the data; a 0 means impossible
    without out-of-scope resources.
  - **specificity** (0-10): concrete enough to admit a clear pass/fail
    test — specific cell types, specific spatial regions, specific gene
    programs, specific predicted directionality. A 10 means a precise
    operationalisation; a 0 means vague platitudes.
  - **falsifiability** (0-10): both positive AND negative outcomes are
    interpretable; the hypothesis predicts something that COULD be wrong.
    A 10 means crisp falsifiable prediction; a 0 means unfalsifiable in
    principle (tautology, definitional, or only confirming evidence
    counts).

Plus one additional measure the response document commits to:

  - **testability** (0-3): whether the hypothesis can be converted into an
    executable validation analysis using the dataset.
        0 — no concrete test described or implied
        1 — vague test plan (e.g., "compare expression") without inputs
        2 — clear test plan referencing concrete inputs (cell types, genes,
            statistical procedure)
        3 — agent already executed a test in the narrowing phase or
            included executable code

Return JSON ONLY in this exact schema:

{
  "best_hypothesis_id": "<id of the strongest hypothesis>",
  "best_hypothesis_quote": "<≤200 chars verbatim>",
  "scores": {
    "derivability":    {"value": <0-10>, "rationale": "<one sentence>"},
    "novelty":         {"value": <0-10>, "rationale": "<one sentence>"},
    "feasibility":     {"value": <0-10>, "rationale": "<one sentence>"},
    "specificity":     {"value": <0-10>, "rationale": "<one sentence>"},
    "falsifiability":  {"value": <0-10>, "rationale": "<one sentence>"}
  },
  "criteria_sum_50": <sum of the five above, 0-50>,
  "testability":     {"value": <0-3>, "rationale": "<one sentence>"},
  "overall_rationale": "<2-3 sentences>"
}

---
BIOLOGICAL BACKGROUND the agent was given:

{background}

---
AGENT'S HYPOTHESES (raw JSON or notebook excerpt):

{hypotheses}
"""


def _judge(background_text: str, hypotheses_text: str) -> dict:
    from langchain_openai import ChatOpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set — required for the LLM judge.")

    prompt = (
        _QUALITY_PROMPT
        .replace("{background}", background_text)
        .replace("{hypotheses}", hypotheses_text)
    )
    model = ChatOpenAI(model="gpt-5", reasoning_effort="high")
    response = model.invoke(prompt)
    content = str(response.content).strip()

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
        help="Recovery target id (e.g. 'farah'). Used to look up "
        "demo/data/<dataset>_background.md.",
    )
    parser.add_argument(
        "--hypotheses",
        required=True,
        type=Path,
        help="Path to the generated hypotheses.json / cellvoyager summary.",
    )
    args = parser.parse_args()

    demo_data = Path(__file__).resolve().parent / "data"
    bg_path = demo_data / f"{args.dataset}_background.md"
    if not bg_path.is_file():
        raise SystemExit(f"Background file missing: {bg_path}")
    if not args.hypotheses.is_file():
        raise SystemExit(f"Hypotheses file missing: {args.hypotheses}")

    background_text = bg_path.read_text(encoding="utf-8")
    hypotheses_text = args.hypotheses.read_text(encoding="utf-8")

    result = _judge(background_text, hypotheses_text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
