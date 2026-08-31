# Fidelity and bounded repair

## Compare

Run after every render:

```bash
python3 project/skills/figure-reproduce-codex/scripts/compare_figures.py \
  <target> <attempt.png> \
  --out <compare_attempt.png> \
  --geometry-out <geometry_attempt.png> \
  --json-out <compare_metrics_attempt.json>
```

The JSON binds metrics to SHA-256 hashes of both inputs. SSIM is a structural prior,
palette ΔE is an image-level color prior, and the geometry pass checks canvas shape,
background, and whether a reflection materially improves similarity. None proves
that the correct category owns each color.

Open both comparison images and check:

- scientific variable, values, subset, and panel count;
- category set, identity, order, and color binding;
- canvas, panel boxes, orientation, aspect, limits, and underlay;
- labels, ticks, units, legend/colorbar, annotations, and scale bars;
- marker size, density, opacity, line width, and drawing order.

## Repair

Write a concrete difference list before changing code. Classify each difference as
data/method, palette/identity, geometry/orientation, mark styling, text/annotation,
or environment. Apply the smallest principled fix and batch related visual changes
into one new render. Never edit an earlier attempt.

Use at most five renders and one environment or data-preparation restart. Keep the
best evidence-valid attempt. Stop when the comparison has no unexplained structural
finding, no supported change would shorten the difference list, or the remaining
gap requires missing data or undocumented preprocessing.

## Final validation

Run:

```bash
python3 project/skills/figure-reproduce-codex/scripts/validate_reproduction.py \
  --target <target> --final-figure <final.png> \
  --accepted-attempt <accepted_attempt.png> \
  --plotted-data project/outputs/tables/plotted_data.csv \
  --provenance project/outputs/tables/colormap_provenance.json \
  --repro-note project/outputs/reports/<name>_repro_note.md \
  --attempt-metrics <attempt1.json> <attempt2.json> ... \
  --out project/outputs/reports/reproduction_validation.json
```

The accepted attempt and final figure must be byte-identical. A failed validator is
an incomplete reproduction, not a warning to suppress.
