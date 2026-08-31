---
name: figure-reproduce-codex
description: Reproduce a supplied reference figure from its dataset with measured geometry, explicit color provenance, automated comparison, and bounded repair. Use when the user asks to recreate or closely match an existing scientific plot. Not for designing a new figure without a reference.
applies_to: [coding_agent]
status: disable
strict: true
---

# Evidence-driven figure reproduction

Rebuild the reference from the supplied data. Match both scientific meaning and
visible composition, and leave enough evidence for another agent to audit every
important choice.

## Inputs and boundaries

Require a readable target figure and the data needed to regenerate it. A caption,
methods section, source notebook, or supplied palette may also be used unless the
user excludes that source.

- Generate the result with analysis and plotting code. Never copy the target.
- Do not change data, labels, or thresholds merely to improve pixel similarity.
- Follow explicit source restrictions. “Do not use colormap.yaml” means do not
  read it as an input; a newly measured palette must have a different, clear name.
- Stop with an evidence-backed limitation when the data cannot support the panel.

## Required artifacts

Write under `project/outputs/`:

- `figures/<name>_attempt<N>.png` for every render and `<name>.png` as an exact
  copy of the accepted attempt;
- a vector copy when appropriate and the plotting source;
- `tables/plotted_data.csv` containing exactly the values and categories drawn;
- `tables/reference_spec.json`;
- `tables/resolved_colormap.yaml` and `tables/colormap_provenance.json` for a
  categorical panel, or an equivalent continuous-scale specification;
- `tables/compare_metrics_attempt<N>.json` and both comparison images per attempt;
- `reports/<name>_repro_note.md` and `reports/reproduction_validation.json`.

Here `project/` is the coding agent's workspace-relative alias for the active host
directory `workspace/projects/<active-id>/`. Use the relative alias with agent file
tools and bundled commands.

## Workflow

### 1. Inspect before choosing fields

Open the target and inspect the dataset schema. Identify the plot family, panel
count, plotted subset, coordinate/value fields, categorical or continuous
encoding, legend/colorbar, canvas, orientation, axes, annotations, and underlay.
Do not infer a field solely from its name when its values can be checked.

Read [references/plot-recipes.md](references/plot-recipes.md) only for the plot
family being reproduced.

### 2. Measure the target

Record normalized panel boxes, canvas aspect and background, data extent,
orientation, legend/colorbar placement, text, mark style, and annotations in
`reference_spec.json`. For a legend, run:

```bash
python3 project/skills/figure-reproduce-codex/scripts/extract_reference_spec.py \
  <target> --legend-box x0,y0,x1,y1 -o project/outputs/tables/reference_spec.json
```

Open the crop or specification and verify that every reported swatch is truly a
legend mark. Automatic detection is evidence, not permission to skip inspection.

### 3. Resolve color identity before rendering

Use an allowed source that gives category identity, color, and order. For visible
appearance, prefer a labeled target legend, then an explicitly authorized palette
known to belong to that target, then dataset metadata when the target lacks a named
binding. User-mandated source constraints override this order. If two named sources
contradict, stop and report the conflict rather than silently choosing one. Record
each category's source and confidence.
For AnnData metadata, inspect the categorical order and its paired
`adata.uns["<key>_colors"]`; accept it only when lengths match and every plotted
category has exactly one entry. Do not treat an ordered color list as a named
binding when the category order is absent or stale.

When OCR is absent, transcribe legend labels into a line-delimited file in detected
reading order. Use an explicit alias map for genuine spelling or naming variants.
Never silently reinterpret names, and never positionally align different counts.

```bash
python3 project/skills/figure-reproduce-codex/scripts/build_colormap.py \
  --dataset <data> --key <category-field> \
  --categories-file <plotted_categories.txt> \
  --reference-spec project/outputs/tables/reference_spec.json \
  --legend-labels <labels.txt> --label-aliases <aliases.json> \
  --provenance-out project/outputs/tables/colormap_provenance.json \
  -o project/outputs/tables/resolved_colormap.yaml
```

Exact-count positional binding is disabled unless a human-readable legend has been
checked and `--allow-exact-positional` is deliberately supplied. An unlabeled count
mismatch always returns nonzero. Different named vocabularies are safe when every
plotted category is resolved; unused reference labels remain explicit provenance.
When plotted categories are unresolved, the builder still writes partial provenance
but does not write a verified final palette.

If categories remain unresolved, read
[references/palette-recovery.md](references/palette-recovery.md). Registered pixel
inference is allowed only for a categorical scatter whose observations correspond
to visible reference points. Pass that partial provenance directly to the inference
helper as documented there. Otherwise stop rather than inventing colors.

### 4. Render from one specification

Make plotting code consume the inspected data subset, measured panel specification,
and resolved palette directly. Match category binding and order, axes and limits,
orientation, aspect, background/underlay, mark geometry, text, legend styling,
scale bars, panel letters, and other visible annotations. Save the plotted-data CSV
from the exact post-filter table passed to the plotting primitive.

Build the palette for the reviewed plotted subset via `--categories-file`. Before
plotting, assert that every plotted categorical value has a resolved palette key;
never allow a plotting library to fill a missing value with its default color.
Reference-only target categories must be rendered as legend-only handles when they
are visible in the target, but must never generate observations. Keep spatial
coordinates unmodified in `plotted_data.csv`; implement the required image
convention with explicit axis state such as `invert_yaxis()`.

### 5. Compare every attempt

After each render, run `compare_figures.py` with attempt-matched JSON, side-by-side,
and letterboxed geometry outputs. Open both images. Metrics cannot establish label
identity, semantic correctness, or category order; verify those against the spec
and provenance.

Read [references/fidelity-and-repair.md](references/fidelity-and-repair.md), name
concrete differences, and batch related corrections into the next attempt. Keep at
most five renders and one data/environment re-preparation. Stop early when no
concrete supported improvement remains.

User-stated constraints outrank metric suggestions. For example, a reflection score
must not remove a user-required inverted y-axis; instead verify panel registration
and document why that transform is fixed.

### 6. Validate and report

Select the best valid attempt, copy it byte-for-byte to the plain final filename,
then run `validate_reproduction.py`. Do not report success unless it returns zero.

The repro note must state data fields and subset, plot parameters, source constraints,
palette provenance, category vocabulary differences, attempt-by-attempt metrics and
repairs, accepted attempt, final visual assessment, and any residual limitation.

## Completion gate

- The figure was rendered from supplied data.
- Every visible encoding is supported by data or measured reference evidence.
- Every plotted category has explicit color provenance; none are unresolved.
- Each render has hash-bound metrics and inspected comparison images.
- The accepted attempt has no unexplained structural defect.
- The final validator reports `status: pass`.
