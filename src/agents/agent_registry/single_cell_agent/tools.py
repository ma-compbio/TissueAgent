from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.single_cell_agent.tools_impl.retrieve_cellxgene_single_cell_tool import retrieve_cellxgene_single_cell
from agents.agent_registry.single_cell_agent.tools_impl.query_cellxgene_single_cell_tool import run_query_cellxgene_census_live
from agents.agent_registry.single_cell_agent.tools_impl.cell2location_visium_deconvolution_tool import (
    run_cell2location_visium_deconvolution,
)

SingleCellTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=run_query_cellxgene_census_live,
        name="query_cellxgene_census_live_tool",
        description=(
            "Live-filters CELLxGENE Census single-cell datasets by species, tissues, diseases, etc."
            "Accepts strings or lists for filters. Uses the latest Census by default."
        ),
    ),
    StructuredTool.from_function(
        func=retrieve_cellxgene_single_cell,
        name="retrieve_cellxgene_single_cell_tool",
        description="Downloads a dataset (indexed by dataset_id) from CELLxGENE for downstream analysis"
    ),
    StructuredTool.from_function(
        func=run_cell2location_visium_deconvolution,
        name="cell2location_visium_deconvolution_tool",
        description=(
            "Runs cell2location on spot-level spatial transcriptomics data (such as Visium) using a scRNA-seq reference "
            "to estimate cell type abundances per spot and saves deconvolution outputs to disk."
        ),
    ),
]