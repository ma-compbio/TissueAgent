"""Tool definitions for the single cell agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.single_cell_agent.tools_impl.retrieve_cellxgene_single_cell_tool import (
    retrieve_cellxgene_single_cell,
    retrieve_cellxgene_reference_subset,
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
        func=retrieve_cellxgene_reference_subset,
        name="retrieve_cellxgene_reference_subset_tool",
        description=(
            "Retrieves only a reproducible, label-balanced subset of cells from one or more pinned "
            "CELLxGENE datasets. This is the default retrieval tool for cell-annotation "
            "references, "
            "even when the query dataset is full; use a full source download only when explicitly "
            "required. Automatic source scans above one million cells are rejected so the agent "
            "must select a smaller sufficient atlas. Requires an explicit Census version and "
            "never installs packages."
        ),
    ),
    StructuredTool.from_function(
        func=retrieve_cellxgene_single_cell,
        name="retrieve_cellxgene_single_cell_tool",
        description=(
            "Downloads a dataset (indexed by dataset_id) from CELLxGENE for downstream analysis. "
            "The filename is resolved inside DATA_DIR, a stable or pinned Census version is used, "
            "the download is staged through a partial file, and only a valid H5AD is reused. "
            "Automatic full-source downloads above 2 GiB are rejected; use the label-balanced "
            "subset tool for annotation references, and set allow_large_download only for an "
            "explicit user request for the complete source object."
        ),
    ),
]
