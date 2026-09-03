---
name: ccc-commot
description: Step 3 of the ccc_ensemble workflow. Runs the shipped COMMOT (collective optimal transport) spatial_communication scorer on the shared LR resource at a single native-unit distance threshold, scoring each LR pair by total routed OT flow. Writes one LR-level score table (commot_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport, ensemble]
status: enable
---

# CCC — COMMOT (spatial optimal-transport axis)

Run the shipped script (do not reimplement it):

```python
%run project/skills/ccc-commot/scripts/ccc_commot.py
```

Reads the Step 1 artifacts from `project/outputs/`; writes `project/outputs/commot_scores.csv`.
