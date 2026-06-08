---
name: paper_hypothesis_generation
status: enabled
description: >
  Generate research hypotheses from a scientific paper and spatial transcriptomics
  dataset. Includes PDF analysis, dataset inventory, data feasibility assessment,
  hypothesis drafting with critic review, and quality validation (robustness >= 6.0).
---

## Inputs
- PDF
- Dataset (.h5ad)

## Outputs
- briefs/paper_summary.txt
- briefs/paper_outline.md
- tables/data_inventory.tsv
- tables/categorical_values.tsv
- tables/data_feasibility.json
- tables/paper_dataset_reconciliation.tsv
- hypotheses/draft_hypotheses.json
- hypotheses/pre_review_criticism.json
- hypotheses/hypotheses.json
- hypotheses/hypothesis_brief.md

> NOTE: No Jupyter notebook generated at this stage - only during hypothesis testing

## Step Sketch
PDF Reader Agent: analyze PDF → save briefs | Coding Agent: inventory dataset + validate entities + compute feasibility → save tables | Hypothesis Agent: generate drafts → Critic Agent: review quality → Hypothesis Agent: revise/finalize → save hypotheses

## Evaluation Criteria
- paper_summary.txt exists
- data_inventory.tsv exists
- data_feasibility.json exists
- paper_dataset_reconciliation.tsv exists
- pre_review_criticism.json exists
- hypotheses.json exists
- All hypotheses passed robustness >= 6.0
- 1+ hypothesis generated

## Defaults
- hypothesis_count: 1
- output_format: json
- include_paper_summary: true

## Checklist
- PDF Reader Agent: Analyze PDF (text+figures), extract key findings/mechanisms/claims, save briefs/paper_summary.txt
- Coding Agent: Load dataset, inventory genes/annotations/spatial with statistics, save tables/data_inventory.tsv
- Coding Agent: Validate paper entities against dataset + compute data constraints (power/resolution/suitability), save tables/data_feasibility.json
- Hypothesis Agent: Generate 3-5 DRAFT hypotheses using briefs+data_feasibility, focus on system-level patterns, save hypotheses/draft_hypotheses.json
- Critic Agent: Review drafts for robustness (reject if <6/10), specificity, circular logic, biological plausibility, save hypotheses/pre_review_criticism.json
- Hypothesis Agent: Revise/replace hypotheses based on criticism, ensure all pass quality thresholds (robustness>=6.0), save hypotheses/hypotheses.json
- Reporter Agent: Display final hypotheses with quality metrics and critic assessments (NO notebook at this stage)
