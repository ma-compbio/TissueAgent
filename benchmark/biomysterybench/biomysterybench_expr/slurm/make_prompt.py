#!/usr/bin/env python3
"""Emit the TissueAgent prompt for a BioMysteryBench-Expression problem id.

Prompt = a short preamble (where the data lives + the benchmark contract) + the
benchmark question verbatim. Usage: make_prompt.py <problem_id>

The contract half of the preamble exists because refusal, not bad analysis, was
the dominant failure mode in the 2026-07-25 sweep: 4 of 6 wrong answers were the
agent declining to commit (an empty list, ROUTE: CLARIFY asking for the metadata
the benchmark deliberately withholds, a hedge that rated the correct answer
"low"). Layer-1 execution recovery over the same runs was 5/5 — the code was
fine. Stating that the labels are recoverable and that hedging scores zero
targets that, and incidentally starves ROUTE: CLARIFY, which is a guaranteed
zero in autopilot because ``graph.py:292`` routes it straight to END with no one
to answer.

**This makes the run a new prompt version (v1), not the baseline (v0).** It changes the task framing, so
results are comparable only to other runs built from this same preamble. The
prompt is stored verbatim in ``metrics.json:run.prompt``, which is what keeps
the two versions separable in the archive — do not grade across them.
"""
import csv
import sys
from pathlib import Path

pid = sys.argv[1]
csv_path = Path(__file__).resolve().parent.parent / "problems.csv"
with open(csv_path) as f:
    row = next((r for r in csv.DictReader(f) if r["id"] == pid), None)
if row is None:
    sys.exit(f"id {pid} not found in {csv_path}")

preamble = (
    "The data file(s) for this task are in the directory `library/datasets/` "
    "(inspect the directory and load whatever files are present as appropriate). "
    "Sample labels and group assignments are deliberately withheld — they are "
    "recoverable from the expression data itself, which is the point of the task. "
    "No clarification is available and no additional metadata exists. "
    "You must commit to one specific answer in the requested format; "
    "hedging, an empty list, or 'cannot determine' is scored as wrong. "
)
print(preamble + row["question"].strip())
