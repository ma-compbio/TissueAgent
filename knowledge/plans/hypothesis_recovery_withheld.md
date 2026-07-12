---
name: hypothesis_recovery_withheld
status: enabled
description: >
  Retrospective hypothesis-recovery under a withheld-background protocol.
  Agents receive a spatial dataset and limited background only; author claims
  and PDF findings are not provided. Used for the Comment #7 benchmark
  (TissueAgent vs CellVoyager).
---

## Inputs
- Dataset (.h5ad)
- Limited background text (tissue / technology / annotations / constraints; NO findings)

## Outputs
- hypotheses/exploration_log.md
- tables/data_inventory.tsv
- hypotheses/hypotheses_draft.json
- hypotheses/hypotheses.json
- hypotheses/hypothesis_brief.md
- hypotheses/test_results_phase3.json

> NOTE: Do NOT invoke PDF Reader. Do NOT load gold_claims or paper findings.

## Step Sketch
Coding Agent: explore dataset under withheld background → save exploration_log + inventory | Hypothesis Agent: draft observation-grounded hypotheses → Critic Agent: review quality → Coding Agent: execute test plans and narrow statuses

When CellVoyager Agent is present in the recruitable pool, the Recruiter may assign an exploratory analysis step to `cellvoyager_agent` on the same `.h5ad` + limited background. On success the adapter writes `hypotheses/cellvoyager_suggestions.json` and appends `OBSERVATION_CV` to `hypotheses/exploration_log.md` — treat those as the CellVoyager step artifacts. Hypothesis Agent should then synthesize CellVoyager proposals with TissueAgent observations. Do not invoke PDF Reader or load gold claims.

> Intended execution path: full TissueAgent graph (planner → recruiter → manager). Not the archived 3-phase coding/hypothesis shortcut.

## Evaluation Criteria
- exploration_log.md exists with 1+ OBSERVATION entries
- hypotheses.json exists
- 1+ hypothesis generated
- All retained hypotheses have quality scores for derivable/novel/feasible/specific/falsifiable
- test_results_phase3.json exists after testing phase

## Defaults
- hypothesis_count: 3
- withhold_paper_findings: true
- output_format: json

## Checklist
- Coding Agent: Read limited background only; inventory dataset; run spatial exploration; save hypotheses/exploration_log.md and tables/data_inventory.tsv
- Hypothesis Agent: Generate 3 DRAFT hypotheses grounded_in OBSERVATION ids (not paper claims); save hypotheses/hypotheses_draft.json
- Critic Agent: Review drafts for specificity, circular logic, biological plausibility, and score robustness; save hypotheses/pre_review_criticism.json
- Hypothesis Agent: Revise/finalize; save hypotheses/hypotheses.json and hypotheses/hypothesis_brief.md
- Coding Agent: Execute each test_plan; save hypotheses/test_results_phase3.json; update statuses (SUPPORTED/REFINE/DROPPED) and narrowing_notes
- Reporter Agent: Summarize recovered hypotheses without revealing withheld gold claims
