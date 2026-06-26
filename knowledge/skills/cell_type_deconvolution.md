---
name: cell-type-deconvolution
description: Estimate per-spot cell type composition on spot-based spatial data (10x Visium, Slide-seq, ST) by mapping a scRNA-seq reference with cell2location. Use when the user asks to deconvolve spots, infer cell type proportions/abundances, or "annotate cell types" on multi-cell spatial spots.
applies_to: [spot, single_cell, coding]
tags: [deconvolution, cell2location, visium, spatial, cell_type, abundance]
status: enable
---

# Cell Type Deconvolution (cell2location)

## When to use

The platform is **spot-based** — each capture location holds many cells (10x Visium, Slide-seq, ST). A single label per spot is wrong; you want **cell type abundances/proportions per spot**, learned by mapping an annotated scRNA-seq reference onto the spatial data.

- Use this skill when the user says "deconvolve", "deconvolution", "cell type composition/proportions/abundance per spot", or asks to "annotate cell types" on Visium/spot data.
- **Do not** use it for single-cell-resolution platforms (MERFISH, Xenium, CosMx, seqFISH) — those get a label per cell via the annotation/transfer path, not deconvolution.

This codebase implements deconvolution with **cell2location only** (Bayesian mapping with uncertainty). There is no DestVI/Stereoscope/gimVI tool here — do not promise those methods.

## Prerequisites

- **Spatial h5ad** (Visium etc.) with **raw integer counts** in `.X` (or in `.raw`, which is picked up automatically; or pass a counts layer via `visium_count_layer`).
- **Reference scRNA-seq h5ad** with **raw integer counts** and a `.obs` column of cell type labels. No reference on hand? Retrieve one from CELLxGENE — see the next section.
- **≥50 shared genes** between the two after filtering (the tool aborts below this).
- GPU strongly recommended; the tool falls back to CPU (much slower).

Counts must be unnormalized. Log/normalized matrices are rejected — the tool inspects a sample of `.X` for non-integer / negative / suspiciously-small-max values and errors out with guidance.

## No reference? Retrieve one from CELLxGENE first

If the user has spot-based spatial data but **no scRNA-seq reference**, retrieve a matched one from the CZI **CELLxGENE Census** before deconvolving. This is the `single_cell` agent's job (two tools); run it as a prerequisite step, then feed the downloaded path into `cell2location_visium_deconvolution_tool` as `reference_h5ad_path`.

1. **Find the best-matching reference** — `query_cellxgene_census_live_tool` (agent: `single_cell`). Filter the Census to match the spatial sample (`species`, `tissue_general`/`tissue`, optional `disease`/`development_stage`/`assay`). Set `include_cell_type_counts: True` so each candidate's top cell types are returned — pick a reference whose cell types cover what you expect in the tissue, with matching species/tissue and large `n_cells`. Returns JSON, one record per `dataset_id`, with metadata and links (`enrich_metadata` default on).
2. **Download the chosen reference** — `retrieve_cellxgene_single_cell_tool` (agent: `single_cell`) with the selected `dataset_id` + a `filename`. Saves to `projects/<id>/outputs/datasets/<filename>` and returns that workspace-relative path (won't overwrite an existing file).
3. **Deconvolve** — pass the downloaded path as `reference_h5ad_path`. **Important:** a CELLxGENE reference stores its labels in the **`cell_type`** `.obs` column, but this tool's `cell_type_column` defaults to `leiden` — you **must** set `cell_type_column="cell_type"` for a Census reference, or the run aborts / trains on the wrong field.

In a multi-step plan this is two agents: recruit `single_cell` for steps 1–2 (produce the reference h5ad), then `single_cell`/`spot` for the cell2location step. See [[cell-type-annotation]] for the single-cell-resolution counterpart.

## The tool

`cell2location_visium_deconvolution_tool` (agent: `spot`; also available to `single_cell`). Key arguments:

- `visium_h5ad_path` *(required)* — spatial counts. Relative paths resolve under the workspace `DATA_DIR`.
- `reference_h5ad_path` *(required)* — annotated scRNA-seq reference.
- `cell_type_column` — `.obs` column with reference labels. **Default is `leiden`** — almost always wrong; pass the real annotation column (e.g. `CellType`, `celltype_mapped_refined`). The tool errors if the column is absent.
- `output_subdir` — defaults to `cell2location_results/`, created under the active project's `outputs/`.
- `reference_batch_key` / `visium_batch_key` — optional batch columns for multi-sample data.
- `reference_count_layer` / `visium_count_layer` — name a counts layer instead of using `.X`/`.raw`.
- `n_cells_per_location` (default `30`) — expected cells per spot; tune to tissue (~8 brain, ~20 most tissues, ~30 lymph node).
- `detection_alpha` (default `20`) — use the lower value (`20`) when batch/technical variation is high; `200` for clean single-batch data.
- `regression_max_epochs` (default `50`), `spatial_max_epochs` (default `300`) — these are **reduced for speed** vs. the cell2location tutorial (250 / 3000). Raise them for a production-quality fit if results look under-trained.
- `posterior_samples` (default `1000`), `posterior_batch_size` (default `2048`), `use_gpu` (default: auto-detect).

## What the tool does internally (so you can set inputs correctly)

1. Resolves paths, reads both AnnData files, checks `cell_type_column` exists.
2. Recovers raw counts: if no count layer is given and `.raw` exists, it promotes `.raw` to `.X` for both objects.
3. Validates counts are raw integers; aborts otherwise.
4. **Subsamples large references**: if the reference has >100k cells, it does **stratified sampling down to ~10k** cells to keep cell type proportions. If you need all cells, pre-subset yourself and keep it under 100k.
5. **Standardizes gene IDs to Ensembl** (`ENSG…`) when an Ensembl column exists in `.var`; preserves symbols in `var['gene_symbol']`. Make sure both datasets carry compatible gene identifiers.
6. Optional gene QC filter (`min_cells_ref`/`min_cells_vis`/`min_counts`, all default 10), **removes MT- genes** from the spatial data, then intersects to shared genes (**aborts if <50**).
7. Trains the reference **RegressionModel** → exports posterior → extracts the cell-state signature matrix.
8. Trains the spatial **Cell2location** model on the shared genes → exports posterior → writes per-spot abundance.

## Outputs

Written to `<output_subdir>/` under the project's `outputs/`. The tool returns a dict with `status` and these paths:

- `q05_cell_abundance_w_sf.csv` — **5% quantile** abundance per spot × cell type (conservative/confident estimate; prefer this for downstream calls).
- `means_cell_abundance_w_sf.csv` — posterior mean abundance per spot × cell type.
- `visium_with_cell2location.h5ad` — spatial AnnData with abundances in `.obsm`.
- `reference_with_posteriors.h5ad` — reference with exported posteriors.
- `reference_regression_model/`, `spatial_model/` — saved model dirs for reuse/plotting.

On failure the tool returns `{"status": "error", "message": ...}` instead of raising — read the message; it names the exact problem (missing column, non-raw counts, too few shared genes).

## Visualizing results (via the coding agent)

```python
import scanpy as sc, pandas as pd, matplotlib.pyplot as plt

adata = sc.read_h5ad("cell2location_results/visium_with_cell2location.h5ad")
ab = pd.read_csv("cell2location_results/q05_cell_abundance_w_sf.csv", index_col=0)

fig, axes = plt.subplots(2, 3, figsize=(15, 10))
for ax, ct in zip(axes.flat, ab.columns[:6]):
    adata.obs[ct] = ab[ct].values
    sc.pl.spatial(adata, color=ct, ax=ax, show=False, title=ct)
plt.tight_layout(); plt.savefig("celltype_abundance.png", dpi=150)
```

## Pitfalls

- **`cell_type_column` default is `leiden`.** Always override it with the reference's real annotation column — silent wrong-column use yields meaningless cell states.
- **Counts, not norms.** If `.X` is log/normalized and there's no raw layer or `.raw`, the run aborts. Point `*_count_layer` at the right layer.
- **Gene-ID mismatch** (symbols in one dataset, Ensembl in the other) collapses the shared-gene set below 50 and aborts. Reconcile identifiers first.
- **Speed vs. quality.** Default epochs are low for fast iteration. For final results, increase `regression_max_epochs` / `spatial_max_epochs` and run on GPU.
- **Sanity-check the output:** abundances per spot should track tissue structure; compare a known marker's spatial pattern against the inferred abundance of the cell type that expresses it.

## References

- Internal tool: `cell2location_visium_deconvolution_tool` (`src/agents/agent_registry/spot_agent/tools.py`).
- Implementation: `spot_agent/tools_impl/cell2location_visium_deconvolution_tool.py`.
- Reference retrieval (agent `single_cell`): `query_cellxgene_census_live_tool` and `retrieve_cellxgene_single_cell_tool` (`src/agents/agent_registry/single_cell_agent/tools.py`).
- Related: [[cell-type-annotation]] for single-cell-resolution platforms.
- External: cell2location docs (RegressionModel → Cell2location two-stage mapping); CZI CELLxGENE Census.
