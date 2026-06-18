from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    harmony_transfer_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.niche_annotation import (
    niche_annotation_tool,
)

CellAnnotaterTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=harmony_transfer_tool,
        name="harmony_transfer_tool",
        description=(
            "Transfers cell type annotations from a user-provided reference dataset to spatial transcriptomics data using Harmony integration and MLP classification. "
            "Use only when the user explicitly asks for reference-based cell-type transfer or provides a reference_anndata_path. "
            "Optional gene name mapping via MyGene.info API standardizes spatial gene identifiers. "
            "Preprocesses both datasets (filters cells/genes, normalizes, log-transforms) unless skip_preprocessing=True. "
            "Identifies shared genes between reference and spatial datasets, combines them for batch correction using Harmony, "
            "performs PCA on the integrated data, then trains an MLP classifier on reference Harmony-corrected PCA space. "
            "Predicts cell types and confidence scores for spatial cells. "
            "Saves transferred labels CSV, annotated spatial AnnData (.h5ad), and reference with Harmony PCA. "
            "Returns transfer statistics including cell type counts, mean prediction confidence, and number of shared genes. "
            "Required parameters: spatial_anndata_path, reference_anndata_path. "
            "Optional: output_dir, cell_type_column, skip_preprocessing, preprocessing parameters (min_genes, min_cells, target_sum, n_top_genes, n_pcs), "
            "MLP parameters (mlp_hidden_layers, mlp_max_iter, mlp_random_state), and map_spatial_gene_names."
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
