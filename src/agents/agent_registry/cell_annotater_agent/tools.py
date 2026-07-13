from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    harmony_transfer_tool,
    inspect_anndata_preprocessing_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.niche_annotation import (
    niche_annotation_tool,
)

CellAnnotaterTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=inspect_anndata_preprocessing_tool,
        name="inspect_anndata_preprocessing_tool",
        description=(
            "Read-only inspection of spatial and reference AnnData expression matrices before "
            "Harmony transfer. Deterministically samples bounded rows/genes and reports dtype, "
            "integer-like fraction, negative/non-finite values, log1p metadata, and an explicit "
            "raw-count-like versus processed-continuous classification for each input. Returns a "
            "recommended skip_preprocessing boolean only when both inputs have compatible, "
            "high-confidence states. Returns a visible error for ambiguous, invalid, or mixed "
            "states instead of guessing. Call this before every Harmony transfer."
        ),
    ),
    StructuredTool.from_function(
        func=harmony_transfer_tool,
        name="harmony_transfer_tool",
        description=(
            "Transfers cell type annotations from a user-provided reference dataset to spatial transcriptomics data using Harmony integration and MLP classification. "
            "Use only when the user explicitly asks for reference-based cell-type transfer or provides a reference_anndata_path. "
            "Optional gene identifier harmonization standardizes both reference and spatial features into a shared namespace using common AnnData .var columns and MyGene.info when conversion is needed. "
            "Set gene_mapping_species to a MyGene-supported species name/taxid, or use 'auto' to infer common AnnData organism/species metadata. "
            "Set gene_mapping_target to 'symbol' or 'ensembl'. "
            "Requires an explicit skip_preprocessing boolean chosen after calling inspect_anndata_preprocessing_tool on both inputs. "
            "When skip_preprocessing=False, preprocesses working copies of both datasets by filtering cells/genes, normalizing, and log-transforming. "
            "With preserve_all_spatial_obs=True, the saved annotated AnnData preserves all original spatial observations and marks rows excluded from transfer in .obs['harmony_transfer_status'] and .obs['harmony_exclusion_reason']. "
            "Identifies shared genes between reference and spatial datasets, combines them for batch correction using Harmony, "
            "performs PCA on the integrated data, then trains an MLP classifier on reference Harmony-corrected PCA space. "
            "Predicts cell types and confidence scores for spatial cells. "
            "Predictions are stored in .obs['harmony_predicted_cell_type'], .obs['harmony_prediction_confidence'], and .obs['label']. "
            "Saves annotated spatial AnnData (.h5ad); use output_path for an exact .h5ad file path relative to DATA_DIR. "
            "Returns transfer statistics including input/output cell counts, transferred/excluded cell counts, cell type counts, mean prediction confidence, and number of shared genes. "
            "Required parameters: spatial_anndata_path, reference_anndata_path. "
            "Required decision parameter: skip_preprocessing. Optional: output_path, output_dir, output_filename, cell_type_column, preserve_all_spatial_obs, preprocessing parameters (min_genes, min_cells, target_sum, n_top_genes, n_pcs), Harmony iteration limit (harmony_max_iter), "
            "MLP parameters (mlp_hidden_layers, mlp_max_iter, mlp_random_state), map_spatial_gene_names, gene_mapping_species, and gene_mapping_target."
        ),
    ),

    StructuredTool.from_function(
        func=niche_annotation_tool,
        name="niche_annotation_tool",
        description=(
            "Runs an end-to-end tissue niche annotation pipeline on a spatial transcriptomics AnnData object. "
            "First runs UTAG to discover spatial niches, then builds one LLM labeling prompt per niche using available cell-type composition, marker-gene summaries, and spatial centroid summaries. "
            "The tool itself performs the internal LLM labeling step, parses the JSON responses, applies the resulting tissue niche labels and justifications back to the AnnData object, "
            "and saves the UTAG intermediate h5ad, final annotated h5ad, and JSON artifacts containing the generated niche queries and LLM labeling results. "
            "This tool does not use CELLxGENE, external references, Harmony transfer, or single-cell reference acquisition. "
            "Use slide_key='auto' to infer common slide/sample columns or create a single-slide grouping. "
            "If cell-type labels are present in a non-default .obs column, pass celltype_key; use celltype_key='auto' to infer common columns. "
            "If no cell-type column exists, the tool falls back to marker-gene summaries instead of retrieving a reference dataset. "
            "Required parameter: spatial_anndata_path. "
            "Optional parameters include output_dir, slide_key, celltype_key, spatial_key, niche_key, annotation_col, justification_col, "
            "allowed_labels, unmatched_label, top_n_celltypes, top_n_marker_genes, and UTAG configuration values such as utag_max_dist, utag_normalization_mode, "
            "utag_apply_clustering, utag_clustering_method, and utag_resolutions."
        ),
    ),
]
