from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.cell_annotater_agent.tools_impl.preprocessing_tool import (
    preprocess_spatial_data_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    harmony_transfer_tool,
)

CellAnnotaterTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=preprocess_spatial_data_tool,
        name="preprocess_spatial_data_tool",
        description=(
            "Automates preprocessing of spatial transcriptomics data using Scanpy. "
            "Filters low-quality cells and genes, normalizes expression values, applies log transformation, "
            "selects highly variable genes, performs PCA, computes neighborhood graphs, and generates UMAP embeddings. "
            "Standardizes gene naming conventions and saves processed dataset in .h5ad format. "
            "Returns preprocessing statistics and output path."
        ),
    ),
    StructuredTool.from_function(
        func=harmony_transfer_tool,
        name="harmony_transfer_tool",
        description=(
            "Transfers cell type annotations from reference datasets to spatial transcriptomics data using Harmony integration and MLP classification. "
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
]
