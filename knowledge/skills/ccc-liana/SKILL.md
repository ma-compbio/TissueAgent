---
name: ccc-liana
description: Step 2 of the ccc_ensemble workflow. Runs the shipped LIANA+ rank_aggregate scorer (non-spatial cell-group expression consensus) on the shared LR resource, and writes one LR-level score table (liana_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor, ensemble]
status: enable
---

# CCC — LIANA+ (expression-consensus axis)

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-liana/scripts/ccc_liana.py
```

Reads the Step 1 artifacts from `project/outputs/`; writes `project/outputs/liana_scores.csv`.
