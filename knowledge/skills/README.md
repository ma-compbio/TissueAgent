# Skills

This directory holds **shared skills** — prose playbooks that one or more specialist agents in [`src/agents/agent_registry/`](../../src/agents/agent_registry/) can pull in when their current task matches.

> **Status: scaffold only.** No skills exist yet (aside from the disabled `_example.md` placeholder). This README locks in the format so future skills are consistent.

## What a skill is — and is not

| | Skill | Agent (in `agent_registry/`) | Plan template (in `../plans/`) |
|---|---|---|---|
| **Form** | Markdown file with YAML frontmatter | Python module (`prompt.py`, `tools.py`, `model_ctor`) | Markdown file with YAML frontmatter |
| **Scope** | A *procedure or reference* — "how to do X" or "facts to remember about Y" | A *capability* — one ReAct loop with bound tools and a model | A *workflow recipe* — sequencing + artifacts + eval gates across multiple agents |
| **Invocation** | Loaded by an agent when the task description matches | Recruited per plan step by the recruiter | Retrieved by the planner at planning time |
| **Has tools?** | No — pure prose | Yes — `StructuredTool` list | No — references agents by name |
| **Has side effects?** | No | Yes (via tools) | No — declarative |

Rule of thumb: **if it has tools or side effects, it's a tool. If it's a written procedure or reference, it's a skill.**

Skills are *shared* — multiple agents can apply the same skill. That's the main reason this directory is separate from each agent's own prompt: avoids duplicating "how to clean an h5ad" across `cell_annotater`, `spot`, and `single_cell`.

## File format

Each skill is one markdown file in this directory:

```
knowledge/skills/
├── README.md                       (this file)
├── _example.md                     (disabled placeholder)
├── clean_anndata.md
├── interpret_de_results.md
└── …
```

### Frontmatter

```markdown
---
name: clean-anndata
description: Steps to validate and clean an AnnData object before downstream analysis. Use when receiving a fresh .h5ad and the task depends on its integrity.
applies_to: [cell_annotator_agent, spot_agent, single_cell_agent, coding_agent]
status: enable
---
```

- **`name`** *(required)* — kebab-case slug. Must be unique within this directory.
- **`description`** *(required)* — one sentence that explains **when to use the skill**. This is the retrieval surface — write it like an Anthropic skill description, not like a title.
- **`applies_to`** *(required)* — list of agent IDs that may load this skill. Use the agent's registry-node id (the form recruiter sees and the manager dispatches against — the agent's `id` field from [`src/agents/agent_defns.py`](../../src/agents/agent_defns.py) with `_agent` appended): `coding_agent`, `cell_annotator_agent`, `spot_agent`, `single_cell_agent`, `gene_agent`, `hypothesis_agent`, `searcher_agent`, `critic_agent`, `pdf_reader_agent`.
- **`status`** *(optional, default `"enable"`)* — `"enable"` or `"disable"`. Disabled skills are excluded from the recruiter prompt index, the `read_skill` tool, and assignment validation.

### Body

Free-form markdown, but use these standard sections so skills are consistent (see
[`_example.md`](_example.md) for a filled-in template):

```markdown
# Clean AnnData

## When to use
Single-sentence trigger condition (mirror the frontmatter `description`), expanded with
examples and when NOT to use it.

## Input
Required and optional inputs; preconditions the agent must check first.

## Output
Concrete artifacts produced (names, locations) and the value the tool returns.

## Success Criteria
Checkable conditions that mean it worked (artifacts exist, sanity checks pass); how failure
is signaled.

## Workflow
1. Validate inputs.
2. Run the tool / analysis.
3. Verify outputs against the success criteria.
4. Summarize results + paths.

## Code Template
A minimal, copy-pasteable snippet the coding agent can adapt (real call, not pseudocode).

## Common Issues
Symptom → cause → fix for known pitfalls; wrong defaults; data/environment assumptions.

## References
- Internal tool: `harmony_transfer_tool`
- Related skills: `[[other-skill]]`
- External docs: scanpy preprocessing
```

Not every section applies to every skill — drop the ones that don't (e.g. a pure reference skill
may have no `Code Template`). Keep the body short enough to fit in a model's working context
comfortably (rough guideline: < 1500 tokens). If you need more, split into multiple skills or
reference external docs.

## What lives here vs. in an agent's `prompt.py`

- **Stays in the agent prompt:** role, ReAct policy, tool calling rules, output format, hard call budgets, refuse-conditions — anything universal to that agent.
- **Goes into a skill:** procedural know-how that several agents would otherwise duplicate, reference tables, well-known pitfalls, recipes for common sub-tasks.

If only one agent ever needs the content, prefer keeping it in that agent's prompt — don't pre-emptively factor.

## Future work (not in scope for this milestone)

- A `list_skills` + `load_skill` tool pair on each agent so skills load lazily (progressive disclosure, similar to Anthropic skills)
- A skill selector based on frontmatter `description` similarity
- Validation that `applies_to` entries are real agent IDs at registration time
- A schema linter run in CI to catch malformed frontmatter

When that work happens, the parent [knowledge/README.md](../README.md) and this file are the authoritative sources of the format. Schema changes should land here first.
