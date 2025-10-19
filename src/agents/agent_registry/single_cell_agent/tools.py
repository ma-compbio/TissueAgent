# src/agents/single_cell_agent/tools.py
from typing import List, Optional, Iterable, Union
from langchain.tools import StructuredTool
from agents.agent_registry.single_cell_agent.tools_impl.retrieve_cellxgene_single_cell_tool import retrieve_cellxgene_single_cell
from agents.agent_registry.single_cell_agent.tools_impl.query_cellxgene_single_cell_tool import run_query_cellxgene_census_live
from api_keys import APIKeys
from config import CACHED_DOCS_DIR


    
query_cellxgene_single_cell_tool = StructuredTool.from_function(
    func=run_query_cellxgene_census_live,
    name="query_cellxgene_census_live_tool",
    description=(
        "Live-filters CELLxGENE Census single-cell datasets by species, tissues, diseases, etc."
        "Accepts strings or lists for filters. Uses the latest Census by default."
    ),
)

retrieve_cellxgene_single_cell_tool = StructuredTool.from_function(
    func=retrieve_cellxgene_single_cell,
    name="retrieve_cellxgene_single_cell_tool",
    description="Downloads a dataset (indexed by dataset_id) from CELLxGENE for downstream analysis"
)


SingleCellTools = [
    query_cellxgene_single_cell_tool,
    retrieve_cellxgene_single_cell_tool,
]

