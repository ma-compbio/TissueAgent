---
name: figure-reproduce
description: Reproduce a target figure from a dataset — regenerate a published/reference plot (e.g. a scatter, line/bar chart, heatmap, UMAP, dotplot, violin, or spatial map from a paper) using the coding agent and matching its panels, layout, and color encoding. Use when the user asks to "reproduce", "recreate", "replicate", or "remake" a figure, or to match a figure from a paper/notebook. Covers self-evaluation of the result and a bounded reflect-and-retry repair loop when the first attempt is off.
applies_to: [coding_agent]
status: enable
strict: true
---

# Figure Reproduction
Reproduce a reference figure from supplied data, match its scientific
content and visual encoding, verify the result against the target, and
repair meaningful mismatches.

## When to use

- The user says "reproduce / recreate / replicate / remake figure X", "match this
  plot", or "make the same figure as the paper".
- The target may be a **paper figure** (recruit the `pdf_reader` agent, or use
  `scripts/extract_pdf_figure.py` to pull the figure image + caption), a notebook
  plot, an image/PDF path, a description, or a prior output figure.
- **Not** for designing a brand-new figure with no reference (that's ordinary
  plotting), and never to **fabricate** data to match a figure — reproduce only
  what the data legitimately supports.

## Inputs

- Target figure (required) — the figure or panel to reproduce.
- Dataset (required) — the data from which the figure should be regenerated.
- Method description (optional) — text describing how the target figure was generated, such as a paper Methods section, figure caption, analysis description, or user-provided instructions. Use it to recover preprocessing, algorithms, parameters, data subsets, and plotting choices.
- Method plot / workflow figure (optional) — a schematic, flowchart, or other figure describing the analysis procedure that produced the target. Interpret it together with the method description to reconstruct the intended workflow.

If either target figure or dataset is unavailable, report the missing requirement rather than fabricating it.

## Required outputs

- `project/outputs/figures/<name>.png`
- vector figure when appropriate
- `project/outputs/tables/plotted_data.csv`
- `project/outputs/tables/colormap.yaml`
- `project/outputs/tables/compare_metrics.json`
- `project/outputs/reports/<name>_repro_note.md`

## Invariants

1. Generate the figure by running analysis/plotting code on the data.
   Never copy, decode, download, or synthesize the target image.
2. Do not guess palette, category order, labels, orientation, or
   colormap direction when they can be measured.
3. Never silently substitute a default palette.
4. Every reproduction must be compared against the target.
5. Structural mismatches must be fixed before completion.
6. Maximum 5 render attempts and 1 data/environment re-preparation.
7. Any unresolved mismatch or unsupported feature must be recorded in
   the repro note.

## Completion Gate

Do not report success unless all are true:

- [ ] figure rendered from supplied data
- [ ] plotted-data CSV written
- [ ] palette provenance verified
- [ ] automated comparison executed
- [ ] no unresolved structural defects
- [ ] ≤5 render attempts
- [ ] residual differences documented
- [ ] repro note written


## Workflow

### 1. Acquire and inspect the target

Obtain the target image/panel and caption.

Record:
- plot primitive and panel count
- orientation/aspect
- background/underlay
- categorical vs continuous encoding
- legend/colorbar
- visible text
- marker style
- unusual annotations

### 2. Inspect the dataset

Identify the exact data subset and fields required for the figure:
coordinates/embedding, category/value field, genes/features, and
relevant metadata.

If required information is absent, stop and report the blocker.

### 3. Measure the reference

Run `extract_reference_spec.py`.

Resolve:
- palette / colormap
- category order
- visible labels
- orientation and panel geometry

Treat measured values as the plotting specification.

### 4. Resolve palette

Run `build_colormap.py`.

Allowed sources, highest priority first:
1. supplied palette
2. dataset metadata
3. reference legend
4. reliable reference pixels

If no trustworthy palette can be resolved, report a constraint
violation instead of silently using defaults.

Confirm the written file with `build_colormap.py --verify`.

### 5. Render attempt 1

Generate the figure using the measured specification.

Match:
- data subset
- primitive
- panel layout
- palette/order
- labels
- orientation/aspect
- background/underlay

Save the plotting code and plotted-data table.

### 6. Compare attempt 1

Run `compare_figures.py` and save its JSON and both diff images (the
side-by-side and the letterboxed `--geometry-out`, which preserves shape).

Check both:
- content fidelity — the similarity metrics
- structural fidelity — `pass2_geometry.findings`; proceed only on `clean: true`

Then inspect the diff images and explicitly list the differences you
can see, at minimum:
- plot content
- panel count
- orientation
- axes
- category set/order
- palette / colormap
- labels
- legend
- background
- aspect ratio
- marker size/density
- layout

### 7. Diagnose and propose changes

Before modifying the code, produce a short repair plan:

- observed difference
- likely cause
- proposed change

Prioritize structural differences before aesthetic differences.

Example:

| Difference | Likely cause | Change |
|---|---|---|
| vertically flipped | image coordinates use opposite y direction | invert y-axis |
| category colors mismatched | palette/order mapping incorrect | rebuild category-color mapping |
| target is portrait | incorrect figsize | match target aspect ratio |

### 8. Repair and render attempt 2

Apply the proposed changes in one batched repair pass.

Re-run the plotting code and save the new figure.

Do not modify the target or fabricate data to improve similarity.

### 9. Compare attempt 2

Run `compare_figures.py` again on the repaired figure.

Inspect the new metrics and diff image.

Explicitly check:
- which previously identified differences were fixed
- which differences remain
- whether any new defects were introduced

The repaired figure is not considered verified until this second
comparison has been completed.

### 10. Optional final repair

If meaningful differences remain and the cause is clear:

1. propose the remaining change,
2. repair,
3. render attempt 3,
4. run `compare_figures.py` again,
5. inspect the result.

Repeat the loop.

Maximum: 5 total renders.

Do not perform more renders without subsequently running
`compare_figures.py`.


### 11. Finalize

Verify all required artifacts exist.

Write the repro note with:
- data fields/subset
- important parameters
- palette source
- verification result
- number of attempts
- deviations or blockers

Do not report completion unless all structural defects are resolved or
explicitly identified as unsupported by the available data.

## References

Read only when needed:

- `references/panel-geometry.md`
- `references/fidelity-check.md`
- `references/reflect-and-retry.md`
- `references/debugging-playbook.md`
- `references/domain-recipes.md`
