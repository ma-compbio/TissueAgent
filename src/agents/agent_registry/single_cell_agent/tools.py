"""Tool definitions for the single cell agent."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from agents.agent_registry.single_cell_agent.tools_impl.retrieve_cellxgene_single_cell_tool import (
    retrieve_cellxgene_single_cell,
)
from agents.agent_registry.single_cell_agent.tools_impl.query_cellxgene_single_cell_tool import (
    run_query_cellxgene_census_live,
)

# cell2location Visium deconvolution lives on the spot_agent (spot-resolution
# spatial data). Registering it here too would shadow that registration under
# the same tool name and shipped stale defaults / a dropped `use_gpu=` kwarg.

SingleCellTools: list[StructuredTool] = [
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
        description="Downloads a dataset (indexed by dataset_id) from CELLxGENE for downstream analysis",
    ),
]
