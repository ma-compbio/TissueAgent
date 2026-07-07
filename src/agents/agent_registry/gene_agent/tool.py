"""StructuredTool exposed to the manager for gene_agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.gene_agent.runner import run_geneagent_cascade


GeneAgentTools: list[StructuredTool] = [
    StructuredTool.from_function(
        func=run_geneagent_cascade,
        name="geneagent_analyze_gene_set_tool",
        description=(
            "Runs the NCBI GeneAgent cascade to propose and verify "
            "biological process names for a gene set. "
            "Arguments: gene_list (List[str], at most 10 canonical symbols, "
            "passed most-significant-first — the cascade verifies each claim "
            "sequentially and is slow, so longer lists are truncated to the "
            "first 10), optional request_id (str). "
            "Returns the final summary, extracted process names, "
            "verification log text, and artifact paths."
        ),
    )
]
