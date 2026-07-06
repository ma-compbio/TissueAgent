---
name: cell2location-deconvolution
description: Estimate per-spot cell type composition on spot-based spatial data (10x Visium, Slide-seq, ST) by mapping a scRNA-seq reference with cell2location. Use when the user asks to deconvolve spots, infer cell type proportions/abundances, or "annotate cell types" on multi-cell spatial spots.
applies_to: [spot_agent, single_cell_agent, coding_agent]
status: enable
---

# Cell Type Deconvolution (cell2location)

## When to use

The platform is **spot-based** — each capture location holds many cells (10x Visium, Slide-seq, ST). A single label per spot is wrong; you want **cell type abundances/proportions per spot**, learned by mapping an annotated scRNA-seq reference onto the spatial data.

- Use this skill when the user says "deconvolve", "deconvolution", "cell type composition/proportions/abundance per spot", or asks to "annotate cell types" on Visium/spot data.
- **Do not** use it for single-cell-resolution platforms (MERFISH, Xenium, CosMx, seqFISH) — those get a label per cell via the annotation/transfer path, not deconvolution. See [[cell-type-annotation]].

This codebase implements deconvolution with **cell2location only** (Bayesian mapping with uncertainty). There is no DestVI/Stereoscope/gimVI tool here — do not promise those methods.

## Input

- **Spatial h5ad** *(required)* — Visium etc. with **raw integer counts** in `.X` (or in `.raw`, picked up automatically; or name a counts layer via `visium_count_layer`). Relative paths resolve under `DATA_DIR`.
- **Reference scRNA-seq h5ad** *(required)* — **raw integer counts** and a `.obs` column of cell type labels. No reference on hand? See the retrieval sub-path in **Workflow** (step 0).
- **≥50 shared genes** between the two after filtering — a precondition the tool enforces (it aborts below this).
- Counts must be **unnormalized**; log/normalized matrices are rejected (the tool samples `.X` for non-integer / negative / suspiciously-small-max values and errors out).
- GPU strongly recommended; the tool falls back to CPU (much slower).

**Tool arguments** — `cell2location_visium_deconvolution_tool` (agent: `spot_agent`; also available to `single_cell_agent`):

- `visium_h5ad_path` *(required)* / `reference_h5ad_path` *(required)*.
- `cell_type_column` — `.obs` column with reference labels. **Default is `leiden`** — almost always wrong; pass the real annotation column (e.g. `CellType`, `celltype_mapped_refined`, or `cell_type` for a CELLxGENE reference). The tool errors if absent.
- `output_subdir` — defaults to `cell2location_results/` under the active project's `outputs/`.
- `reference_batch_key` / `visium_batch_key` — optional batch columns for multi-sample data.
- `reference_count_layer` / `visium_count_layer` — name a counts layer instead of `.X`/`.raw`.
- `n_cells_per_location` (default `30`) — expected cells per spot; tune to tissue (~8 brain, ~20 most, ~30 lymph node).
- `detection_alpha` (default `20`) — lower (`20`) for high batch/technical variation; `200` for clean single-batch data.
- `regression_max_epochs` (default `50`), `spatial_max_epochs` (default `300`) — **reduced for speed** vs. the tutorial (250 / 3000); raise for a production-quality fit.
- `posterior_samples` (default `1000`), `posterior_batch_size` (default `2048`), `use_gpu` (auto-detect).

## Output

Written to `<output_subdir>/` under the project's `outputs/`. The tool returns a dict with `status` and:

- `q05_cell_abundance_w_sf.csv` — **5% quantile** abundance per spot × cell type (conservative/confident estimate; prefer this for downstream calls).
- `means_cell_abundance_w_sf.csv` — posterior mean abundance per spot × cell type.
- `visium_with_cell2location.h5ad` — spatial AnnData with abundances in `.obsm`.
- `reference_with_posteriors.h5ad` — reference with exported posteriors.
- `reference_regression_model/`, `spatial_model/` — saved model dirs for reuse/plotting.

## Success Criteria

- `q05_cell_abundance_w_sf.csv` and `visium_with_cell2location.h5ad` exist and are non-empty.
- Returned `status` is `"success"`; the abundance matrix is spots × cell types with the reference's cell types as columns.
- **Sanity check:** abundances per spot track tissue structure — compare a known marker's spatial pattern against the inferred abundance of the cell type that expresses it.
- **Failure signal:** the tool returns `{"status": "error", "message": ...}` instead of raising — read the message; it names the exact problem (missing column, non-raw counts, too few shared genes).

## Workflow

0. **(Only if no reference is supplied) retrieve one from CELLxGENE** — agent `single_cell_agent`, two tools:
   1. `query_cellxgene_census_live_tool` — filter the CZI Census to match the spatial sample (`species`, `tissue_general`/`tissue`, optional `disease`/`development_stage`/`assay`). Set `include_cell_type_counts=True` so each candidate's top cell types are returned; pick a reference covering the expected cell types, matching species/tissue, with large `n_cells`. Returns JSON, one record per `dataset_id`, with metadata/links.
   2. `retrieve_cellxgene_single_cell_tool` — download the chosen `dataset_id` + a `filename`. Saves to `projects/<id>/outputs/datasets/<filename>` and returns that path (won't overwrite). **Its labels are in `cell_type`, but this tool defaults `cell_type_column` to `leiden` — you MUST set `cell_type_column="cell_type"`** for a Census reference.
   *In a plan this is two agents: `single_cell_agent` produces the reference, then `single_cell_agent`/`spot_agent` runs cell2location.*
1. **Validate inputs** — paths resolve, reference `cell_type_column` exists, counts are raw; set `n_cells_per_location` for the tissue.
2. **Run** `cell2location_visium_deconvolution_tool` with `visium_h5ad_path` + `reference_h5ad_path`. Internally it: recovers raw counts (promotes `.raw` if needed) → validates counts are integers (**aborts otherwise**) → **stratified-subsamples references >100k cells to ~10k** → standardizes gene IDs to Ensembl → QC-filters + removes MT- genes → intersects to shared genes (**aborts if <50**) → trains the reference `RegressionModel` (cell-state signatures) → trains the spatial `Cell2location` model → exports per-spot abundance.
3. **Verify** against the Success Criteria.
4. **Summarize** the abundance tables and output paths.

## Code Template

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

## Common Issues

- **Wrong label column → meaningless cell states.** `cell_type_column` defaults to `leiden`; always override with the reference's real annotation column (`cell_type` for a Census reference).
- **Counts, not norms → aborts.** If `.X` is log/normalized and there's no raw layer or `.raw`, the run aborts. Point `*_count_layer` at the right layer.
- **Gene-ID mismatch → shared genes <50 → aborts.** Symbols in one dataset, Ensembl in the other. Reconcile identifiers first.
- **Speed vs. quality.** Default epochs are low for fast iteration; for final results raise `regression_max_epochs`/`spatial_max_epochs` and run on GPU.
- **Large references are subsampled.** References >100k cells are stratified-subsampled to ~10k; pre-subset yourself if you need specific cells.

## References

- Internal tool: `cell2location_visium_deconvolution_tool` (`src/agents/agent_registry/spot_agent/tools.py`).
- Implementation: `spot_agent/tools_impl/cell2location_visium_deconvolution_tool.py`.
- Reference retrieval (agent `single_cell_agent`): `query_cellxgene_census_live_tool` and `retrieve_cellxgene_single_cell_tool` (`src/agents/agent_registry/single_cell_agent/tools.py`).
- Related skill: [[cell-type-annotation]] for single-cell-resolution platforms.
- Alternative methods: [[card-deconvolution]] — CARD (R), a spatially-aware
  (CAR-prior) deconvolution via the coding agent's `r` tool; and
  [[tangram-deconvolution]] — Tangram (Python/torch), scRNA-seq→spatial mapping.
  Consider these when the user names CARD/Tangram or wants an alternative method.
- External: cell2location docs (RegressionModel → Cell2location two-stage mapping); CZI CELLxGENE Census.
