from typing import Dict, List, Optional

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from agents.agent_registry.spot_agent.tools_impl.cell2location_visium_deconvolution_tool import (
    run_cell2location_visium_deconvolution,
)

class Cell2LocationArgs(BaseModel):
    visium_h5ad_path: str = Field(..., description="Path to the Visium spatial transcriptomics AnnData file")
    reference_h5ad_path: str = Field(..., description="Path to the reference scRNA-seq AnnData file")
    output_subdir: str = Field(default="cell2location_results", description="Subdirectory for outputs")
    cell_type_column: str = Field(default="leiden", description="Column in reference AnnData containing cell type labels")
    reference_batch_key: Optional[str] = None
    reference_count_layer: Optional[str] = None
    visium_batch_key: Optional[str] = None
    visium_count_layer: Optional[str] = None
    n_cells_per_location: float = 30.0
    detection_alpha: float = 20.0
    regression_max_epochs: int = 50
    spatial_max_epochs: int = 300
    posterior_samples: int = 1000
    posterior_batch_size: int = 2048
    use_gpu: Optional[bool] = None

SpotTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=run_cell2location_visium_deconvolution,
        name="cell2location_visium_deconvolution_tool",
        description=(
            "Runs cell2location to deconvolve spatial (e.g., 10x Visium) transcriptomics spots using a scRNA-seq reference. "
            "Produces fitted model directories, annotated AnnData files, and per-spot cell type abundance tables."
        ),
        args_schema=Cell2LocationArgs,
    ),
]
