from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.gene_agent.tools_impl.run_geneagent_cascade import (
    run_geneagent_cascade,
)

GeneAgentTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=run_geneagent_cascade,
        name="geneagent_analyze_gene_set_tool",
        description=(
            "Runs the GeneAgent cascade to propose and verify biological process names for a gene set. "
            "Arguments: gene_list (List[str]), optional request_id (str). "
            "Returns process-summary artifacts (summaries, verification logs, artifact paths). "
            "Does not produce enrichment-style tables/plots."
        ),
    )
]

