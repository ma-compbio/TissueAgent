---
name: cell-type-annotation
description: Assign a cell type label to every cell in single-cell-resolution spatial data (MERFISH, Xenium, CosMx, seqFISH) by transferring annotations from a labeled scRNA-seq reference via Harmony integration + an MLP classifier. Use when the user asks to annotate / label cell types per cell, or transfer labels from a reference onto spatial cells.
applies_to: [cell_annotator, single_cell, coding]
status: enable
---

# Cell Type Annotation (Harmony label transfer)

## When to use

The data has **single-cell resolution** — each observation is one cell (MERFISH, Xenium, CosMx, seqFISH, or any scRNA-seq-like spatial object). You want **one cell type label per cell**, learned by transferring labels from an annotated scRNA-seq reference.

- Use this skill when the user says "annotate cell types", "label transfer", "predict cell types per cell", or "map reference annotations onto my spatial cells".
- **Do not** use it for spot-based platforms (10x Visium, Slide-seq, ST) where each spot is a mixture of cells — those need per-spot **deconvolution**, not a single label. See [[cell-type-deconvolution]].

This codebase implements annotation with one method: **Harmony batch correction + an MLP classifier** trained in the integrated PCA space. There is no marker-based or ontology-LLM annotation tool here — do not promise those.

## Input

- **Spatial h5ad** *(required)* — cells in `.obs`, a gene-expression matrix in `.X`. A bare filename is searched across the project's `outputs/`/`uploads/`, `library/datasets/`, `library/files/`, then `DATA_DIR`.
- **Reference scRNA-seq h5ad** *(required)* — a `.obs` column holding cell type labels. No reference on hand? See the retrieval sub-path in **Workflow** (step 0).
- **≥50 shared genes** between the two after preprocessing — a precondition the tool enforces (it aborts below this).
- Gene identifiers must line up between datasets. If the spatial object uses gene **symbols**, the default MyGene.info mapping converts them to Ensembl.

Inputs may be **raw counts** — by default the tool preprocesses (normalize + log1p + HVG). Use `skip_preprocessing=True` only when both objects are already normalized/log-transformed the same way.

**Tool arguments** — `harmony_transfer_tool` (agent: `cell_annotator`; also usable by `single_cell`):

- `spatial_anndata_path` *(required)* / `reference_anndata_path` *(required)*.
- `cell_type_column` — `.obs` column with reference labels. **Default is `cell_type`** — override with the reference's real column (e.g. `CellType`, `celltype_mapped_refined`) unless it's a CELLxGENE reference (which uses `cell_type`). The tool errors if the column is absent.
- `output_dir` — defaults to `harmony_transfer_results/` under the active project's `outputs/`.
- `map_spatial_gene_names` (default `True`) — maps spatial `var_names` via the **MyGene.info API** (symbol → Ensembl, human only). Set `False` when genes already match, when offline, or for a non-human species.
- `skip_preprocessing` (default `False`) — skip filter/normalize/log/HVG.
- Preprocessing: `min_genes` (50), `min_cells` (10), `target_sum` (1e4), `n_top_genes` (2000), `n_pcs` (30). MLP: `mlp_hidden_layers` (`(100, 50)`), `mlp_max_iter` (500), `mlp_random_state` (42).

## Output

Written to `<output_dir>/` under the project's `outputs/`. The tool returns a dict with `status` and:

- `annotated_object.h5ad` — the spatial AnnData with new `.obs` columns:
  - `harmony_predicted_cell_type` — the transferred label per cell.
  - `harmony_prediction_confidence` — max class probability (use to threshold/flag low-confidence cells).
  - `label` — alias of the predicted cell type.
- `run_meta.json` (under `logs/`) — parameters, inputs/outputs, and a summary block.
- Returned stats: `n_cells_transferred`, `n_unique_cell_types`, `cell_type_counts`, `mean_prediction_confidence`, `n_shared_genes`.

## Success Criteria

- `annotated_object.h5ad` exists and carries the three new `.obs` columns above.
- The returned `status` is `"success"`; `n_shared_genes >= 50` and `n_unique_cell_types` is plausible for the tissue.
- `mean_prediction_confidence` is reasonable and low-confidence regions are flagged for review, not blindly trusted.
- **Failure signal:** the tool returns `{"status": "error", "message": ...}` instead of raising — read the message; it names the exact problem (missing column, too few shared genes, runtime error).

## Workflow

0. **(Only if no reference is supplied) retrieve one from CELLxGENE** — agent `single_cell`, two tools:
   1. `query_cellxgene_census_live_tool` — filter the CZI Census to match the spatial sample: `species` (`homo_sapiens`/`mus_musculus`, must match organism), `tissue_general`/`tissue` (ontology labels, e.g. `heart left ventricle`), optional `disease` (`["normal"]` for healthy), `development_stage`/`sex`/`assay`. Set `include_cell_type_counts=True` (+ `top_k_cell_types`) to confirm the reference contains the expected cell types. Returns JSON, one record per `dataset_id` (`n_cells`, tissues, `cell_type_topK`, titles/links). **Pick the best match**: matching tissue + species, relevant disease state, large `n_cells`, covering cell types.
   2. `retrieve_cellxgene_single_cell_tool` — download the chosen `dataset_id` + a `filename`. Saves to `projects/<id>/outputs/datasets/<filename>` and returns that path (won't overwrite). Its labels are in the `cell_type` column — the tool default, so no `cell_type_column` override needed.
   *In a plan this is two agents: `single_cell` produces the reference, then `cell_annotator` transfers labels.*
1. **Validate inputs** — paths resolve, reference `cell_type_column` exists; decide `map_spatial_gene_names` and `skip_preprocessing` from the data.
2. **Run** `harmony_transfer_tool` with `spatial_anndata_path` + `reference_anndata_path`. Internally it: maps gene names (if enabled) → preprocesses each dataset (unless skipped) → intersects to shared genes (**aborts if <50**) → concatenates → `sc.pp.pca` → `sc.external.pp.harmony_integrate` → trains an `MLPClassifier` on the reference in Harmony-PCA space → predicts labels + confidence for the spatial cells.
3. **Verify** against the Success Criteria; inspect confidence.
4. **Summarize** cell-type counts, mean confidence, shared-gene count, and the output path.

## Code Template

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

## Common Issues

- **Wrong label column → aborts or trains on the wrong field.** `cell_type_column` defaults to `cell_type`; override it with the reference's real annotation column (Census references already use `cell_type`).
- **Gene-ID mismatch → shared genes <50 → aborts.** Most common failure: spatial uses symbols, reference uses Ensembl (or vice versa) and mapping is off/incomplete. Keep `map_spatial_gene_names=True` for human symbol panels; reconcile manually otherwise.
- **Non-human species → bad mapping.** MyGene mapping is hard-coded to `species="human"`. For mouse/other, set `map_spatial_gene_names=False` and pre-align identifiers yourself.
- **`skip_preprocessing` mismatch → garbage labels.** Skipping when inputs aren't already normalized identically yields a bad PCA/Harmony space.
- **Over-trusting confidence.** Cell types absent/rare in the reference are still forced into a known class — treat low-`harmony_prediction_confidence` regions skeptically.
- **Determinism.** Given `mlp_random_state`, re-running with identical args won't change the result.

## References

- Internal tool: `harmony_transfer_tool` (`src/agents/agent_registry/cell_annotater_agent/tools.py`).
- Implementation: `cell_annotater_agent/tools_impl/harmony_transfer.py` (Harmony integration + `MLPClassifier`; MyGene.info gene mapping).
- Reference retrieval (agent `single_cell`): `query_cellxgene_census_live_tool` and `retrieve_cellxgene_single_cell_tool` (`src/agents/agent_registry/single_cell_agent/tools.py`).
- Related skill: [[cell-type-deconvolution]] for spot-based platforms.
- External: scanpy `sc.external.pp.harmony_integrate`; MyGene.info querymany; CZI CELLxGENE Census.
