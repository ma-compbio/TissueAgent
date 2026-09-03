---
name: ccc-stlearn
description: Step 4 of ccc_ensemble. Run the shipped stLearn co-expression scorer on Step 1 outputs; write project/outputs/stlearn_scores.csv.
applies_to: [coding_agent]
tags: [ccc, stlearn, spatial, co-expression, ensemble]
status: enable
---

# CCC — stLearn (spatial co-expression axis)

Fast path: run this command directly; do not list/read the skill directory or script, paste code, or create extra verification files.

```python
%run project/skills/ccc-stlearn/scripts/ccc_stlearn.py
```

Reads Step 1 outputs and prep-log radius; required output: `project/outputs/stlearn_scores.csv`. If a file tool is needed, use `/project/...` paths.
