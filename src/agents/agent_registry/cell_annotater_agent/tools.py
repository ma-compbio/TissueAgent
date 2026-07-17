"""Tool definitions for the Cell Annotater Agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    harmony_transfer_tool,
    inspect_anndata_preprocessing_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.niche_annotation import (
    niche_annotation_tool,
)

CellAnnotaterTools: list[StructuredTool] = [
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
            "Transfers reference cell-type labels to spatial observations with Harmony and an "
            "MLP classifier. Call inspect_anndata_preprocessing_tool first and pass its exact "
            "boolean as skip_preprocessing. Choose and pass min_shared_genes explicitly for the "
            "assay and panel; the decision is recorded in run metadata. Gene mapping is symmetric "
            "and species-aware. With "
            "preserve_all_spatial_obs=True, the output keeps every query row and records explicit "
            "transfer status and exclusion reason columns. Predictions, confidence, and label are "
            "written to .obs. Relative outputs must be beneath project/outputs; existing outputs "
            "are never overwritten."
        ),
    ),
    StructuredTool.from_function(
        func=niche_annotation_tool,
        name="niche_annotation_tool",
        description=(
            "Runs UTAG tissue-niche discovery and internal LLM labeling on one spatial AnnData. "
            "It uses cell-type composition when available, otherwise marker and spatial summaries. "
            "It writes annotated H5AD and JSON prompt/result artifacts without CELLxGENE, Harmony, "
            "or external reference acquisition."
        ),
    ),
]
