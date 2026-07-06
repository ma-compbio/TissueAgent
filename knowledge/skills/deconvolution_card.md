---
name: card-deconvolution
description: Estimate per-spot cell type proportions on spot-based spatial data (10x Visium, Slide-seq, ST) with CARD, a reference-based conditional-autoregressive deconvolution method that borrows spatial correlation across neighboring spots. An R-package alternative to cell2location, driven by the coding agent's `r` tool. Use when the user asks to deconvolve spots with CARD specifically, or wants a spatially-aware / R-based deconvolution method.
applies_to: [coding_agent]
tags: [deconvolution, spatial, CARD, R]
status: enable
---

# Cell Type Deconvolution — CARD (R)

## When to use

Spot-based spatial data (each capture location holds many cells: 10x Visium,
Slide-seq, ST) where you want **per-spot cell type proportions** by mapping an
annotated scRNA-seq reference. CARD ([YMa-lab/CARD](https://github.com/YMa-lab/CARD))
adds a **conditional autoregressive (CAR)** prior so neighboring spots inform
each other — often smoother, more spatially coherent proportions than
non-spatial methods.

- Use when the user **names CARD**, wants a spatially-aware deconvolution, or
  wants an R-based alternative to the built-in cell2location tool.
- For the codebase's default, tool-backed deconvolution (Bayesian, with
  uncertainty, Python), prefer [[cell2location-deconvolution]] (cell2location).
- **Do not** use for single-cell-resolution platforms (MERFISH, Xenium, CosMx,
  seqFISH) — those get a per-cell label, not deconvolution. See [[cell-type-annotation]].
- CARD is a **coding-agent** task run through the `r` execution tool; there is
  no dedicated CARD tool in this codebase.

## Prerequisites (read first)

- CARD is an **R package** and needs the **R (IRkernel) kernel**, which exists
  only in the **Docker sandbox** (`docker/Dockerfile`, `FROM r-base` + IRkernel).
  A local Kernel Gateway typically has **Python only** — enable the Docker
  sandbox in Settings before running CARD, or the `r` tool will have no R kernel.
- CARD is **not pre-installed** in the image. Install it once per kernel session
  (see Workflow step 0). Installing from GitHub pulls compilation deps; if it
  fails, record it as an obstacle rather than silently switching methods.

## Input

- **Reference scRNA-seq** — **raw counts**, `genes × cells`, plus a cell-metadata
  table (`data.frame`, rows = cells) with a **cell-type column** and a
  **sample/subject column**.
- **Spatial data** — **raw counts**, `genes × spots`, plus a **spatial location**
  `data.frame` with columns `x`, `y` and `rownames` = spot IDs (matching the
  spatial count colnames).
- Gene identifiers should match between reference and spatial (both symbols or
  both Ensembl); reconcile first if they differ.
- Data usually lives in `.h5ad`. Bridge to R either by exporting the four pieces
  to CSV/MTX from Python first (simplest, robust), or reading the `.h5ad` in R.
  The Python-export bridge is recommended and shown below.

**`createCARDObject` arguments** (all required unless noted):

- `sc_count` — sparse/dense matrix, **genes × cells** (raw counts).
- `sc_meta` — `data.frame`, rows = cells (rownames match `sc_count` colnames).
- `spatial_count` — matrix, **genes × spots** (raw counts).
- `spatial_location` — `data.frame` with `x`, `y`; rownames = spot IDs.
- `ct.varname` — the `sc_meta` column holding cell-type labels (e.g. `"cellType"`).
- `ct.select` — vector of cell types to deconvolve (usually `unique(sc_meta$cellType)`).
- `sample.varname` — the `sc_meta` column holding sample/subject id (e.g. `"sampleInfo"`).
- `minCountGene` (default `100`) — min counts per spot.
- `minCountSpot` (default `5`) — min non-zero spots per gene.

## Output

- `CARD_obj@Proportion_CARD` — **spots × cell types** proportion matrix (rows sum
  to ~1). Export to `outputs/tables/card_proportions.csv` for downstream use.
- Optional high-resolution: `CARD.imputation(...)` →
  `CARD_obj@refined_prop` (imputed proportions on a denser grid) and
  `CARD_obj@refined_expression`.
- Optional single-cell mapping: `CARD_SCMapping(...)` →
  a `SingleCellExperiment` with per-cell coordinates + cell-type assignments.
- Figures: spatial proportion maps via `CARD.visualize.prop`.

## Success Criteria

- `CARD_obj@Proportion_CARD` exists, is `spots × cell types`, non-empty, and rows
  sum to ~1; columns are the reference's cell types (from `ct.select`).
- The proportions CSV is written and its spot count matches the filtered spatial
  data.
- **Sanity check:** a known marker's spatial expression tracks the inferred
  proportion of the cell type that expresses it.
- **Honest-failure:** if R/IRkernel is unavailable (Docker sandbox off) or the
  install fails, say so and name the blocker — do not silently fall back to
  another method without telling the user.

## Workflow

0. **Environment + install (once per kernel session).** Confirm the R kernel is
   reachable (Docker sandbox on). Install CARD:
   ```r
   if (!requireNamespace("CARD", quietly = TRUE)) {
     install.packages(c("remotes"), repos = "https://cloud.r-project.org")
     remotes::install_github("YMa-lab/CARD")
   }
   library(CARD)
   ```
   (Upstream docs also reference `devtools::install_github('YingMa0107/CARD')`;
   the `YMa-lab/CARD` repo is the maintained one.)
1. **Bridge the data from `.h5ad` to R** (Python `python` tool): load reference +
   spatial AnnData, write `sc_count` (genes×cells), `sc_meta` (with cell-type &
   sample columns), `spatial_count` (genes×spots), and `spatial_location`
   (`x`,`y`, spot rownames) to `outputs/card_input/` as CSV/MTX. Confirm raw
   counts and matching gene IDs.
2. **Build + run CARD** (`r` tool): `createCARDObject(...)` then
   `CARD_deconvolution(CARD_object = CARD_obj)`.
3. **Export** `CARD_obj@Proportion_CARD` to `outputs/tables/card_proportions.csv`.
4. **Visualize** a few cell types with `CARD.visualize.prop`, save to
   `outputs/figures/`.
5. *(Optional)* higher resolution with `CARD.imputation`, or single-cell mapping
   with `CARD_SCMapping`.
6. **Verify** against Success Criteria and summarize the proportion table + paths.

## Code Template

Inputs (`sc_count`, `sc_meta`, `spatial_count`, `spatial_location`) are prepared
by the Python bridge (Workflow step 1) under `outputs/card_input/`:
`sc_count`/`spatial_count` are genes × cells|spots (raw counts); `sc_meta` has
rows = cells with `cellType` + `sampleInfo` columns; `spatial_location` has
`x`,`y` with rownames = spot IDs.

**Step 2a — build the CARD object**

```r
library(CARD)

CARD_obj <- createCARDObject(
  sc_count         = sc_count,
  sc_meta          = sc_meta,
  spatial_count    = spatial_count,
  spatial_location = spatial_location,
  ct.varname       = "cellType",
  ct.select        = unique(sc_meta$cellType),
  sample.varname   = "sampleInfo",
  minCountGene     = 100,
  minCountSpot     = 5
)
```

**Step 2b — run deconvolution**

```r
CARD_obj <- CARD_deconvolution(CARD_object = CARD_obj)
```

**Step 3 — export proportions (spots × cell types)**

```r
prop <- CARD_obj@Proportion_CARD
write.csv(prop, "outputs/tables/card_proportions.csv")
```

**Step 4 — spatial proportion maps for a few cell types**

```r
p <- CARD.visualize.prop(
  proportion       = CARD_obj@Proportion_CARD,
  spatial_location = CARD_obj@spatial_location,
  ct.visualize     = colnames(prop)[1:min(4, ncol(prop))],
  colors           = c("lightblue", "lightyellow", "red"),
  NumCols          = 4, pointSize = 3.0
)
ggplot2::ggsave("outputs/figures/card_proportions.png", p, width = 12, height = 4, dpi = 150)
```

**Step 5 (optional) — high-resolution imputation**

```r
CARD_obj <- CARD.imputation(CARD_obj, NumGrids = 2000, ineibor = 10, exclude = NULL)
refined <- CARD_obj@refined_prop
```

## Common Issues

- **No R kernel → the `r` tool fails.** IRkernel exists only in the Docker
  sandbox; enable it in Settings. A Python-only local gateway can't run CARD.
- **`install_github` fails.** Missing system/compilation deps or network. Report
  the blocker; don't switch methods silently. Retry `remotes::install_github`.
- **Wrong matrix orientation.** CARD wants **genes × cells** and **genes × spots**;
  AnnData is cells/spots × genes — **transpose** on export.
- **Metadata mismatch.** `rownames(sc_meta)` must equal `colnames(sc_count)`;
  `rownames(spatial_location)` must equal `colnames(spatial_count)`. Misaligned
  names silently drop cells/spots or error.
- **Gene-ID mismatch → few shared genes.** Symbols vs. Ensembl between reference
  and spatial — reconcile before building the object.
- **Normalized instead of raw counts.** CARD expects raw counts; export `.X`/raw
  layer, not a log-normalized matrix.
- **Wrong `ct.varname`/`sample.varname`.** Pass the reference's real annotation
  and sample columns; wrong columns produce meaningless signatures.

## References

- External: CARD paper (Ma & Zhou, *Nat Biotechnol* 2022), repo
  [YMa-lab/CARD](https://github.com/YMa-lab/CARD), tutorial
  https://yma-lab.github.io/CARD/.
- Driven by the coding agent (`coding_agent`) `r` / `python` tools; no dedicated
  CARD tool in this codebase.
- Related skills: [[cell2location-deconvolution]] (cell2location, the tool-backed
  Python default) and [[tangram-deconvolution]] (Tangram, Python) — same problem,
  different methods; and [[cell-type-annotation]] for single-cell-resolution platforms.
