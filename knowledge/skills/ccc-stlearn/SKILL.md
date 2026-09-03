---
name: ccc-stlearn
description: Step 4 of the ccc_ensemble workflow. Runs the shipped vectorised stLearn cci.lr spatial LR co-expression scorer on the shared LR resource at the same native-unit radius as COMMOT, scoring each pair by its neighbourhood co-expression strength. Writes one LR-level score table (stlearn_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, stlearn, spatial, co-expression, ensemble]
status: enable
---

# CCC — stLearn (spatial co-expression axis)

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-stlearn/scripts/ccc_stlearn.py
```

Reads the Step 1 artifacts from `project/outputs/`; writes `project/outputs/stlearn_scores.csv`.
