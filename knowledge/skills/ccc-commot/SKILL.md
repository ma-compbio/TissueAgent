---
name: ccc-commot
description: Step 3 of ccc_ensemble. Run the shipped COMMOT scorer on Step 1 outputs; write project/outputs/commot_scores.csv.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport, ensemble]
status: enable
---

# CCC — COMMOT (spatial optimal-transport axis)

Fast path: run this command directly; do not list/read the skill directory or script, paste code, or create extra verification files.

```python
%run project/skills/ccc-commot/scripts/ccc_commot.py
```

Reads Step 1 outputs and prep-log radius; required output: `project/outputs/commot_scores.csv`. If a file tool is needed, use `/project/...` paths.
