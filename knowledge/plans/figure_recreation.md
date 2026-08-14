---
name: figure_recreation
status: enabled
description: >
  Recreate a target figure from a dataset — regenerate a published/reference plot
  (spatial scatter, UMAP, heatmap, dotplot, violin, bar/line) so it matches the
  target's panels, layout, category order and color encoding, then verify the
  reproduction against the target and repair it if it is off. Use when the user
  asks to "reproduce", "recreate", "replicate", or "remake" a figure, or to match
  a figure from a paper/notebook.
---

## Inputs
- Target figure (required): an image/PDF path, a paper figure + caption (via `pdf_reader`), or a prior output figure
- Dataset (required): the `.h5ad`/table the figure is computed from, holding the coords/embedding, the color column, or the gene
- Optional: a supplied palette file (e.g. `colormap.yaml`) — it outranks anything measured from the image

## Outputs
- `figures/<name>.png` (150+ DPI) and a vector copy (`.pdf`/`.svg`)
- `tables/<name>_plot_data.csv` — exactly what was plotted (coords + color field, or the matrix)
- `tables/colormap.yaml` — the resolved palette **and the source tier it came from**
- `tables/compare_metrics.json` + `figures/compare_diff.png` — the fidelity comparison against the target
- `reports/<name>_repro_note.md` — fields used, params, B-level, named deviations

## Step Sketch
Prepare inputs + measure the target spec → resolve the colormap → render → compare against the target and repair (4 steps; prepend analysis steps if the figure's fields must be computed first)

## Details
- Apply the `figure-reproduce` skill to **every** step. It supplies the method for each; the plan supplies only the boundaries, the input paths, and the artifacts. Do not restate the method in step descriptions.
- **Step 1 — Prepare inputs and define the figure spec**, agent `coding_agent`: inventory the dataset (coords/embedding, the categorical color column and its order) and measure the target's spec (palette, category order, colormap incl. `_r`, on-panel text). Artifacts: `tables/<name>_spec.yaml`, `tables/<name>_inventory.*`.
- **Step 2 — Resolve the colormap**, agent `coding_agent`: produce one `tables/colormap.yaml` from the most trustworthy source available (supplied file → colors stored in the dataset → the reference's legend → refuse). Artifact: `tables/colormap.yaml`.
  - This step is a **gate**. If no trustworthy source exists the step fails *before* anything is rendered — that is the intended behaviour. The fix is to supply a palette source, not to let the executor invent one.
- **Step 3 — Render the figure**, agent `coding_agent`: plot from `tables/colormap.yaml` with an explicit category order, labels copied verbatim, and any background/histology underlay preserved. Artifacts: `figures/<name>.png`, the vector copy, `tables/<name>_plot_data.csv` (categories in plotted order).
- **Step 4 — Compare against the target and repair**, agent `coding_agent`: run the fidelity comparison, open the side-by-side diff, name the differences, and apply a bounded repair/polish pass. Artifacts: `tables/compare_metrics.json`, `figures/compare_diff.png`, `reports/<name>_repro_note.md`.
  - Step 4 contains a **bounded loop** (re-render → re-compare). Keep it inside this one step; the skill owns the loop and its retry budget.
- Do **not** collapse these into a single step. Each boundary exists because it emits an artifact the verifier can check; a figure reproduction with no checkpoint ships unverified.
- Do **not** write descriptions telling the executor to *choose*, *tune*, or *pick* a color palette. The skill derives the palette by **measuring** it; an instruction to select one contradicts the skill and produces wrong colors. State the goal ("colors match the reference's cell-type palette") and let the skill supply the method.
- The final figure should be iterated to near publication quality: readable labels, no overlapping or obscured elements, and — when a reference is provided — matching style.
- Never fabricate data to match a figure. If the dataset lacks a field the figure needs, reproduce the closest supported variant and name the gap.

## Evaluation Criteria
- file_exists(figures/<name>.png)
- file_exists(tables/colormap.yaml)
- file_exists(tables/compare_metrics.json)
- file_exists(reports/<name>_repro_note.md)
- The reproduction was **compared to the target**, not merely rendered: a figure whose repro note admits the colors do not match the reference is a failed step, not a completed one.

## Common Issues
- **Missing field → can't reproduce as-is.** The target colors by a column/embedding the dataset lacks (no `X_umap`, no `cell_type`). Compute it if the data supports it (run the relevant analysis first), or reproduce the closest supported variant and say so.
- **Gene symbol vs ID mismatch.** A figure keyed by gene won't plot if `var_names` use a different ID scheme — map identifiers first.
- **Wrong plot primitive.** A "heatmap" in a paper may be a clustermap, matrixplot, or dotplot — match the actual encoding.
- **Color/category mismatch.** Categories render in a different order or different colors than the target. The colormap step exists to prevent this: resolve it from a real source and set an explicit category order — never rely on library defaults, and never name colors by eye.
- **Unrecoverable palette.** A legendless dense scatter of sub-pixel markers does not contain its own colors; the colormap step will refuse rather than guess. Supply a palette file or use the dataset's own color field.
- **Over-matching.** Don't tweak data or thresholds just to make the picture look identical — reproduce what the data legitimately yields and document differences.
