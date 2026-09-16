# Palette recovery

Use this reference only when a categorical palette is incomplete or uncertain.

## Evidence order

1. A labeled reference legend, measured by swatch.
2. A user-authorized palette known to belong to the target.
3. Dataset metadata binding category names to colors when the target lacks names.
4. Registered reference pixels for unresolved categories in a corresponding
   categorical scatter.

Never replace a disallowed source with the same source under a new filename. Keep
reference-only categories separate from dataset-only categories; neither implies a
positional shift.

Create `plotted_categories.txt` from the reviewed post-filter subset, one category
per line in intended order, and pass it as `--categories-file`. Categories present
only in unplotted dataset rows must not block palette resolution.

## Legend labels and aliases

`extract_reference_spec.py` detects repeated compact marks without rejecting pale
or neutral colors. It records vertical, horizontal, or grid reading order. Supply
`--legend-box` when auto-detection includes plot marks or misses an inset legend.
All boxes are `x0,y0,x1,y1` in source-image pixels, with `(0,0)` at the upper-left;
the right and lower bounds are exclusive.

If labels cannot be read reliably, create a UTF-8 text file containing exactly one
visually transcribed legend label per detected swatch. An alias JSON maps dataset
label to reference label:

```json
{
  "Dataset category name": "Reference legend name"
}
```

Aliases express reviewed identity. Do not add general spelling rewrites.

## Registered categorical-scatter inference

Use `infer_scatter_palette.py` only when the same observations are represented in
the target. Export the observations to CSV and provide the measured reference plot
box. The helper tests coordinate-axis order, inversions, padding, and translation
against already resolved categories.

For H5AD input:

```bash
python3 project/skills/figure-reproduce-codex/scripts/infer_scatter_palette.py \
  --reference <target> --dataset <data.h5ad> \
  --spatial-key spatial --category <obs-key> \
  --provenance project/outputs/tables/colormap_provenance.json \
  --plot-box x0,y0,x1,y1 \
  --inference-out project/outputs/tables/scatter_palette_inference.json \
  --colormap-out project/outputs/tables/resolved_colormap.yaml \
  --provenance-out project/outputs/tables/colormap_provenance.json
```

For CSV input, use `--dataset <points.csv> --x <column> --y <column>` instead of
`--spatial-key`. The category field is supplied by `--category`. The provenance
input is the partial JSON written by `build_colormap.py`; successful inference
merges evidence and writes the verified final palette. A nonzero exit leaves the
unresolved list in provenance and does not write a final palette.

An inference is accepted only when:

- known-category registration match rate is at least 20% at ΔE ≤12;
- the unresolved category contributes at least 25 usable samples and 10% coverage;
- its dominant color cluster contains at least 50% of usable samples;
- cluster spread is at most 5 ΔE at the 95th percentile;
- its centroid is at least 6 ΔE from every known category color.

Accepted entries use source `registered-reference-pixels`. If any category remains
in `unresolved_dataset_labels`, fail the reproduction. These thresholds are not
plotting parameters and must not be relaxed to force a match.

## Evidence shapes

`reference_spec.json` contains source path, image size, background RGB, and a
`legend` object with box, box source, layout, confidence, and ordered entries. Each
entry contains label, hex/RGB, pixel box, method, and confidence.

`colormap_provenance.json` contains `mapping`, per-category `provenance`,
`unresolved_dataset_labels`, `unused_reference_labels`, status, and registration
evidence when pixel inference ran. Plotting may proceed only when the unresolved
list is empty.
