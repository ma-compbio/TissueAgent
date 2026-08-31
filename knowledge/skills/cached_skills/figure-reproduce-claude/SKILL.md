---
name: figure-reproduce-claude
description: Reproduce a target figure from a dataset — regenerate a published/reference plot (e.g. a scatter, line/bar chart, heatmap, UMAP, dotplot, violin, or spatial map from a paper) using the coding agent and matching its panels, layout, and color encoding. Use when the user asks to "reproduce", "recreate", "replicate", or "remake" a figure, or to match a figure from a paper/notebook. Covers self-evaluation of the result and a bounded reflect-and-retry repair loop when the first attempt is off.
applies_to: [coding_agent]
status: disable
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
(`<name>_attempt1.png`, `compare_metrics_attempt1.json`, …) so the repair
trajectory is auditable. Copy the accepted attempt to the plain `<name>` above;
do not overwrite an earlier attempt.

## Invariants

1. Generate the figure by running analysis/plotting code on the data.
   Never copy, decode, download, or synthesize the target image.
2. Do not guess palette, category order, labels, orientation, or
   colormap direction when they can be measured.
3. Never silently substitute a default palette.
4. **A measurement that reports low confidence is not a measurement.** Every
   extractor here reports whether it ran *and* whether to believe it. Acting on an
   unvalidated reading is the same error as guessing, with more ceremony.
5. Every reproduction must be compared against the target.
6. Structural mismatches must be fixed before completion.
7. Maximum 5 render attempts and 1 data/environment re-preparation.
8. Any unresolved mismatch or unsupported feature must be recorded in
   the repro note.

## Completion Gate

Do not report success unless all are true:

- [ ] figure rendered from supplied data
- [ ] plotted-data CSV written
- [ ] palette provenance verified (`build_colormap.py --verify`) and its **tier**
      recorded in the repro note
- [ ] the palette source was reconciled against the dataset's categories
- [ ] automated comparison executed after every render, each saved under its
      own attempt suffix
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
- legend/colorbar — **or neither**: note whether category colour lives in a legend,
  in the marks themselves, or in a colorbar. This choice drives step 4.
- visible text
- marker style
- unusual annotations

**Check what the target crop actually contains.** A crop taken from a paper page
often carries more than the panel: a neighbouring subpanel, an orientation compass,
a caption block, a scale bar. Anything in the target that your panel will not draw
becomes a permanent, unfixable "difference" that every metric reports and that no
re-render can close. Re-crop to the panel first, or record explicitly what extra
content the target carries and discount it when judging.

### 2. Inspect the dataset

Run `scripts/inspect_dataset.py`.

Identify the exact data subset and fields required for the figure:
coordinates/embedding, category/value field, genes/features, and
relevant metadata.

Record the **category count and their order** — step 4 reconciles the measured
palette against these, and step 5 iterates in this order.

If required information is absent, stop and report the blocker.

### 3. Measure the reference — and validate the measurement

Run `extract_reference_spec.py`.

Resolve:
- palette / colormap
- category order
- visible labels
- orientation and panel geometry

Then read the **confidence**, not just the status:

| Field | Question it answers |
|---|---|
| `legend.status` | did the parser run? |
| `legend.confidence` | should you believe it — `high` / `low` / `rejected`? |
| `legend.evidence` | the numbers behind that verdict |

Only `confidence: high` licenses building a palette from legend entries. At `low`,
reconcile the entry count against the dataset's categories before trusting any
pairing. At `rejected`, there is no legend here — go to step 4's other branches.

If the legend box was autodetected, the report says so; check it with
`--debug-crops` and pass `--legend-box x0,y0,x1,y1` when it looks wrong. For a
legend with many entries pass `--max-legend-entries` generously — papers routinely
show 20–40 categories.

Treat validated values as the plotting specification.

### 4. Resolve palette

Run `build_colormap.py`. **Read `references/palette-recovery.md` before this step**
— it is the decision tree for every figure kind, and the rest of this section is
its summary.

**Prefer what the target actually shows.** Order the sources by which one is
*evidence about this figure*, not by which is most convenient to read:

1. **a labelled reference legend** (`--reference [--legend-box …]`) — the only
   source that binds a name to the colour the target actually renders
2. **per-category mark colours** (`--reference --marks-box …`) — the legendless
   equivalent, for bar / violin / box / strip panels where colour lives in the
   marks and the names live on the tick axis
3. a palette the user supplied *for this target* (`--palette`)
4. dataset metadata (`--dataset --key`) — only when the target carries no names
5. documented default (`--allow-default`) — records a DEVIATION; this is an
   admission, not a palette

**Dataset metadata ranks below the legend, and this is not a technicality.** An
ordered colour list stored beside a category column is not a *named binding* to
this figure: it is whatever the last tool to plot the object happened to write
there. Measured on a real task, `adata.uns["<key>_colors"]` was byte-identical to
the plotting library's own default palette and sat a mean RGB distance of 127 from
the published figure's colours — every category wrong, in a source that looks
authoritative because it is stored, correctly keyed and correctly ordered. Accept
it only when the target genuinely shows no names, and even then **spot-check two
or three categories against reference pixels before trusting it**. A stored
palette that disagrees with the panel loses to the panel.

If two named sources disagree, stop and report the conflict rather than silently
picking one.

Reconcile before plotting: legend/mark entry count vs dataset category count. When
they differ, know which of the three ordinary reasons applies (figure shows classes
the data lacks / a swatch went undetected / the panel drops a class) and say so.
Categories in the reference but not the data are **legend-only handles**: draw them
in the legend if the target shows them, but they must never generate observations.

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
- legend styling (marker shape, size, ordering, placement)

**Assert the palette covers the plotted subset before drawing:**

```python
missing = sorted(set(plotted[category_col]) - set(palette))
assert not missing, f"no resolved colour for: {missing}"
```

This is the last line of defence and it is one line. Every plotting library
silently fills an unmapped category with a default colour, so a single unresolved
label becomes an invented colour in the output with nothing in the logs to show
it — the exact failure the palette tiers exist to prevent, arriving after they
have all passed. Assert on the **post-filter** table actually handed to the
plotting call, not the full dataset.

Save as `<name>_attempt1.png`, plus the plotting code and plotted-data table.

### 6. Compare attempt 1

Run `compare_figures.py` on `<name>_attempt1.png` and save its JSON and both diff
images under the same attempt suffix (the side-by-side and the letterboxed
`--geometry-out`, which preserves shape).

Check both:
- content fidelity — the similarity metrics
- structural fidelity — `pass2_geometry.findings`; proceed only on `clean: true`

`pass2_geometry.alignment` reports the best content-mask IoU under a small
scale/offset search. Read it as a framing signal: a good IoU at a scale far from
1.0 means the panel is drawn at the wrong size (a figsize fix, not a data fix). A
**low** IoU that alignment cannot rescue usually means the target crop contains
something your panel does not — revisit step 1 before re-plotting.

Then inspect the diff images and explicitly list the differences you
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
| content matches but sits smaller | panel drawn at wrong extent | adjust figsize / axes extent |

### 8. Repair and render attempt 2

Apply the proposed changes in one batched repair pass.

Re-run the plotting code and save the new figure as `<name>_attempt2.png`.

Do not modify the target or fabricate data to improve similarity.

### 9. Compare attempt 2

Run `compare_figures.py` on `<name>_attempt2.png`, saving its JSON and diff
images with the `_attempt2` suffix.

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
4. run `compare_figures.py` on it, saving with the matching suffix,
5. inspect the result.

Repeat the loop.

Maximum: 5 total renders.

Do not perform more renders without subsequently running
`compare_figures.py`.

**Stop when the remaining gap is in the data, not the code.** A metric that has
stopped responding to your changes is telling you the difference is no longer
yours to close — for example marker size that no longer moves the overlap because
the target simply contains cells your dataset does not. Record it and stop; more
attempts spent there buy nothing.

### 11. Finalize

Copy the accepted attempt to the plain `<name>` filenames **byte-for-byte** — copy
the file, never re-render it. A re-render is a new attempt with no comparison
behind it, so the metrics you are about to report would describe a different image
than the one you shipped. Keep every attempt on disk.

Write the repro note with:
- data fields/subset
- important parameters
- **palette source tier**, and how any unrecovered or hand-added colour was obtained
- verification result
- number of attempts, and the metric trajectory across them
- category vocabulary differences (naming, extra/missing classes)
- content present in the target crop but not in the panel
- deviations or blockers

Do not report completion unless all structural defects are resolved or
explicitly identified as unsupported by the available data.

## References

Read only when needed:

- `references/palette-recovery.md` — **read before step 4**; colour recovery for
  every figure kind, and how to tell a real measurement from a plausible one
- `references/panel-geometry.md`
- `references/fidelity-check.md`
- `references/reflect-and-retry.md`
- `references/debugging-playbook.md`
- `references/domain-recipes.md`
