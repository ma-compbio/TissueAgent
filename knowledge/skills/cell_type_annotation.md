---
name: cell-type-annotation
description: Assign a cell type label to every cell in single-cell-resolution spatial data (MERFISH, Xenium, CosMx, seqFISH) by transferring annotations from a labeled scRNA-seq reference via Harmony integration + an MLP classifier. Use when the user asks to annotate / label cell types per cell, or transfer labels from a reference onto spatial cells.
applies_to: [cell_annotator, single_cell, coding]
tags: [annotation, label_transfer, harmony, mlp, cell_type, spatial, reference]
status: enable
---

# Cell Type Annotation (Harmony label transfer)

## When to use

The data has **single-cell resolution** — each observation is one cell (MERFISH, Xenium, CosMx, seqFISH, or any scRNA-seq-like spatial object). You want **one cell type label per cell**, learned by transferring labels from an annotated scRNA-seq reference.

- Use this skill when the user says "annotate cell types", "label transfer", "predict cell types per cell", or "map reference annotations onto my spatial cells".
- **Do not** use it for spot-based platforms (10x Visium, Slide-seq, ST) where each spot is a mixture of cells — those need per-spot **deconvolution**, not a single label. See [[cell-type-deconvolution]].

This codebase implements annotation with one method: **Harmony batch correction + an MLP classifier** trained in the integrated PCA space. There is no marker-based or ontology-LLM annotation tool here — do not promise those.

## Prerequisites

- **Spatial h5ad** with cells in `.obs` and a gene-expression matrix in `.X`.
- **Reference scRNA-seq h5ad** with a `.obs` column holding cell type labels. No reference on hand? Retrieve one from CELLxGENE — see the next section.
- **≥50 shared genes** between the two after preprocessing (the tool aborts below this).
- Gene identifiers must line up between datasets. If the spatial object uses gene **symbols**, the default gene-name mapping converts them (see below).

Inputs may be **raw counts** — by default the tool preprocesses (normalize + log1p + HVG). Pass `skip_preprocessing=True` only when both objects are already normalized/log-transformed the same way.

## No reference? Retrieve one from CELLxGENE first

If the user has spatial data but **no labeled scRNA-seq reference**, do not give up — get one from the CZI **CELLxGENE Census** before annotating. This is the `single_cell` agent's job (two tools). Run it as a prerequisite step, then feed the downloaded path into `harmony_transfer_tool` as `reference_anndata_path`.

1. **Find the best-matching reference** — `query_cellxgene_census_live_tool` (agent: `single_cell`). Filter the Census to match the spatial sample so the reference shares cell types and genes:
   - `species` — `homo_sapiens` or `mus_musculus` (must match the spatial data's organism).
   - `tissue_general` / `tissue` — the tissue of the spatial sample (use ontology labels, e.g. `heart`, `heart left ventricle`).
   - `disease` — e.g. `["normal"]` for a healthy reference; omit if not a constraint.
   - `development_stage`, `sex`, `assay` — optional narrowing (assay defaults to common scRNA-seq platforms).
   - `include_cell_type_counts: True` + `top_k_cell_types` — returns each dataset's top cell types so you can confirm the reference actually contains the cell types you expect to see in the tissue.
   - `enrich_metadata: True` (default) adds dataset titles, DOIs, and explorer URLs; `max_results` (default 20) caps results, sorted by `n_cells`.

   Returns JSON: one record per `dataset_id` with `n_cells`, `n_donors`, tissues, diseases, `cell_type_topK`, and metadata. **Pick the best match** — prioritize matching tissue + species, healthy/relevant disease state, large `n_cells`, and a cell-type set that covers what you expect spatially.

2. **Download the chosen reference** — `retrieve_cellxgene_single_cell_tool` (agent: `single_cell`) with the selected `dataset_id` and a `filename`. It saves to `projects/<id>/outputs/datasets/<filename>` and returns that workspace-relative path. (It refuses to overwrite an existing file — choose a fresh name or reuse the existing one.)

3. **Annotate** — pass the downloaded path as `reference_anndata_path` to `harmony_transfer_tool`. The CELLxGENE reference's cell type labels live in the **`cell_type`** `.obs` column — which is exactly `harmony_transfer_tool`'s default `cell_type_column`, so you usually don't need to override it for a Census reference.

In a multi-step plan this is two agents: recruit `single_cell` for steps 1–2 (produce the reference h5ad), then `cell_annotator` for step 3 (transfer labels). The same Census tools also feed `[[cell-type-deconvolution]]` when the missing reference is for spot-based data.

## The tool

`harmony_transfer_tool` (agent: `cell_annotator`; also usable by `single_cell`). Key arguments:

- `spatial_anndata_path` *(required)* — target spatial data to label. A bare filename is searched across the project's `outputs/`/`uploads/`, `library/datasets/`, `library/files/`, then `DATA_DIR`.
- `reference_anndata_path` *(required)* — labeled scRNA-seq reference.
- `cell_type_column` — `.obs` column with reference labels. **Default is `cell_type`** — override it with the reference's real column (e.g. `CellType`, `celltype_mapped_refined`). The tool errors if the column is absent.
- `output_dir` — defaults to `harmony_transfer_results/` under the active project's `outputs/`.
- `map_spatial_gene_names` (default `True`) — maps spatial `var_names` via the **MyGene.info API** (symbol → Ensembl, human by default). Set `False` when the spatial genes already match the reference, when you're offline, or for a non-human species (the call is hard-coded to `species="human"`).
- `skip_preprocessing` (default `False`) — skip filter/normalize/log/HVG. Use only if both inputs are already processed identically.
- Preprocessing: `min_genes` (50), `min_cells` (10), `target_sum` (1e4), `n_top_genes` (2000), `n_pcs` (30).
- MLP: `mlp_hidden_layers` (`(100, 50)`), `mlp_max_iter` (500), `mlp_random_state` (42).

## What the tool does internally (so you can set inputs correctly)

1. Resolves paths, reads both AnnData files, checks `cell_type_column` exists in the reference.
2. If `map_spatial_gene_names`, maps spatial gene symbols → Ensembl IDs via MyGene.info (failed lookups keep their original name).
3. Unless `skip_preprocessing`: filters cells/genes, `normalize_total`, `log1p`, and selects HVGs on **each** dataset.
4. Intersects to **shared genes** and subsets both (**aborts if <50 shared**).
5. Concatenates reference + spatial into one object tagged by `batch`/`dataset`.
6. Runs `sc.pp.pca` then `sc.external.pp.harmony_integrate` for batch correction (`X_pca_harmony`).
7. Trains an `MLPClassifier` on the **reference** cells in Harmony-PCA space (features standardized).
8. Predicts labels + per-cell **confidence** (max class probability) for the **spatial** cells.

## Outputs

Written to `<output_dir>/` under the project's `outputs/`. The tool returns a dict with `status` and:

- `annotated_object.h5ad` — the spatial AnnData with new `.obs` columns:
  - `harmony_predicted_cell_type` — the transferred label per cell.
  - `harmony_prediction_confidence` — max class probability (use to threshold/flag low-confidence cells).
  - `label` — alias of the predicted cell type.
- `run_meta.json` (under `logs/`) — parameters, inputs/outputs, and a summary block.
- Returned stats: `n_cells_transferred`, `n_unique_cell_types`, `cell_type_counts`, `mean_prediction_confidence`, `n_shared_genes`.

On failure the tool returns `{"status": "error", "message": ...}` instead of raising — read the message; it names the exact problem (missing column, too few shared genes, or a runtime error).

## Visualizing / using results (via the coding agent)

```python
import scanpy as sc

adata = sc.read_h5ad("harmony_transfer_results/annotated_object.h5ad")
print(adata.obs["harmony_predicted_cell_type"].value_counts())

# Spatial map of predicted labels + a confidence view
sc.pl.embedding(adata, basis="spatial", color="harmony_predicted_cell_type", save="_celltypes.png")
sc.pl.embedding(adata, basis="spatial", color="harmony_prediction_confidence", save="_confidence.png")

# Flag low-confidence calls for review
low = adata.obs["harmony_prediction_confidence"] < 0.5
print(f"{low.sum()} cells below 0.5 confidence")
```

## Pitfalls

- **`cell_type_column` default is `cell_type`.** Override it with the reference's real annotation column or the run aborts (or, worse, trains on the wrong field).
- **Gene-ID mismatch** is the most common failure: if the spatial panel uses symbols and the reference uses Ensembl (or vice versa) and mapping is off/incomplete, the shared-gene set drops below 50 and the tool aborts. Keep `map_spatial_gene_names=True` for human symbol panels; reconcile manually otherwise.
- **Non-human species:** the MyGene mapping is hard-coded to `species="human"`. For mouse/other, set `map_spatial_gene_names=False` and pre-align identifiers yourself.
- **`skip_preprocessing` mismatch:** skipping when inputs aren't already normalized the same way yields a bad PCA/Harmony space and garbage labels.
- **Trust the confidence:** transferred labels for cell types absent from (or rare in) the reference will still be forced into a known class — inspect `harmony_prediction_confidence` and treat low-confidence regions skeptically.
- **One call per dataset pair** — the model is deterministic given `mlp_random_state`; re-running with identical args won't change the result.

## References

- Internal tool: `harmony_transfer_tool` (`src/agents/agent_registry/cell_annotater_agent/tools.py`).
- Implementation: `cell_annotater_agent/tools_impl/harmony_transfer.py` (Harmony integration + `MLPClassifier`; MyGene.info gene mapping).
- Reference retrieval (agent `single_cell`): `query_cellxgene_census_live_tool` and `retrieve_cellxgene_single_cell_tool` (`src/agents/agent_registry/single_cell_agent/tools.py`).
- Related: [[cell-type-deconvolution]] for spot-based platforms.
- External: scanpy `sc.external.pp.harmony_integrate`; MyGene.info querymany; CZI CELLxGENE Census.
