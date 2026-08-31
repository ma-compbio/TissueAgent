# Domain recipes — concrete per-plot recipes

One good, adaptable recipe per plot family. Each says **what to confirm in the
data** (run `scripts/inspect_dataset.py` first), the **primitive** to reach for,
and the **fidelity tips** that separate B4 from B2. Examples are domain-agnostic
(`pandas`/`matplotlib`/`seaborn`) with a light `scanpy` alternative where the
target is an omics figure. Always: plot **only the shown subset**, copy labels
**verbatim**, save to `outputs/figures/`, and export the plotted-data CSV.

> **The colors and orders below come from the measured target spec, not from this
> page.** Copying a literal palette or `cmap` from a recipe is how a reproduction
> ends up with the recipe's colors instead of the paper's. Every recipe assumes this
> preamble, from `scripts/extract_reference_spec.py <target> -o spec.yaml`:
>
> ```python
> import yaml
> spec = yaml.safe_load(open("spec.yaml"))
> entries    = spec["legend"]["entries"]                # ORDERED [{hex, label}, ...]
> spec_hexes = [e["hex"] for e in entries]              # measured colors, IN TARGET ORDER
> spec_cmap  = (spec["colorbar"] or {}).get("best")     # e.g. "RdBu_r" — mind the _r
>
> labels = [e["label"] for e in entries]
> if any(l is None for l in labels):
>     # No OCR: the ORDER and the HEXES are still valid — only the names are missing.
>     # Read the legend text off the panel yourself and list it in the SAME order.
>     labels = ["<read from the panel, top→bottom>"]    # must match len(spec_hexes)
> assert len(labels) == len(set(labels)) == len(spec_hexes), "labels must be unique & aligned"
> spec_order   = labels
> spec_palette = dict(zip(labels, spec_hexes))
> ```
>
> The `assert` matters: building the palette dict straight from `null` labels
> collapses every entry onto one key and silently throws the rest of the palette
> away.

## Scatter / embedding (UMAP, t-SNE, PCA)

Confirm: two coordinate columns (or an `.obsm` embedding) + one color field.

```python
import matplotlib.pyplot as plt, pandas as pd
df = pd.read_csv("uploads/plotted_data.csv")
order = spec_order                           # from spec.yaml legend.entries (target order)
palette = spec_palette                       # {label: "#RRGGBB"} measured from the target
fig, ax = plt.subplots(figsize=(4, 4))
for g in order:                              # loop in the target's order → legend + z-order match
    d = df[df["group"] == g]
    ax.scatter(d["umap_1"], d["umap_2"], s=6, c=palette[g], label=g, linewidths=0)
ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
ax.set_aspect("equal"); ax.legend(title="group", markerscale=2, frameon=False)
```
Omics alt: `sc.pl.umap(adata, color="cell_type", show=False)` (set
`adata.uns["cell_type_colors"]` for an exact palette).
Fidelity tips: match **category order + palette** (biggest B-level lever); equal
aspect; same point size; for continuous color match the colormap + value range
(`vmin/vmax`). Stochastic embeddings: set the seed and accept a rotated/mirrored
but structurally identical result as B3.

## Heatmap / clustered matrix

Confirm: the matrix (rows × columns) and whether rows/cols are **clustered** or in
a fixed order; the colormap and whether values are scaled (z-score per row).

```python
import seaborn as sns, pandas as pd
m = pd.read_csv("uploads/matrix.csv", index_col=0)
sns.clustermap(m, cmap=spec_cmap, z_score=0,   # cmap from spec.yaml colorbar.best (mind _r)
               row_cluster=True, col_cluster=False,
               figsize=(6, 8), cbar_kws={"label": "z-score"})
```
Omics alt: `sc.pl.heatmap` / `sc.pl.matrixplot`. Fidelity tips: a paper "heatmap"
may be a **clustermap** (with dendrograms), a **matrixplot**, or a **dotplot** —
match the actual encoding. Preserve row/column order (fixed vs clustered) and the
scaling; a mismatched colormap or unscaled values is a common B2 cause.

## Dotplot (size + color)

Confirm: two categorical axes + a size variable (e.g. fraction expressing) + a
color variable (e.g. mean value).

```python
import matplotlib.pyplot as plt, pandas as pd, numpy as np
df = pd.read_csv("uploads/dotplot.csv")       # cols: feature, group, frac, mean
xs = {g:i for i,g in enumerate(df["group"].unique())}
ys = {f:i for i,f in enumerate(df["feature"].unique())}
sc = plt.scatter([xs[g] for g in df["group"]], [ys[f] for f in df["feature"]],
                 s=df["frac"]*200, c=df["mean"], cmap=spec_cmap)   # measured, not guessed
plt.xticks(range(len(xs)), list(xs), rotation=90); plt.yticks(range(len(ys)), list(ys))
plt.colorbar(sc, label="mean"); 
```
Omics alt: `sc.pl.dotplot(adata, var_names, groupby="cell_type")`. Fidelity tips:
match the **size legend scale** and color range; keep the feature/group order shown.

## Bar / line chart

Confirm: category (or x) column + value column(s); error bars; ordering.

```python
import matplotlib.pyplot as plt, pandas as pd
df = pd.read_csv("uploads/bars.csv")          # cols: method, score, sem
df = df.set_index("method").loc[spec_order]             # target's order, curated subset
bar_color = spec["palette_by_frequency"][0]["hex"]       # the panel's dominant measured color
ax = df["score"].plot.bar(yerr=df["sem"], color=bar_color, capsize=3, figsize=(4,3))
ax.set_ylabel("score"); ax.set_xticklabels(df.index, rotation=45, ha="right")
```
Fidelity tips: reproduce the **exact bars shown** (curated subset + order), include
error bars if the panel has them, copy axis titles/units verbatim.

## Violin / box (distributions)

Confirm: a value column + a grouping column; whether points are overlaid.

```python
import seaborn as sns, pandas as pd
df = pd.read_csv("uploads/dist.csv")
order = spec_order                            # target's group order, from the spec
sns.violinplot(data=df, x="group", y="value", order=order, cut=0, inner="box")
```
Omics alt: `sc.pl.violin(adata, keys="gene", groupby="cell_type")`. Fidelity tips:
match the group order, the inner representation (box/quartiles/points), and whether
the tails are clipped (`cut=0`).

## Spatial map (points over tissue)

Confirm: spatial coordinates (`.obsm["spatial"]` or x/y columns), the color field,
and whether a **histology/background image** underlies the points.

```python
import matplotlib.pyplot as plt
# keep the tissue image as the underlay — do NOT draw on plain white
ax = plt.subplots(figsize=(5,5))[1]
ax.imshow(background_img)                        # the paper's H&E / tissue image
sctr = ax.scatter(xy[:,0], xy[:,1], c=values, s=4, cmap=spec_cmap)  # incl. _r direction
ax.set_aspect("equal"); ax.axis("off"); plt.colorbar(sctr)
```
Omics alt: `sc.pl.spatial(adata, color="cell_type", img_key="hires")` /
`sq.pl.spatial_scatter(...)`. Fidelity tips: the **background underlay** is the #1
lever here; also match spot size, coordinate orientation (y often flipped), and the
palette. A spatial map on a white canvas reads as a clear miss.

## Legendless categorical panels (bar / violin / box / strip)

These are the panels whose palette lives in the **marks**, not a legend: categories
are named on the tick axis and told apart by colour. Legend extraction is the wrong
tool by construction, so recover the palette from the marks themselves (tier 4):

```bash
python scripts/build_colormap.py --reference TARGET \
       --marks-box X0,Y0,X1,Y1 --marks-axis x \
       --dataset data.h5ad --key cell_type -o colormap.yaml
```

`--marks-box` is the axes interior, not the whole figure. Each mark is a contiguous
run along the category axis, so the runs give the colours **in plotting order**.

Fidelity tips: the order IS the pairing — mark *i* is category *i*, so confirm the
first and last against the panel before trusting it. Expect tick labels not to OCR
(a rotated 20-category axis defeats it); take the names from the dataset in that
same order rather than accepting a partial OCR. Sort the categories the way the
panel does — these panels are almost always sorted by a statistic (descending
median, say), not alphabetically, and that ordering is part of the figure.

## Choosing the primitive

Use `search_documentation` (or `--help`) to confirm the exact call. If unsure which
family the target is, name what you see: *how many axes carry meaning*, *is size or
color encoding a variable*, *is there clustering/dendrograms*, *is there a
background image*. That description picks the recipe.

---

## Full worked template (moved from the skill body)

```python
import matplotlib.pyplot as plt
from pathlib import Path

out = Path("outputs/figures"); out.mkdir(parents=True, exist_ok=True)

# ── colors come from colormap.yaml (step 5), never from library defaults ─────
import yaml
palette = yaml.safe_load(open("colormap.yaml"))   # {category: "#RRGGBB"}, ordered
order   = list(palette)                            # the target's category order
# build_colormap.py stamped the source tier in the file's header comment — if it
# says "5-default", these are NOT the target's colors: say so in the repro note.

# For a continuous panel, take the colormap from the measured spec instead:
#   spec = yaml.safe_load(open("spec.yaml"))
#   cmap = spec["colorbar"]["best"]                # e.g. "RdBu_r" — mind the _r

# ── domain-agnostic table example ────────────────────────────────────────────
import pandas as pd
df = pd.read_csv("uploads/plotted_data.csv")
print(df.shape, list(df.columns), df.dtypes.to_dict())   # confirm fields first
sub = df[df["group"].isin(order)]             # ONLY the subset the panel shows
fig, ax = plt.subplots(figsize=(4, 4))
for g in order:                               # loop IN ORDER → legend + z-order match
    d = sub[sub["group"] == g]
    ax.scatter(d["x"], d["y"], s=6, c=palette[g], label=g, linewidths=0)
ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")   # labels VERBATIM from the target
ax.legend(title="group")
plt.savefig(out / "reproduced.png", dpi=200, bbox_inches="tight")
plt.savefig(out / "reproduced.pdf", bbox_inches="tight")      # vector copy
sub.to_csv(out / "reproduced_points.csv", index=False)         # audit/reuse

# Continuous color instead of categories? Use the identified colormap, not a default:
#   cmap = spec["colorbar"]["best"]           # e.g. "RdBu_r" — note the _r
#   ax.scatter(d["x"], d["y"], c=d["value"], cmap=cmap, vmin=lo, vmax=hi)

# ── omics example (light): a spatial scatter colored by cell type ────────────
# import scanpy as sc
# adata = sc.read_h5ad("uploads/dataset.h5ad")
# print(adata.shape, list(adata.obs.columns), list(adata.obsm.keys()))
# adata.obs["cell_type"] = adata.obs["cell_type"].cat.reorder_categories(order)
# adata.uns["cell_type_colors"] = [palette[c] for c in order]   # exact palette
# sc.pl.embedding(adata, basis="spatial", color="cell_type", show=False)
# plt.gca().set_aspect("equal"); plt.axis("off")
# plt.savefig(out / "reproduced.png", dpi=200, bbox_inches="tight")
```

**Never** `color="blue"` / `"tab:blue"` / `C0`, and never an unexamined default
`cmap`. Every color in the reproduction should trace to a value you measured.

Concrete per-plot recipes (scatter/UMAP, heatmap, dotplot, bar/violin, spatial):
`references/domain-recipes.md`.
