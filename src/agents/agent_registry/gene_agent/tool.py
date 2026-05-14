"""StructuredTool exposed to the manager for gene_agent."""

from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.gene_agent.runner import run_geneagent_cascade


GeneAgentTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=run_geneagent_cascade,
        name="geneagent_analyze_gene_set_tool",
        description=(
            "Runs the NCBI GeneAgent cascade to propose and verify "
            "biological process names for a gene set. "
            "Arguments: gene_list (List[str]), optional request_id (str). "
            "Returns the final summary, extracted process names, "
            "verification log text, and artifact paths."
        ),
    )
]
