"""Prompt compatibility for the canonical DeepAgent coding agent."""

from pathlib import Path

from agents.agent_registry.coding_agent_cache.prompt import CodingAgentPrompt

CodingAgentDescription = (Path(__file__).parent / "coding_agent_description.txt").read_text().strip()

__all__ = ["CodingAgentDescription", "CodingAgentPrompt"]
