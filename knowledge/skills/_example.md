---
name: example-skill
description: Placeholder skill that demonstrates the frontmatter format and the standard body sections. Not used by any agent.
applies_to: []
status: disable
---

# Example Skill

This file exists only to keep the `skills/` directory tracked by git and to illustrate the
expected file format. See `knowledge/README.md` for the full schema. The frontmatter above is
**required** (the loader skips files without it); everything below the closing `---` is free
markdown injected into the agent.

Copy this file, set `status: enable`, fill the frontmatter, and replace each section below.

## When to use
Single-sentence trigger condition — mirror the frontmatter `description`, expanded with concrete
examples of phrasings or situations that should invoke this skill, and when NOT to use it.

## Input
What the skill needs before it can run.
- Required: e.g. an AnnData (`.h5ad`) path with raw counts in `.X`.
- Optional: e.g. a batch key, a cell-type column name (state the default).
- Preconditions the agent must check first (file exists, column present, counts are raw).

## Output
What the skill produces, with concrete artifact names and locations.
- e.g. `results/<name>.csv` — one row per … , columns … .
- e.g. annotated `.h5ad` with `<key>` added to `.obs` / `.obsm`.
- The structured value/paths the tool returns to the caller.

## Success Criteria
How to know the skill succeeded — checkable conditions, not vibes.
- Expected artifacts exist and are non-empty.
- Sanity checks (e.g. proportions sum to ~1; confidence above a threshold; row count matches input).
- What a failure looks like and how the tool signals it (e.g. returns `{"status": "error", ...}`).

## Workflow
Numbered steps the agent follows. Keep each step a single concrete action.
1. Validate inputs (paths resolve, required columns present, counts are raw).
2. Call the relevant tool / run the analysis with the chosen parameters.
3. Verify the outputs against the success criteria above.
4. Summarize results and artifact paths for the user.

## Code Template
A minimal, copy-pasteable snippet the coding agent can adapt. Show the real call, not pseudocode.

```python
import scanpy as sc

adata = sc.read_h5ad("uploads/input.h5ad")
# ... the core operation this skill standardizes ...
adata.write("results/output.h5ad")
print("done:", adata.shape)
```

## Common Issues
Known pitfalls and how to resolve each — the failure modes the model can't infer from tool docs.
- **Symptom → cause → fix.** e.g. "Too few shared genes / aborts → symbol vs Ensembl mismatch →
  reconcile gene IDs before running."
- Wrong default parameter that silently produces bad output (name it, give the right value).
- Environment / data assumptions (species, raw vs normalized, GPU vs CPU).

## References
- Internal tool: `some_tool` (`src/agents/.../tools.py`).
- Related skills: `[[other-skill]]`.
- External docs: link the upstream method/library.
