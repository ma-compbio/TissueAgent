---
name: tangram-deconvolution
description: Map an annotated scRNA-seq reference onto spatial data with Tangram (broadinstitute/Tangram) to get per-spot cell type composition, or a per-cell mapping. A deep-learning alignment method (Python, torch), driven by the coding agent. Use when the user names Tangram, wants scRNA-seq-to-spatial label transfer / mapping, or an alternative to cell2location/CARD for deconvolution.
applies_to: [coding_agent]
tags: [deconvolution, spatial, tangram, mapping]
status: enable
---

# Cell Type Deconvolution / Mapping — Tangram (Python)

## When to use

Tangram ([broadinstitute/Tangram](https://github.com/broadinstitute/Tangram))
learns a probabilistic **cell → spot** mapping by aligning an annotated
scRNA-seq reference to spatial data on a set of shared training genes, then uses
that mapping to (a) transfer cell-type labels / proportions to spots and
(b) impute genes not measured spatially.

- Use when the user **names Tangram**, wants scRNA-seq→spatial **mapping / label
  transfer**, or an alternative to the built-in cell2location tool or CARD.
- Works for **spot-based** platforms (Visium, Slide-seq, ST) to get per-spot
  cell-type composition (`mode="clusters"`), and can also produce a per-cell
  mapping (`mode="cells"`) or a segmentation-aware fit (`mode="constrained"`).
- For the codebase's default, tool-backed deconvolution (Bayesian, uncertainty),
  prefer [[cell2location-deconvolution]] (cell2location). For the R/CAR-prior
  alternative, see [[card-deconvolution]]. For single-cell-resolution platforms
  needing a per-cell label, see [[cell-type-annotation]].
- Tangram is a **coding-agent** task run via the `python` tool — pure Python
  (torch), no dedicated Tangram tool in this codebase.

## Prerequisites

- Install once per kernel session: `pip install tangram-sc`, then
  `import tangram as tg`. Runs on the **Python kernel** (no R/Docker needed,
  unlike [[card-deconvolution]]).
- **GPU strongly recommended** (`device="cuda:0"`); CPU works but is slow,
  especially `mode="cells"`/`"constrained"` with many cells/epochs.

## Input

- **Reference scRNA-seq** `.h5ad` (`adata_sc`) — cells × genes, with a `.obs`
  cell-type column (e.g. `cell_type`/`cell_subclass`). Raw or normalized both
  work, but be **consistent** with the spatial data's preprocessing.
- **Spatial** `.h5ad` (`adata_sp`) — spots × genes (Visium etc.), with spatial
  coords in `.obsm["spatial"]`.
- **Training genes** — a marker set shared by both, typically the top DE genes
  per cell type from `sc.tl.rank_genes_groups` on the reference. `tg.pp_adatas`
  intersects them with the spatial panel.
- Matching gene identifiers between the two (both symbols or both Ensembl).

## Output

- `ad_map` — the returned **cells × spots** (or clusters × spots) mapping AnnData
  (probability of mapping each reference cell/cluster to each spot);
  training-gene diagnostics in `ad_map.uns`.
- `adata_sp.obsm["tangram_ct_pred"]` — **per-spot cell-type scores/proportions**
  after `tg.project_cell_annotations`. Export to
  `outputs/tables/tangram_ct_pred.csv`.
- `ad_ge` — spatial **imputed gene expression** from `tg.project_genes` (optional).
- Figures: per-cell-type spatial maps and training-score diagnostics.

## Success Criteria

- `ad_map` is returned with the expected orientation (cells|clusters × spots).
- `adata_sp.obsm["tangram_ct_pred"]` exists, is spots × cell types, non-empty,
  and its columns are the reference's cell types.
- **Training quality:** `tg.plot_training_scores` shows reasonable per-gene
  scores; a flat/low score means poor alignment — revisit training genes.
- **Sanity check:** a known marker's spatial pattern tracks the predicted
  abundance of the cell type that expresses it.
- **Honest-failure:** if genes don't overlap or the reference lacks the annotation
  column, say so and name the blocker; don't silently switch methods.

## Workflow

0. **Install + import** (once per kernel session):
   ```python
   # pip install tangram-sc   (run via the shell/first cell if not present)
   import scanpy as sc, tangram as tg
   ```
1. **Load** `adata_sc` (reference) and `adata_sp` (spatial); confirm the
   reference cell-type column and that `adata_sp.obsm["spatial"]` exists.
2. **Pick training genes** — `sc.tl.rank_genes_groups(adata_sc, groupby="<ct_col>")`,
   take the top-N markers per cell type, dedupe.
3. **Preprocess** — `tg.pp_adatas(adata_sc, adata_sp, genes=markers)` (aligns and
   intersects genes; stores the shared set in `.uns`).
4. **Map** — `tg.map_cells_to_space(...)`:
   - **Deconvolution / composition (recommended for Visium):** `mode="clusters"`
     with `cluster_label="<ct_col>"` — averages the reference by cell type
     (faster, robust). `density_prior="rna_count_based"`.
   - **Per-cell mapping:** `mode="cells"` (slower; needs GPU).
   - **Segmentation-aware:** `mode="constrained"` with `target_count` = number of
     segmented cells and a segmentation-derived `density_prior` array — use only
     when you have per-spot cell counts from image segmentation (squidpy).
5. **Project labels to spots** — `tg.project_cell_annotations(ad_map, adata_sp,
   annotation="<ct_col>")` → `adata_sp.obsm["tangram_ct_pred"]`; export to CSV.
6. *(Optional)* **impute genes** — `ad_ge = tg.project_genes(ad_map, adata_sc)`.
7. **Visualize + verify** — `tg.plot_cell_annotation_sc`, `tg.plot_training_scores`;
   check Success Criteria; summarize the proportion table and paths.

## Code Template

**Step 0 — install + load inputs**

```python
import scanpy as sc, tangram as tg

adata_sc = sc.read_h5ad("uploads/reference.h5ad")     # cells x genes, .obs[ct_col]
adata_sp = sc.read_h5ad("uploads/spatial.h5ad")       # spots x genes, .obsm["spatial"]
ct_col = "cell_type"
```

**Step 1 — pick training genes (top DE markers per cell type)**

```python
sc.tl.rank_genes_groups(adata_sc, groupby=ct_col, use_raw=False)
markers = list(set(
    sc.get.rank_genes_groups_df(adata_sc, group=None)
      .groupby("group").head(100)["names"]
))
```

**Step 2 — preprocess: align + intersect onto shared genes**

```python
tg.pp_adatas(adata_sc, adata_sp, genes=markers)
```

**Step 3 — map (cluster mode for per-spot composition on Visium)**

```python
device = "cuda:0"   # fall back to "cpu" if no GPU
ad_map = tg.map_cells_to_space(
    adata_sc, adata_sp,
    mode="clusters",
    cluster_label=ct_col,
    density_prior="rna_count_based",
    num_epochs=1000,
    device=device,
)
```

**Step 4 — project per-spot cell-type predictions and export**

```python
import pandas as pd

tg.project_cell_annotations(ad_map, adata_sp, annotation=ct_col)
pred = pd.DataFrame(
    adata_sp.obsm["tangram_ct_pred"],
    index=adata_sp.obs_names,
)
pred.to_csv("outputs/tables/tangram_ct_pred.csv")
```

**Step 5 (optional) — impute genes onto space**

```python
ad_ge = tg.project_genes(ad_map, adata_sc)
```

## Common Issues

- **Too few shared training genes.** Markers must exist in the spatial panel;
  Visium is whole-transcriptome but targeted panels (MERFISH/Xenium) are small —
  pick markers from the panel. Gene-ID mismatch (symbols vs Ensembl) also kills
  overlap; reconcile first.
- **`cells` mode on CPU is very slow.** Prefer `mode="clusters"` for composition;
  use a GPU for `cells`/`constrained`.
- **Wrong `cluster_label`.** Must be the reference's real annotation column;
  wrong column yields meaningless mappings.
- **Preprocessing mismatch.** Keep normalization consistent between reference and
  spatial before `pp_adatas`.
- **`constrained` mode without segmentation.** It needs per-spot cell counts
  (`target_count` + density array from image segmentation); don't use it without
  that input — use `clusters` instead.
- **Reading results:** per-spot composition is `adata_sp.obsm["tangram_ct_pred"]`
  (spots × cell types), NOT `ad_map` (which is the cell/cluster × spot mapping).

## References

- External: Tangram (Biancalani et al., *Nat Methods* 2021),
  repo [broadinstitute/Tangram](https://github.com/broadinstitute/Tangram),
  squidpy tutorial
  (`tutorial_tangram_with_squidpy.ipynb`), docs https://tangram-sc.readthedocs.io/.
- Driven by the coding agent (`coding_agent`) `python` tool; no dedicated Tangram
  tool in this codebase.
- Related skills: [[cell2location-deconvolution]] (cell2location, tool-backed Python
  default) and [[card-deconvolution]] (CARD, R) — same problem, different
  methods; [[cell-type-annotation]] for single-cell-resolution platforms.
