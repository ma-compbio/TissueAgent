# Skill Registry

This directory holds **shared skills** — prose playbooks that one or more specialist agents in [`../agent_registry/`](../agent_registry/) can pull in when their current task matches.

> **Status: scaffold only.** No skills exist yet, no loader has been wired up, and no agent currently consults this directory. This README locks in the format so future skills are consistent.

## What a skill is — and is not

| | Skill | Agent (in `agent_registry/`) | Plan template (in `../planner_agent/plan_registry/`) |
|---|---|---|---|
| **Form** | Markdown file with YAML frontmatter | Python module (`prompt.py`, `tools.py`, `model_ctor`) | YAML file |
| **Scope** | A *procedure or reference* — "how to do X" or "facts to remember about Y" | A *capability* — one ReAct loop with bound tools and a model | A *workflow recipe* — sequencing + artifacts + eval gates across multiple agents |
| **Invocation** | Loaded by an agent when the task description matches | Recruited per plan step by the recruiter | Retrieved by the planner via `template_selector_tool` |
| **Has tools?** | No — pure prose | Yes — `StructuredTool` list | No — references agents by name |
| **Has side effects?** | No | Yes (via tools) | No — declarative |

Rule of thumb: **if it has tools or side effects, it's a tool. If it's a written procedure or reference, it's a skill.**

Skills are *shared* — multiple agents can apply the same skill. That's the main reason this directory is separate from each agent's own prompt: avoids duplicating "how to clean an h5ad" across `cell_annotater`, `spot`, and `single_cell`.

## File format

Each skill is one markdown file in this directory:

```
src/agents/skill_registry/
├── README.md                       (this file)
├── clean_anndata.md
├── interpret_de_results.md
└── …
```

### Frontmatter

```markdown
---
name: clean-anndata
description: Steps to validate and clean an AnnData object before downstream analysis. Use when receiving a fresh .h5ad and the task depends on its integrity.
applies_to: [cell_annotater, spot, single_cell, coding]
tags: [anndata, h5ad, quality_control, preprocessing]
status: enable
---
```

- **`name`** *(required)* — kebab-case slug. Must be unique within this directory.
- **`description`** *(required)* — one sentence that explains **when to use the skill**. This is the retrieval surface — write it like an Anthropic skill description, not like a title.
- **`applies_to`** *(required)* — list of agent IDs from `agent_registry/` that may load this skill. Use the agent's `id` field as it appears in [`../agent_defns.py`](../agent_defns.py) (e.g. `coding`, `cell_annotater`, `spot`, `single_cell`, `gene_agent`, `hypothesis`, `searcher`, `critic`, `pdf_reader`).
- **`tags`** *(optional)* — lowercase keywords to assist future retrieval.
- **`status`** *(optional, default `"enable"`)* — `"enable"` or `"disable"`. Disabled skills are excluded from the recruiter prompt index, the `read_skill` tool, and assignment validation.

### Body

Free-form markdown. A skeleton that works well:

```markdown
# Clean AnnData

## When to use
Single-sentence trigger condition. Mirror what the frontmatter `description`
says, expanded with examples.

## Steps
1. Confirm `.X` is numeric and 2-D.
2. ...

## Pitfalls
- ...

## References
- Internal tool: `harmony_transfer_tool`
- External docs: scanpy preprocessing
```

Keep the body short enough to fit in a model's working context comfortably (rough guideline: < 1500 tokens). If you need more, split into multiple skills or reference external docs.

## What lives here vs. in an agent's `prompt.py`

- **Stays in the agent prompt:** role, ReAct policy, tool calling rules, output format, hard call budgets, refuse-conditions — anything universal to that agent.
- **Goes into a skill:** procedural know-how that several agents would otherwise duplicate, reference tables, well-known pitfalls, recipes for common sub-tasks.

If only one agent ever needs the content, prefer keeping it in that agent's prompt — don't pre-emptively factor.

## Future work (not in scope for this milestone)

- A `list_skills` + `load_skill` tool pair on each agent so skills load lazily (progressive disclosure, similar to Anthropic skills)
- A skill selector based on frontmatter `description` similarity (mirroring `template_selector_tool` for plan templates)
- Validation that `applies_to` entries are real agent IDs at registration time
- A schema linter run in CI to catch malformed frontmatter

When that work happens, this README is the authoritative source of the format. Schema changes should land here first.
