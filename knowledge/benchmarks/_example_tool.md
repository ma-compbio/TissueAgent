---
name: _example_tool
status: disabled
tier: tool
task: cell_annotation
# tier=tool: call a tool function directly with explicit args. No prompt, no LLM.
# Deterministic and cheap — safe for CI once the dataset is cached.
tool: harmony_transfer_tool
args:
  spatial_anndata_path: uploads/spatial.h5ad
  reference_anndata_path: uploads/reference.h5ad
  cell_type_column: cell_type
inputs:                       # dest-inside-project : source-in-local-cache
  uploads/spatial.h5ad:    library/benchmarks/_example/spatial.h5ad
  uploads/reference.h5ad:  library/benchmarks/_example/reference.h5ad
golden:
  labels: library/benchmarks/_example/expected/labels.csv
metrics:
  - { name: file_exists, args: { path: harmony_transfer_results/annotated_object.h5ad }, threshold: { eq: true } }
  - { name: ari,         threshold: { gte: 0.6 } }
---

# Example: tool-tier benchmark (disabled placeholder)

This file documents the **tool-tier** spec format and is excluded from runs
(`status: disabled`). Copy it to a new name and set `status: enabled` to add a real benchmark.

## What a tool-tier benchmark does
1. The runner stages each `inputs` source file into a fresh temp project under the mapped path.
2. It resolves `tool` from the agent registry and calls it with `args` (paths relative to the
   staged project) — **no prompt, no graph, no LLM**. Deterministic.
3. It scores produced artifacts (and `golden`) with the named `metrics`, comparing each to its
   `threshold` (`gte`/`lte`/`gt`/`lt`/`eq`).

## Fields
- `tier: tool` — direct tool call.
- `tool` / `args` — the registered tool name and its arguments.
- `inputs` — `dest-in-project: source-in-cache`; sources are populated by `scripts/fetch_benchmarks.py`.
- `golden` — ground-truth files passed to reference-based metrics (e.g. `ari` gets the golden `labels`).
- `metrics` — list of `{name, args?, threshold}`; `name` must exist in the metric registry.

Use a tool-tier benchmark to test the **analysis** in isolation (correctness, regressions),
independent of agent routing.
