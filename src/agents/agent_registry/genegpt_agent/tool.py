"""StructuredTool exposed to the manager for the GeneGPT external agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.genegpt_agent.runner import run_genegpt_question


GeneGPTTools: list[StructuredTool] = [
    StructuredTool.from_function(
        func=run_genegpt_question,
        name="genegpt_answer_question_tool",
        description=(
            "Answers a factual genomics question by having an LLM call live "
            "NCBI Web APIs (E-utilities over gene/snp/omim, and BLAST for DNA "
            "sequences) in a multi-step loop. Good for: official gene symbol / "
            "alias resolution, genomic location, SNP-to-gene and "
            "gene-to-disease associations, and aligning a DNA sequence. "
            "Arguments: question (str, required), optional mask (str, six 0/1 "
            "chars toggling few-shot components; default '111111'). "
            "Returns: status, answer, api_trace (executed URLs + response "
            "excerpts), num_calls, and artifact_path. "
            "Use the Gene Agent instead for verifying a biological-process "
            "narrative over a whole gene set."
        ),
    )
]
