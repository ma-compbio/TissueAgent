---
name: ccc-liana
description: Step 2 of ccc_ensemble. Run the shipped LIANA+ scorer on Step 1 outputs; write project/outputs/liana_scores.csv.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor, ensemble]
status: enable
---

# CCC — LIANA+ (expression-consensus axis)

Fast path: run this command directly; do not list/read the skill directory or script, paste code, or create extra verification files.

```python
%run project/skills/ccc-liana/scripts/ccc_liana.py
```

Reads Step 1 outputs; required output: `project/outputs/liana_scores.csv`. If a file tool is needed, use `/project/...` paths.
