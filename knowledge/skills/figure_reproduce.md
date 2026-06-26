---
name: figure-reproduce
description: Reproduce a target figure from a dataset — regenerate a published/reference plot (e.g. a spatial scatter, UMAP, heatmap, dotplot from a paper) using the coding agent and matching its panels, layout, and color encoding. Use when the user asks to "reproduce", "recreate", "replicate", or "remake" a figure, or to match a figure from a paper/notebook.
applies_to: [coding]
status: enable
---

# Figure Reproduction

## When to use

The user wants an existing figure **recreated from data** — a paper panel, a notebook plot, or a
previously produced figure — so the output matches the target's content and appearance.

- Use when the user says "reproduce / recreate / replicate / remake figure X", "match this plot",
  or "make the same figure as the paper".
- This is a **coding-agent** task: there is no dedicated reproduction tool. You drive it with the
  coding agent's `python` / `r` execution and `search_documentation`.
- If the target lives in a **paper PDF**, the `pdf_reader` agent extracts the figure image and its
  caption first; this skill then reproduces it from the dataset.
- **Not** for designing a brand-new figure with no reference — that's ordinary plotting, not
  reproduction. And don't use it to fabricate data to match a figure; reproduce only what the data
  supports.

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

## Workflow

1. **Acquire the target.** If it's a paper figure, recruit `pdf_reader` to pull the figure image
   and caption. Identify plot type, panels, and the color/encoding to match.
2. **Inspect the dataset** with the `python` tool — load the `.h5ad`, print `.shape`, `.obs.columns`,
   `.obsm.keys()`, and candidate color columns / genes. Confirm every field the figure needs exists.
3. **Find the plotting API** with `search_documentation` (scanpy / squidpy / liana) — e.g.
   `sc.pl.spatial`, `sc.pl.umap`, `sc.pl.dotplot`, `sc.pl.heatmap` — to match the target's plot kind.
4. **Render a first pass** with `python`, saving to `outputs/figures/`. The tool returns the image
   inline; **visually compare** it to the target.
5. **Iterate** on color map, panel layout, point size, ordering, and labels until content and
   appearance match. Keep edits minimal and intentional.
6. **Export the plotted-data CSV** and write the repro note (fields used, params, deviations).

## Code Template

```python
import scanpy as sc
import matplotlib.pyplot as plt
from pathlib import Path

out = Path("figures"); out.mkdir(exist_ok=True)   # under the project's outputs/
adata = sc.read_h5ad("uploads/dataset.h5ad")

# Inspect what's available before plotting
print(adata.shape, list(adata.obs.columns), list(adata.obsm.keys()))

color = "cell_type"          # the field the target colors by
# Reproduce, e.g., a spatial scatter colored by cell type
sc.pl.embedding(adata, basis="spatial", color=color, show=False)
plt.gca().set_aspect("equal"); plt.axis("off")
plt.savefig(out / "reproduced.png", dpi=200, bbox_inches="tight")
plt.savefig(out / "reproduced.pdf", bbox_inches="tight")   # vector copy

# Export exactly what was plotted, for audit/reuse
import pandas as pd
xy = adata.obsm["spatial"]
pd.DataFrame({"x": xy[:, 0], "y": xy[:, 1], color: adata.obs[color].values}) \
  .to_csv(out / "reproduced_points.csv", index=False)
```

## Common Issues

- **Missing field → can't reproduce as-is.** The target colors by a column/embedding the dataset
  lacks (no `X_umap`, no `cell_type`). Compute it if the data supports it (run the relevant
  analysis first, e.g. annotation/clustering), or reproduce the closest supported variant and say so.
- **Gene symbol vs ID mismatch.** A figure by gene won't plot if `var_names` use a different ID
  scheme — map identifiers first.
- **Color/category mismatch.** Categories render in a different order or palette than the target —
  set an explicit category order and color map to match; don't rely on defaults.
- **Wrong plot primitive.** A "heatmap" in a paper may be a clustermap, matrixplot, or dotplot —
  match the actual encoding (use `search_documentation` to pick the right `sc.pl.*`).
- **No backend / blank image.** Figure reproduction runs in the coding sandbox; a missing kernel
  produces no inline image. Ensure the Jupyter Kernel Gateway is reachable before plotting.
- **Over-matching.** Don't tweak data or thresholds just to make the picture look identical —
  reproduce what the data legitimately yields and document differences.

## References

- Driven by the coding agent (id `coding`) tools: `python`, `r`, `search_documentation`
  (`src/agents/agent_registry/coding_agent/model.py`).
- Target extraction from papers: `pdf_reader` agent.
- Related plan template: `spatial_scatter` (`knowledge/plans/spatial_scatter.md`) — a concrete
  figure recipe with coords/color/checks.
- External: scanpy `sc.pl.*`, squidpy `sq.pl.*` plotting APIs (searchable via `search_documentation`).
