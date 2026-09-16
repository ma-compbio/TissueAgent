"""CellBench-aligned prompts adapted only for spatial-omics terminology."""

from __future__ import annotations

import json

from benchmark.spatial_cellbench.schemas import CVAnalysis

DIRECT_SYSTEM = "Follow the scientific task and return the requested structured object."

SPATIAL_EXPERT_SYSTEM = """
You are a creative and skilled expert in spatial transcriptomics computational analysis.
Return the requested structured object. Do not number analysis-plan steps; return them as a list.
""".strip()

SPATIAL_CRITIC_SYSTEM = """
You are a spatial transcriptomics expert providing feedback on an analysis plan. Return only
the feedback.
""".strip()


def direct_prompt(context: str, count: int) -> str:
    """Build the spatial adaptation of the upstream one-call baseline prompt."""
    return f"""
Given the following scientific background and research questions, propose {count} spatial
transcriptomics analyses that are consistent with the goals. Make sure your proposed analyses
are specific and ONLY pertain to spatial transcriptomics or spatial-omics.

{context}

Return exactly {count} analyses. Give each a concise title and a detailed paragraph describing
how the analysis would be conducted.
""".strip()


def cv_draft_prompt(context: str, past_analyses: str, overview: str) -> str:
    """Build one minimally spatialized upstream CellVoyager draft prompt."""
    return f"""
You will be provided the background/introduction from a research paper. The computational
analyses done in the paper are hidden from you.

Your role is to propose a computational analysis that you think was most likely done in the
paper.

For the analysis plan, think of the analysis plan as a scientific workflow:
1. Start with exploratory data analysis that is broad and tests many things.
2. Then focus on promising results with more focused analyses.
3. Include statistical validation where appropriate.
Do not number the analysis plan. Each step should be distinct. Use however many steps are
appropriate, but aim for at least five steps.

Ensure that the analysis solely uses data explicitly mentioned in the paper. If histology,
single-cell reference data, depth-resolved measurements, or another modality is not mentioned,
do not use it.

PREVIOUS ANALYSES:
{past_analyses or "None"}

BACKGROUND INFORMATION FROM THE PAPER:
{context}

EXAMPLES OF POTENTIAL SPATIAL ANALYSES:
{overview}
""".strip()


def cv_critic_prompt(
    context: str,
    analysis: CVAnalysis,
    past_analyses: str,
    overview: str,
) -> str:
    """Build the upstream-style expert review prompt for one proposal."""
    return f"""
You will be given a hypothesis, analysis plan, and summary. This analysis was generated from
the background/introduction of a research paper. The computational analyses done in the paper
are hidden, and the goal is to propose an analysis most likely to be in that hidden set.

Your role is to provide feedback on the analysis based on these goals. Ensure that it solely
uses data explicitly mentioned in the paper. If a modality or resource is not mentioned, do not
use it.

TITLE:
{analysis.title}

HYPOTHESIS:
{analysis.hypothesis}

ANALYSIS PLAN:
{json.dumps(analysis.analysis_plan, ensure_ascii=False)}

SUMMARY:
{analysis.summary}

BACKGROUND INFORMATION FROM THE PAPER:
{context}

PREVIOUS ANALYSES:
{past_analyses or "None"}

EXAMPLES OF POTENTIAL SPATIAL ANALYSES:
{overview}
""".strip()


def cv_revision_prompt(
    context: str,
    analysis: CVAnalysis,
    feedback: str,
    past_analyses: str,
    overview: str,
) -> str:
    """Build the upstream-style feedback-incorporation prompt."""
    return f"""
You will be given a hypothesis, analysis plan, and summary generated from a paper's
background/introduction. The computational analyses done in the paper are hidden, and the
goal is to propose an analysis most likely to be in that hidden set.

You will also be given feedback. Incorporate that feedback and update the title, hypothesis,
analysis plan, and summary.

ORIGINAL TITLE:
{analysis.title}

ORIGINAL HYPOTHESIS:
{analysis.hypothesis}

ORIGINAL PLAN:
{json.dumps(analysis.analysis_plan, ensure_ascii=False)}

ORIGINAL SUMMARY:
{analysis.summary}

EXPERT FEEDBACK:
{feedback}

PREVIOUS ANALYSES:
{past_analyses or "None"}

BACKGROUND INFORMATION FROM THE PAPER:
{context}

EXAMPLES OF POTENTIAL SPATIAL ANALYSES:
{overview}
""".strip()
