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

Every render and every comparison is saved under an attempt suffix
(`<name>_attempt1.png`, `compare_figures_attempt1.png`,
`compare_figures_geometry_attempt1.png`, `compare_metrics_attempt1.json`, …) so
the repair trajectory is auditable. Copy the accepted attempt to the plain
`<name>` above; do not overwrite an earlier attempt.

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
- [ ] palette provenance tier verified and reconciled with plotted categories
- [ ] automated comparison executed after every render, each saved under its
      own attempt suffix
- [ ] no unresolved structural defects
- [ ] ≤5 render attempts
- [ ] residual differences documented
- [ ] repro note written


## Workflow

The bundled scripts live under `project/skills/figure-reproduce/scripts/`. Run
them by full path, e.g.:

```
python3 project/skills/figure-reproduce/scripts/build_colormap.py --help
```

A bare filename will not resolve. Run each script rather than reimplementing it.

### 1. Acquire and inspect the target

Obtain the target image/panel and caption.

Record:
- plot primitive and panel count
- orientation/aspect
- background/underlay
- categorical vs continuous encoding
- legend/colorbar, or whether category color lives in the marks
- visible text
- marker style
- unusual annotations

Confirm that the target crop contains only the panel being reproduced. Re-crop a
paper-page image that includes neighboring panels, captions, or orientation aids;
otherwise record the extra content and discount it during comparison.

### 2. Inspect the dataset

Identify the exact data subset and fields required for the figure:
coordinates/embedding, category/value field, genes/features, and
relevant metadata.

Record categorical values and their plotting order for palette reconciliation.

If required information is absent, stop and report the blocker.

### 3. Measure the reference

Run `scripts/extract_reference_spec.py`. For long legends, use
`--max-legend-entries`; `--max-colors` controls only the dominant-color summary.

Resolve:
- palette / colormap
- category order
- visible labels
- orientation and panel geometry

Treat measured values as the plotting specification.

### 4. Resolve palette

Run `scripts/build_colormap.py`.

Allowed sources, highest priority first:
1. supplied palette
2. dataset metadata
3. reference legend
4. reliable reference pixels

An explicit supplied palette remains authoritative. When a named reference
legend materially disagrees, the script retains the supplied colors and records
the conflict for the repro note.

If no trustworthy palette can be resolved, report a constraint
violation instead of silently using defaults.

The script measures colours; you own the pairing. Legends and datasets often
disagree — different spellings, a class the figure shows but the data lacks, a
scale bar counted as a swatch. When the script warns that counts differ or that
categories went unmatched, resolve it yourself by name and record the decision:
assign a neutral grey to categories the figure does not distinguish, and say in
the note which are measured and which are not.

Every category must end up with a colour, and no two categories may share one
unless you state that it is deliberate.

Confirm the written file with `scripts/build_colormap.py --verify`.

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
- legend styling (marker shape, size, ordering, placement)

Before drawing, assert that the resolved palette covers the post-filter table
actually passed to the plotting call:

```python
missing = sorted(set(plotted[category_col]) - set(palette))
assert not missing, f"no resolved colour for: {missing}"
```

Save as `<name>_attempt1.png`, plus the plotting code and plotted-data table.

### 6. Compare attempt 1

Run `scripts/compare_figures.py` on `<name>_attempt1.png` with `--attempt 1` and
save its JSON as `compare_metrics_attempt1.json`. The script writes distinct
`compare_figures_attempt1.png` and `compare_figures_geometry_attempt1.png` files
beside the reproduction by default. The first is a three-panel comparison:
target | reproduction | 50% overlay. The second is letterboxed and preserves
each image's shape.

```bash
python3 project/skills/figure-reproduce/scripts/compare_figures.py \
  <target.png> project/outputs/figures/<name>_attempt1.png \
  --attempt 1 --json > project/outputs/tables/compare_metrics_attempt1.json
```

Check both:
- content fidelity — the similarity metrics
- structural fidelity — `pass2_geometry.findings`; proceed only on `clean: true`

If the geometry comparison remains poor, first check whether the target crop
contains content the reproduction intentionally omits before changing plotting code.

Then inspect both comparison images, using the overlay panel to check alignment,
and explicitly list the differences you
can see, at minimum:
- plot content
- panel count
- orientation
- axes
- category set/order
- palette / colormap
- labels
- legend (presence, entries, order, marker shape)
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

Re-run the plotting code and save the new figure as `<name>_attempt2.png`.

Do not modify the target or fabricate data to improve similarity.

### 9. Compare attempt 2

Run `scripts/compare_figures.py` on `<name>_attempt2.png` with `--attempt 2`,
saving its JSON as `compare_metrics_attempt2.json`; keep the default distinct
`compare_figures_attempt2.png` and `compare_figures_geometry_attempt2.png` names.

Inspect the new metrics and diff images.

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
3. render attempt 3 (`<name>_attempt3.png`),
4. run `scripts/compare_figures.py` on it with `--attempt 3`, saving all outputs
   with the matching suffix,
5. inspect the result.

Repeat the loop.

Maximum: 5 total renders.

Do not perform more renders without subsequently running
`scripts/compare_figures.py`.

Stop when the remaining mismatch is caused by unavailable or different data and
no longer responds to plotting changes. Record the limitation instead of spending
the remaining attempts on it.


### 11. Finalize

Copy the accepted attempt byte-for-byte to the plain `<name>` filenames; never
re-render during finalization. Then verify all required artifacts exist. Keep
every attempt on disk.

Write the repro note with:
- data fields/subset
- important parameters
- palette source tier, reconciliation result, and any unrecovered color
- verification result
- number of attempts, and the metric trajectory across them
- category vocabulary differences (naming, extra/missing classes)
- target-crop content not reproduced
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
