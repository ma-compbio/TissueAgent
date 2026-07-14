---
name: figure-reproduce
description: Reproduce a target figure from a dataset — regenerate a published/reference plot (e.g. a spatial scatter, UMAP, heatmap, dotplot from a paper) using the coding agent and matching its panels, layout, and color encoding. Use when the user asks to "reproduce", "recreate", "replicate", or "remake" a figure, or to match a figure from a paper/notebook.
status: enable
---

# Figure Reproduction

## When to use

The user wants an existing figure **recreated from data** — a paper panel, a notebook plot, or a
previously produced figure — so the output matches the target's content and appearance.

- Use when the user says "reproduce / recreate / replicate / remake figure X", "match this plot",
  or "make the same figure as the paper".
- If the target lives in a **paper PDF**, the `pdf_reader` agent extracts the figure image and its
  caption first; this skill then reproduces it from the dataset.
- This workflow is not for designing a brand-new figure with no reference. Never fabricate data to match a figure; reproduce only what the data supports.

## Input

- **Target figure** *(required)* — what to match. One of: an image/PDF path, a paper figure +
  caption (via `pdf_reader`), a description, or an existing output figure. Capture: plot **type**
  (scatter/UMAP/heatmap/dotplot/violin/spatial), **panels/facets**, the **color encoding** (by
  cluster / cell type / gene / continuous value), axes, and any legend/annotations.
- **Dataset** *(required)* — the `.h5ad` (or table) the figure is computed from. Confirm it
  contains the fields the figure needs: the embedding/coords (`.obsm['spatial']`, `X_umap`), the
  color column in `.obs`, or the gene in `.var_names`.
- **Style hints** *(optional)* — palette, point size, figure size/DPI, panel grid. Default to the
  target's apparent style; record any guess.

## Output

- **Reproduced figure** — saved under the active project's `outputs/` (e.g.
  `outputs/figures/<name>.png`, 150+ DPI). Save a vector copy (`.pdf`/`.svg`) too when the target
  is publication-quality.
- **Plotted data table** — a CSV of exactly what was plotted (coords + color field, or the matrix
  behind a heatmap) so the figure is auditable and reusable.
- **A short repro note** — which dataset fields, parameters, and assumptions produced the figure,
  plus any deviations from the target and why.

## Success Criteria

- The figure file exists, is non-empty, and renders (the `python` tool returns it inline — the
  agent can **see** it and compare against the target).
- **Content matches**: same plot type, same number of panels, same color encoding, same groups
  (e.g. the cell types present and their relative spatial/embedding positions agree with the target).
- The plotted-data CSV exists and its row/column counts match the dataset subset shown.
- Deviations from the target are **named** in the repro note, not silently introduced.
- Honest-failure: if the dataset lacks a field the figure needs, say so and propose the closest
  reproducible variant — don't invent data.

## Plan Workflow 

First, the planner should identify the appropriate targets (dataset, reference figure, additional descriptions). Then, the plan should be created in one or more steps.
 - If the task is relatively simple and does not require significant preprocessing, create a plan with only a single step. This step should encapsulate dataset inspection, data processing, and graph creation.
 - If the task requires significant pre-computation, split the data processing into one or more different steps. The final step should always be the actual graph creation. In each intermediate steps, you should assign relevant and useful artifacts to persist the data between steps.

IMPORTANT: For the final plotting step, you should explicitly specify that the final figure needs to be iterated on to be near publication quality. This should include nice labels and avoid overlapping or obsucured plot elements. If a reference image is provided, the produced figure and the reference figure need to be matching in style.

## Common Issues

- **Missing field → can't reproduce as-is.** The target colors by a column/embedding the dataset
  lacks (no `X_umap`, no `cell_type`). Compute it if the data supports it (run the relevant
  analysis first, e.g. annotation/clustering), or reproduce the closest supported variant and say so.
- **Gene symbol vs ID mismatch.** A figure by gene won't plot if `var_names` use a different ID
  scheme — map identifiers first.
- **Wrong plot primitive.** A "heatmap" in a paper may be a clustermap, matrixplot, or dotplot —
  match the actual encoding (use `search_documentation` to pick the right `sc.pl.*`).
- **Over-matching.** Don't tweak data or thresholds just to make the picture look identical —
  reproduce what the data legitimately yields and document differences.
