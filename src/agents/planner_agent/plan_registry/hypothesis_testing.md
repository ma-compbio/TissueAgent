---
name: hypothesis_testing
status: enabled
description: >
  Test user-selected hypotheses by gathering related literature, designing and
  executing computational experiments on the dataset, and producing a
  comprehensive report with critic review of findings.
---

## Inputs
- hypotheses.json (from hypothesis generation step)
- User-selected hypothesis IDs (e.g., 1, 3)
- Dataset (.h5ad)

## Outputs
- related_papers.json
- experiment_results/
- reports/hypothesis_testing_report.md

## Step Sketch
Find related papers → design experiments for selected hypotheses → execute analyses → summarize findings

## Evaluation Criteria
- related_papers.json exists
- Experiment results generated
- Report created

## Defaults
- papers_per_hypothesis: 3-5
- include_visualizations: true

## Checklist
- Searcher Agent: Search literature for papers related to each selected hypothesis topic
- Coding Agent: Design computational experiments to test each hypothesis using the dataset
- Coding Agent: Execute analyses - load data, compute metrics, generate visualizations, save to experiment_results/
- Critic Agent: Attempt to falsify hypothesis, identify confounds and alternative explanations, save to reports/criticism.json
- Reporter Agent: Create comprehensive report summarizing findings with criticism and key results
