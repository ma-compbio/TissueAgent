"""StructuredTool exposed to the manager for the CellVoyager external agent."""

from typing import List

from langchain.tools import StructuredTool

from agents.agent_registry.cellvoyager_agent.runner import run_cellvoyager_analysis


CellVoyagerTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=run_cellvoyager_analysis,
        name="cellvoyager_analyze_dataset_tool",
        description=(
            "Runs the upstream CellVoyager autonomous analysis agent on an "
            "AnnData dataset with a biological-background text. "
            "Arguments: h5ad_path (str, absolute), background_text (str), "
            "analysis_name (str, snake_case), optional num_analyses (int, "
            "default 1), max_iterations (int, default 6), model_name (str). "
            "Returns: notebook_path, hypotheses (list of {header, code_excerpt}), "
            "stdout_tail, run_directory, returncode."
        ),
    )
]
