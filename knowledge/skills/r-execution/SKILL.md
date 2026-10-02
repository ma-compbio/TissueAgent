---
name: r-execution
description: Enables R code execution for this step. Assign when the step requires R packages (e.g. Seurat, BayesSpace, or other Bioconductor tooling) or the user explicitly requests R; do NOT assign for work Python libraries already cover.
applies_to: [coding_agent]
status: enable
tags: [r, execution, seurat, bioconductor]
---

# R execution

## When to use

Assign this skill to a step only when the analysis genuinely needs R: a required
package has no Python equivalent (Seurat-specific workflows, BayesSpace, many
Bioconductor packages), or the user explicitly asked for R. When scanpy/squidpy
or another Python library covers the task, do not assign it — the step then runs
Python-only.

## What it provides

With this skill assigned, the coding agent gets an `r` tool that executes R code
in a persistent Jupyter kernel (IRkernel) inside the sandbox. Unlike the `execute`
shell tool, **state persists across `r` calls**: variables, loaded libraries and
in-memory objects (e.g. a Seurat object) survive from one call to the next, so
build analyses incrementally instead of re-loading data each call.

## Workflow

1. Read inputs with workspace-relative paths, same convention as Python:
   `read.csv("project/uploads/foo.csv")`, `readRDS("library/bar.rds")`.
2. Work incrementally in the kernel; use `cat()` / `print()` to surface values.
3. Write all artifacts under `project/outputs/`; save figures explicitly to
   `project/outputs/figures/` (`ggsave(...)` or `png(...); ...; dev.off()`).
4. Persist final objects the next step needs (`saveRDS`, `write.csv`).

## Environment

- Packages live on a persistent volume: `install.packages("<pkg>")` or
  `BiocManager::install("<pkg>")` installs survive across runs — check with
  `requireNamespace("<pkg>", quietly = TRUE)` before reinstalling.
- Long installs can take minutes; prefer packages that are already present.

## Common issues

- `could not find function` → the library isn't loaded in *this* kernel yet:
  `library(<pkg>)` first (state persists afterwards).
- Writing to `library/` fails by design — it is read-only shared input; write
  under `project/outputs/`.
- Keep Python work in `execute`/scripts; use `r` only for the R-package work
  this step was assigned this skill for. Exchange data between the two through
  files (`.csv`, `.rds`, `.h5ad`), not in memory.
