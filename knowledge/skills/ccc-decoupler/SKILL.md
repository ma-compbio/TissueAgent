---
name: ccc-decoupler
description: Step 5 of ccc_ensemble. Run the shipped decoupler/PROGENy-response scorer using Step 1 obs['_dact']; write project/outputs/decoupler_scores.csv.
applies_to: [coding_agent]
tags: [ccc, decoupler, progeny, downstream, pathway, ensemble]
status: enable
---

# CCC — decoupler + PROGENy (downstream-response axis)

Fast path: run this command directly; do not list/read the skill directory or script, paste code, recompute PROGENy, or create extra verification files.

```python
%run project/skills/ccc-decoupler/scripts/ccc_decoupler.py
```

Reads Step 1 outputs including `obs['_dact']`; required output: `project/outputs/decoupler_scores.csv`. If a file tool is needed, use `/project/...` paths.
