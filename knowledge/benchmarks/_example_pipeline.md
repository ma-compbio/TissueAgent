---
name: _example_pipeline
status: disabled
tier: pipeline
task: spatial_deconvolution
# tier=pipeline: drive the REAL graph from a prompt. Tests planner/recruiter routing
# and tool use. Costs tokens, nondeterministic — run manually/nightly, not in default CI.
prompt: |
  Deconvolve the Visium slide at uploads/visium.h5ad using the scRNA-seq reference at
  uploads/reference.h5ad. The reference cell type labels are in the `cell_type` column.
  Save per-spot cell type abundances.
inputs:                       # dest-inside-project : source-in-local-cache
  uploads/visium.h5ad:     library/benchmarks/_example/visium.h5ad
  uploads/reference.h5ad:  library/benchmarks/_example/reference.h5ad
run_config:
  mode: autopilot             # MUST be autopilot — copilot blocks on human review
  model: default              # pin so a model swap is an explicit, tracked variable
  recursion_limit: 100
census_version: null          # set a dated snapshot if the prompt triggers a live CELLxGENE fetch
golden:
  abundances: library/benchmarks/_example/expected/q05_cell_abundance_w_sf.csv
metrics:
  - { name: file_exists,   args: { path: cell2location_results/q05_cell_abundance_w_sf.csv }, threshold: { eq: true } }
  - { name: abundance_jsd, threshold: { lte: 0.15 } }
---

# Example: pipeline-tier benchmark (disabled placeholder)

This file documents the **pipeline-tier** spec format and is excluded from runs
(`status: disabled`). Copy it to a new name and set `status: enabled` to add a real benchmark.

## What a pipeline-tier benchmark does
1. The runner materializes the **fixture**: a fresh temp project with `inputs` staged, then sets
   `session.project_id`, forces `session.mode = autopilot`, applies `run_config.model`
   (re-compiling the graph if pinned), and a fresh `thread_id`.
2. It invokes the **real compiled graph**: `session.agent.invoke({"messages": [HumanMessage(prompt)]}, config)`.
3. It scores artifacts under the project's `outputs/` (and `golden`) with the named `metrics`.

This tests the **whole pipeline** — does the planner pick `spatial_deconvolution`, does the
recruiter wire the right agent/skill, does the tool run — not just the analysis.

## Fields beyond the tool tier
- `prompt` *(required)* — the `HumanMessage` that enters the graph. Phrasing is a tested variable.
- `run_config` — `mode` (force `autopilot`), `model`, `recursion_limit`.
- `census_version` — pin a dated Census snapshot when the run may hit the live CELLxGENE tools
  (`query_cellxgene_census_live_tool` / `retrieve_cellxgene_single_cell_tool`); otherwise the
  benchmark is non-hermetic and drifts as the Census updates.

## Reproducibility
Pin everything that affects the run: inputs (checksummed via the manifest), `model`, and
`census_version` if the fetch path is exercised. Token cost and nondeterminism mean these run
manually or nightly, not in default CI.
