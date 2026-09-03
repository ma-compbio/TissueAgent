"""Optimizer agent: mines past sessions for failure modes and makes small,
guardrailed edits to the knowledge layer (skills + plan templates).

Invoked as ``tissueagent optimize --sessions ... --focus "..."``. Never edits
``src/`` or skill ``scripts/`` — that boundary is enforced in tool code
(see :mod:`optimizer.guardrails`), not just in the prompt.
"""
