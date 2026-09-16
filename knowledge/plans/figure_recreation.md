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
Reproduce and verify the figure end to end (**1 step**, dispatched to `coding_agent`; prepend analysis steps only if the figure's fields must be computed first)

## Details
- Assign the `figure-reproduce` skill to the step. The skill owns the **method and
  its ordering**; this plan supplies only the input paths and the artifacts to
  emit. Do not restate the method in the step description.
- **Step 1 — Reproduce the target figure and verify it**, agent `coding_agent`:
  follow the `figure-reproduce` skill end to end — inventory the dataset, measure
  the target's spec, resolve the colormap, render, compare against the target, and
  apply the skill's bounded repair loop. Artifacts: `figures/<name>.png`, the
  vector copy, `tables/<name>_plot_data.csv`, `tables/colormap.yaml`,
  `tables/compare_metrics.json`, `figures/compare_diff.png`,
  `reports/<name>_repro_note.md`.
- **Why one step.** The skill already sequences this work and its later stages
  verify its earlier ones, so splitting it across dispatches duplicated that
  ordering and paid a full manager round-trip per boundary. The checkpoints are
  not lost: they move from step boundaries to **artifacts**. Every file listed
  above is still required, and `colormap.yaml` in particular is still a gate —
  rendering before it exists means the palette was invented, which the repro note
  and `compare_metrics.json` will expose.
- **The colormap remains a hard gate.** Resolve it from the most trustworthy
  source available (supplied file → colors stored in the dataset → the reference's
  legend → refuse). If no trustworthy source exists, **fail before rendering**
  rather than inventing one. A default palette (tier 5) is not a low-fidelity
  reproduction — it is a differently-coloured plot of the same data — so the
  correct outcome is a "Constraint violation:" report naming the missing source.
  **Do not `retry_step` a palette refusal**: retrying cannot conjure a source the
  data does not contain, and only pressures the sub-agent into `--allow-default`.
  Surface it to the user; the fix is to supply a palette file or a legended
  reference. A step that ends this way is correctly reported as blocked, not
  failed-and-retried.
- **A missing repro note fails the step.** `reports/<name>_repro_note.md` is
  where deviations and the fidelity result are recorded; without it the run
  asserts nothing about its own quality. Observed: a run produced every other
  artifact and no `reports/` directory at all, and was still reported finished.
- **Do not accept the step on artifact existence alone.** `figures/<name>.png`
  appearing proves only that something rendered. The step is complete when
  `compare_metrics.json` exists *and* the repro note reports the comparison
  outcome. A note admitting the colors do not match the reference is a **failed**
  step: retry it naming the stage that was skipped.
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
