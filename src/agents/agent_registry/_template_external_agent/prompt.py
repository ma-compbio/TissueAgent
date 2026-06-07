"""System prompt and description shown to the recruiter / manager.

Fill in `MyAgentDescription` (1–3 sentences, what your agent does and what input/output to expect) and `MyAgentPrompt`
(the full ReAct-style prompt with Tool, Scope, Output Format sections).

See ``agent_registry/gene_agent/prompt.py`` for a worked example.
"""

MyAgentDescription = """
TODO: One- or two-sentence summary of what this agent does.
Input contract: ...
Output contract: ...
Out of scope: ...
""".strip()


MyAgentPrompt = """
TODO: Write the agent's system prompt here.

See gene_agent/prompt.py for the recommended structure:
  - Visibility & Channels (scratchpad vs. final)
  - Tool list with arguments and return shapes
  - Pre-flight and post-flight checklists
  - Output format
""".strip()
