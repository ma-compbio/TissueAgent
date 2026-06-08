# Knowledge

Centralized, declarative knowledge assets consumed by agents at runtime. Nothing here has side effects or binds tools — it is pure reference content.

## Directory layout

```
knowledge/
├── README.md          (this file)
├── __init__.py        (path constants for Python consumers)
├── plans/             (workflow templates for the planner agent)
├── docs/              (library documentation for the coding agent)
└── skills/            (shared procedural playbooks for specialist agents)
```

## Asset types

### Plans (`plans/`)

Workflow recipes that the **planner agent** retrieves when building a multi-step plan. Each file is Markdown with YAML frontmatter.

**Frontmatter fields**

| Field | Required | Description |
|---|---|---|
| `name` | yes | Snake-case slug, unique within the directory. |
| `status` | yes | `enabled` or `disabled`. Disabled templates are excluded from the planner's template index. |
| `description` | yes | One-sentence summary of what the plan accomplishes. This is the retrieval surface. |

**Body** — free-form Markdown. Recommended sections: *Inputs*, *Outputs*, *Step Sketch*.

### Docs (`docs/`)

JSON files containing library API documentation (e.g. scanpy, squidpy, liana). Loaded by the **coding agent** to ground code generation in accurate API signatures and descriptions.

No frontmatter — each file is a plain JSON object or array whose schema is defined by the doc-scraping pipeline that produces it.

### Skills (`skills/`)

Prose playbooks that one or more specialist agents can pull in when the current task matches. A skill is **not** a tool — it has no side effects. If only one agent ever needs the content, prefer keeping it in that agent's prompt.

**Frontmatter fields**

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | yes | — | Kebab-case slug, unique within the directory. |
| `description` | yes | — | One sentence explaining **when** to use the skill. This is the retrieval surface. |
| `applies_to` | yes | — | List of agent IDs (from `src/agents/agent_defns.py`) that may load this skill. |
| `tags` | no | `[]` | Lowercase keywords for future retrieval. |
| `status` | no | `enable` | `enable` or `disable`. Disabled skills are excluded from prompts. |

**Body** — free-form Markdown. Recommended sections: *When to use*, *Steps*, *Pitfalls*, *References*. Keep under ~1 500 tokens.

## Adding a new asset

1. Create a `.md` (plans, skills) or `.json` (docs) file in the appropriate subdirectory.
2. For Markdown assets, include valid YAML frontmatter between `---` fences.
3. The asset will be picked up automatically at agent-construction time — no registration code needed.
