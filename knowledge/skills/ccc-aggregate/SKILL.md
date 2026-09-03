---
name: ccc-aggregate
description: Step 6 (final) of the ccc_ensemble workflow. Runs the shipped build_ensemble step, combining the four member LR-level score tables (LIANA+, COMMOT, stLearn, decoupler) into the ensemble by the mean of the four members' percentile ranks over the LR pairs scored by ALL members. Writes the final ranked ensemble table ccc_ensemble.csv.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, ensemble, consensus]
status: enable
---

# CCC — Ensemble (mean-of-percentile-ranks consensus)

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-aggregate/scripts/ccc_aggregate.py
```

Reads the four `*_scores.csv` member tables from `project/outputs/`; writes the final
`project/outputs/ccc_ensemble.csv`.
