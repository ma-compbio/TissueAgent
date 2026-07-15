"""StructuredTool exposed to the manager for the mLLMCelltype external agent."""

from __future__ import annotations

from langchain.tools import StructuredTool

from agents.agent_registry.mllmcelltype_agent.runner import (
    run_mllmcelltype_annotation,
)


MLLMCelltypeTools: list[StructuredTool] = [
    StructuredTool.from_function(
        func=run_mllmcelltype_annotation,
        name="mllmcelltype_annotate_clusters_tool",
        description=(
            "Annotates scRNA-seq clusters from per-cluster marker-gene lists "
            "using the mLLMCelltype (multi-)LLM annotator. "
            "Arguments: marker_genes (dict[str, list[str]] — cluster id -> "
            "ordered marker symbols, most significant first), species (str, "
            "e.g. 'human'), optional tissue (str), mode ('single' or "
            "'consensus'; default 'single'), provider (str, single mode; "
            "default 'openai'), model (str; recommended to set explicitly), "
            "models (list[str], consensus mode), additional_context (str). "
            "Returns: status, annotations (cluster -> cell-type label), and in "
            "consensus mode consensus_proportion / entropy / model_annotations, "
            "plus run_directory and artifact_path."
        ),
    )
]
